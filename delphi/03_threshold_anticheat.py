"""Delphi mờ mã hóa — OpenFHE, giải mã ngưỡng + chống phiếu gian.

- Hội đồng 3 người giữ 3 mảnh khóa. Phải đủ cả 3 mới giải mã được (không ai tự giải mã một mình).
- Chuyên gia KHÔNG gửi số (a,b,c). Họ gửi phiếu "chọn 1 trong 5 mức" dạng 0/1 (one-hot),
  máy chủ tự đổi sang số mờ tam giác -> a<=b<=c và nằm trong thang được bảo đảm bằng cấu trúc.
- Kiểm tra hợp lệ trên bản mã: tổng các ô = 1 và mỗi ô x*(x-1) = 0. Kết quả kiểm tra được che
  bằng số ngẫu nhiên: phiếu hợp lệ -> giải mã ra 0; phiếu gian -> số ngẫu nhiên, không lộ nội dung.
"""
import time, sys, numpy as np
from openfhe import *

P = 786433
LEVELS = 5
TFN = np.array([(0,0,1), (0,1,2), (1,2,3), (2,3,4), (3,4,4)])  # đơn vị 0.25
rng = np.random.default_rng(7)

def setup(n_parties):
    p = CCParamsBFVRNS(); p.SetPlaintextModulus(P); p.SetMultiplicativeDepth(2)
    cc = GenCryptoContext(p)
    for f in (PKESchemeFeature.PKE, PKESchemeFeature.KEYSWITCH, PKESchemeFeature.LEVELEDSHE,
              PKESchemeFeature.ADVANCEDSHE, PKESchemeFeature.MULTIPARTY): cc.Enable(f)
    kps = [cc.KeyGen()]
    ek = cc.KeySwitchGen(kps[0].secretKey, kps[0].secretKey)
    for _ in range(1, n_parties):                       # mỗi thành viên góp một mảnh khóa
        kp = cc.MultipartyKeyGen(kps[-1].publicKey)
        eki = cc.MultiKeySwitchGen(kp.secretKey, kp.secretKey, ek)
        ek = cc.MultiAddEvalKeys(ek, eki, kp.publicKey.GetKeyTag()); kps.append(kp)
    tag = kps[-1].publicKey.GetKeyTag()
    parts = [cc.MultiMultEvalKey(kp.secretKey, ek, tag) for kp in kps]
    final = parts[0]
    for x in parts[1:]: final = cc.MultiAddEvalMultKeys(final, x, final.GetKeyTag())
    cc.InsertEvalMultKey([final])
    return cc, kps

