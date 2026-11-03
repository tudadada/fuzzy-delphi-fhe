"""Delphi mờ mã hóa — bản dồn 5 mức vào 1 bản mã (ô thứ l*K+k = mức l của tiêu chí k).
Giữ nguyên: giải mã ngưỡng 3 người + chống phiếu gian. Cần thêm khóa xoay (do hội đồng tạo chung 1 lần)."""
import time, numpy as np
from openfhe import *
P = 786433; LV = 5
TFN = np.array([(0,0,1),(0,1,2),(1,2,3),(2,3,4),(3,4,4)])
rng = np.random.default_rng(7)

def setup(n, K):
    p = CCParamsBFVRNS(); p.SetPlaintextModulus(P); p.SetMultiplicativeDepth(2)
    cc = GenCryptoContext(p)
    for f in (PKESchemeFeature.PKE, PKESchemeFeature.KEYSWITCH, PKESchemeFeature.LEVELEDSHE,
              PKESchemeFeature.ADVANCEDSHE, PKESchemeFeature.MULTIPARTY): cc.Enable(f)
    idx = [l*K for l in range(1, LV)]
    kps = [cc.KeyGen()]
    ek = cc.KeySwitchGen(kps[0].secretKey, kps[0].secretKey)
    cc.EvalAtIndexKeyGen(kps[0].secretKey, idx)
    rk = cc.GetEvalAutomorphismKeyMap(kps[0].secretKey.GetKeyTag())
    for _ in range(1, n):
        kp = cc.MultipartyKeyGen(kps[-1].publicKey); tag = kp.publicKey.GetKeyTag()
        ek = cc.MultiAddEvalKeys(ek, cc.MultiKeySwitchGen(kp.secretKey, kp.secretKey, ek), tag)
        rk = cc.MultiAddEvalAutomorphismKeys(rk, cc.MultiEvalAtIndexKeyGen(kp.secretKey, rk, idx, tag), tag)
        kps.append(kp)
    tag = kps[-1].publicKey.GetKeyTag()
    parts = [cc.MultiMultEvalKey(kp.secretKey, ek, tag) for kp in kps]
    fin = parts[0]
    for x in parts[1:]: fin = cc.MultiAddEvalMultKeys(fin, x, fin.GetKeyTag())
    cc.InsertEvalMultKey([fin]); cc.InsertEvalAutomorphismKey(rk)
    return cc, kps

def jdec(cc, kps, ct, n):
    sh = [cc.MultipartyDecryptLead([ct], kps[0].secretKey)[0]] + \
         [cc.MultipartyDecryptMain([ct], kp.secretKey)[0] for kp in kps[1:]]
    pt = cc.MultipartyDecryptFusion(sh); pt.SetLength(n)
    v = np.array(pt.GetPackedValue()); return np.where(v > P//2, v-P, v)

def run(E, K, n_cheat=2):
    cc, kps = setup(3, K); pk = kps[-1].publicKey; N = cc.GetRingDimension(); slots = N
    votes = np.clip(rng.integers(1,6,K) + rng.integers(-1,2,(E,K)), 1, 5) - 1
    OH = np.zeros((E, LV, K), int); OH[np.arange(E)[:,None], votes, np.arange(K)[None,:]] = 1
    if n_cheat: OH[0,4,3] = 50; OH[1,0,5] = 1; OH[1,4,5] = 1
    pad = lambda v: list(map(int, v)) + [0]*(slots - len(v))
    PT = lambda v: cc.MakePackedPlaintext(pad(v))
    t0 = time.time()
    C = [cc.Encrypt(pk, PT(OH[i].reshape(-1))) for i in range(E)]       # 1 bản mã / chuyên gia
    t_enc = (time.time()-t0)/E
    up = len(Serialize(C[0], BINARY))/1024
    def lsum(ct):                                                       # cộng 5 mức về ô 0..K-1
        acc = ct
        for l in range(1, LV): acc = cc.EvalAdd(acc, cc.EvalRotate(ct, l*K))
        return acc
    one = PT([1]*K)
    t0 = time.time(); checks = []
    for i in range(E):
        s = cc.EvalSub(lsum(C[i]), one)
        q = lsum(cc.EvalMult(C[i], cc.EvalSub(C[i], PT([1]*(LV*K)))))
        r1 = PT(rng.integers(1, P, K)); r2 = PT(rng.integers(1, P, K))
        checks.append(cc.EvalAdd(cc.EvalMult(s, r1), cc.EvalMult(q, r2)))
    t_chk = time.time()-t0
    valid = [bool(np.all(jdec(cc, kps, c, K) == 0)) for c in checks]
    t0 = time.time()
    good = [i for i in range(E) if valid[i]]; G = len(good)
    W = [PT(np.repeat(TFN[:, j], K)) for j in range(3)]
    A = {i: [lsum(cc.EvalMult(C[i], W[j])) for j in range(3)] for i in good}
    S = list(A[good[0]])
    for i in good[1:]: S = [cc.EvalAdd(S[j], A[i][j]) for j in range(3)]
    GG = PT([G]*slots); D2 = {}
    for i in good:
        acc = None
        for j in range(3):
            d = cc.EvalSub(cc.EvalMult(A[i][j], GG), S[j]); sq = cc.EvalMult(d, d)
            acc = sq if acc is None else cc.EvalAdd(acc, sq)
        D2[i] = acc
    t_agg = time.time()-t0
    M = np.stack([jdec(cc, kps, S[j], K) for j in range(3)], 1)/(4*G)
    dist = np.sqrt(np.array([jdec(cc, kps, D2[i], K) for i in good])/(3*16*G*G))
    truth = [i >= n_cheat for i in range(E)]
    Tp = TFN[votes[good]]/4; Mp = Tp.mean(0); dp = np.sqrt(((Tp-Mp)**2).mean(2))
    return dict(E=E, K=K, N=N, up=up, enc=t_enc*1000, chk=t_chk*1000, agg=t_agg*1000,
                detect=valid==truth, exact=np.allclose(M,Mp) and np.allclose(dist,dp))

if __name__ == "__main__":
    for E, K in [(15, 20), (50, 100), (50, 800)]:
        r = run(E, K)
        print(f"{E:3d} chuyên gia × {K:3d} tiêu chí | N={r['N']} | gửi/người {r['up']:.0f} KB | mã hóa {r['enc']:.1f} ms | "
              f"kiểm phiếu {r['chk']:.0f} ms | gộp {r['agg']:.0f} ms | bắt gian {'đúng' if r['detect'] else 'SAI'} | "
              f"{'chính xác 100%' if r['exact'] else 'LỆCH'}")