def joint_decrypt(cc, kps, ct, n):
    shares = [cc.MultipartyDecryptLead([ct], kps[0].secretKey)[0]]
    shares += [cc.MultipartyDecryptMain([ct], kp.secretKey)[0] for kp in kps[1:]]
    pt = cc.MultipartyDecryptFusion(shares); pt.SetLength(n)
    v = np.array(pt.GetPackedValue()); return np.where(v > P//2, v-P, v)

def run(E, K, n_parties=3, n_cheat=2):
    cc, kps = setup(n_parties)
    pk = kps[-1].publicKey
    ring = cc.GetRingDimension()
    votes = np.clip(rng.integers(1, 6, K) + rng.integers(-1, 2, (E, K)), 1, 5) - 1   # mức 0..4
    OH = np.zeros((E, LEVELS, K), int); OH[np.arange(E)[:,None], votes, np.arange(K)[None,:]] = 1
    cheaters = list(range(n_cheat))
    if n_cheat:                                   # phiếu gian: dồn 50 phiếu vào một ô / chọn 2 mức cùng lúc
        OH[0, 4, 3] = 50
        OH[1, 0, 5] = 1; OH[1, 4, 5] = 1
    enc = lambda v: cc.Encrypt(pk, cc.MakePackedPlaintext([int(x) for x in v]))
    const = lambda c: cc.MakePackedPlaintext([int(c)]*K)

    t0 = time.time()
    C = [[enc(OH[i, l]) for l in range(LEVELS)] for i in range(E)]       # mỗi chuyên gia 5 bản mã
    t_enc = (time.time()-t0)/E
    up_kb = sum(len(Serialize(c, BINARY)) for c in C[0]) / 1024

    t0 = time.time()
    # (1) kiểm tra phiếu hợp lệ, có che ngẫu nhiên
    checks = []
    for i in range(E):
        s = C[i][0]
        for l in range(1, LEVELS): s = cc.EvalAdd(s, C[i][l])
        s = cc.EvalSub(s, const(1))
        q = None
        for l in range(LEVELS):
            t = cc.EvalMult(C[i][l], cc.EvalSub(C[i][l], const(1)))
            q = t if q is None else cc.EvalAdd(q, t)
        r1 = cc.MakePackedPlaintext(rng.integers(1, P, K).tolist())
        r2 = cc.MakePackedPlaintext(rng.integers(1, P, K).tolist())
        checks.append(cc.EvalAdd(cc.EvalMult(s, r1), cc.EvalMult(q, r2)))
    t_chk = time.time()-t0
    valid = []
    for i in range(E):
        v = joint_decrypt(cc, kps, checks[i], K); valid.append(bool(np.all(v == 0)))

    # (2) chỉ gộp phiếu hợp lệ: đổi one-hot -> số mờ (a,b,c) ngay trên bản mã
    t0 = time.time()
    good = [i for i in range(E) if valid[i]]; G = len(good)
    def tfn(i, j):
        acc = None
        for l in range(LEVELS):
            if TFN[l, j]:
                t = cc.EvalMult(C[i][l], const(TFN[l, j])); acc = t if acc is None else cc.EvalAdd(acc, t)
        return acc
    A = {i: [tfn(i, j) for j in range(3)] for i in good}
    S = [A[good[0]][j] for j in range(3)]
    for i in good[1:]: S = [cc.EvalAdd(S[j], A[i][j]) for j in range(3)]
    D2 = {}
    for i in good:
        acc = None
        for j in range(3):
            d = cc.EvalSub(cc.EvalMult(A[i][j], const(G)), S[j]); sq = cc.EvalMult(d, d)
            acc = sq if acc is None else cc.EvalAdd(acc, sq)
        D2[i] = acc
    t_agg = time.time()-t0

    M = np.stack([joint_decrypt(cc, kps, S[j], K) for j in range(3)], 1) / (4*G)
    dfz = M.mean(1)
    dist = np.sqrt(np.array([joint_decrypt(cc, kps, D2[i], K) for i in good]) / (3*16*G*G))

    # đối chứng bản rõ chỉ trên phiếu hợp lệ thật
    truth_valid = [i not in cheaters for i in range(E)]
    Tp = TFN[votes[good]] / 4                            # (G,K,3)
    Mp = Tp.mean(0); dp = np.sqrt(((Tp - Mp)**2).mean(2))
    exact = np.allclose(M, Mp) and np.allclose(dist, dp)

    # thử: một thành viên hội đồng tự giải mã một mình -> phải ra rác
    pt = cc.Decrypt(kps[0].secretKey, C[2][0]); pt.SetLength(K)
    solo = np.array(pt.GetPackedValue())
    solo_leak = np.array_equal(np.where(solo > P//2, solo-P, solo), OH[2, 0])

    keysz = len(SerializeEvalMultKeyString(BINARY, "")) / 1024 if False else None
    return dict(E=E, K=K, ring=ring, up=up_kb, enc=t_enc*1000, chk=t_chk*1000, agg=t_agg*1000,
                detect=(valid == truth_valid), exact=exact, solo_leak=solo_leak,
                keep=int((dfz >= 0.5).sum()), cons=int((((dist <= 0.2).mean(0)) >= 0.75).sum()))

if __name__ == "__main__":
    print(f"{'Chuyên gia':>10} {'Tiêu chí':>8} {'N':>6} {'Gửi/người KB':>12} {'Mã hóa ms':>9} "
          f"{'Kiểm phiếu ms':>13} {'Gộp ms':>8} {'Bắt gian':>8} {'Chính xác':>9} {'1 người tự giải mã':>18}")
    for E, K in [(15, 20), (50, 100)]:
        r = run(E, K)
        print(f"{r['E']:10d} {r['K']:8d} {r['ring']:6d} {r['up']:12.0f} {r['enc']:9.1f} {r['chk']:13.0f} "
              f"{r['agg']:8.0f} {'đúng 2/2' if r['detect'] else 'SAI':>8} {'100%' if r['exact'] else 'LỆCH':>9} "
              f"{'LỘ' if r['solo_leak'] else 'ra rác':>18}")
