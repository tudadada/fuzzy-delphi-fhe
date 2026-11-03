"""Delphi mờ mã hóa — v0.2: cải thiện theo góp ý.

So với 04_packed_final.py:
  1. Giải mã t-trên-n (mặc định 2/3): mỗi thành viên chia mảnh khóa của mình (Shamir) cho người khác
     lúc khởi tạo. Vắng 1 người, 2 người còn lại khôi phục phần của người vắng rồi giải mã.
  2. Kiểm chứng công khai: mỗi chuyên gia nhận biên nhận = SHA-256 bản mã của mình. Máy chủ công bố
     toàn bộ bản mã lên "bảng tin". Phép gộp là tất định và không dùng bí mật, nên bất kỳ ai
     cũng tính lại được và so với kết quả máy chủ công bố -> bắt được máy chủ bỏ phiếu hoặc tính sai.
  3. Xáo trộn độ lệch: máy chủ hoán vị ngẫu nhiên danh sách độ lệch trước khi giải mã -> hội đồng
     thấy phân bố độ lệch nhưng không gắn được với từng chuyên gia (nếu máy chủ không thông đồng).
"""
import hashlib, time, numpy as np
from openfhe import *

P = 786433; LV = 5
TFN = np.array([(0,0,1),(0,1,2),(1,2,3),(2,3,4),(3,4,4)])
rng = np.random.default_rng(7)
H = lambda ct: hashlib.sha256(Serialize(ct, BINARY)).hexdigest()

class Committee:
    def __init__(self, n, t, K):
        self.n, self.t = n, t
        p = CCParamsBFVRNS(); p.SetPlaintextModulus(P); p.SetMultiplicativeDepth(2)
        cc = self.cc = GenCryptoContext(p)
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
        self.kps, self.pk = kps, kps[-1].publicKey
        # mỗi thành viên i (đánh số 1..n) chia mảnh khóa của mình cho những người còn lại
        self.held = {j: {} for j in range(1, n+1)}        # held[j][i] = mảnh khóa của i mà j giữ
        for i in range(1, n+1):
            for j, s in cc.ShareKeys(kps[i-1].secretKey, n, t, i, "shamir").items():
                self.held[j][i] = s

    def decrypt(self, ct, length, present):
        assert len(present) >= self.t, "không đủ số người tối thiểu"
        cc = self.cc; keys = {}
        for i in range(1, self.n+1):
            if i in present: keys[i] = self.kps[i-1].secretKey
            else:                                          # khôi phục phần của người vắng
                rec = cc.KeyGen().secretKey
                cc.RecoverSharedKey(rec, {j: self.held[j][i] for j in present[:self.t]}, self.n, self.t, "shamir")
                keys[i] = rec
        sh = [cc.MultipartyDecryptLead([ct], keys[1])[0]] + \
             [cc.MultipartyDecryptMain([ct], keys[i])[0] for i in range(2, self.n+1)]
        pt = cc.MultipartyDecryptFusion(sh); pt.SetLength(length)
        v = np.array(pt.GetPackedValue()); return np.where(v > P//2, v-P, v)

def aggregate(cc, K, C, good):
    """Phép gộp công khai, tất định: ai cũng chạy lại được trên các bản mã đã công bố."""
    slots = cc.GetRingDimension()
    PT = lambda v: cc.MakePackedPlaintext(list(map(int, v)) + [0]*(slots-len(v)))
    def lsum(ct):
        acc = ct
        for l in range(1, LV): acc = cc.EvalAdd(acc, cc.EvalRotate(ct, l*K))
        return acc
    W = [PT(np.repeat(TFN[:, j], K)) for j in range(3)]
    A = {i: [lsum(cc.EvalMult(C[i], W[j])) for j in range(3)] for i in good}
    S = list(A[good[0]])
    for i in good[1:]: S = [cc.EvalAdd(S[j], A[i][j]) for j in range(3)]
    GG = PT([len(good)]*slots); D2 = []
    for i in good:
        acc = None
        for j in range(3):
            d = cc.EvalSub(cc.EvalMult(A[i][j], GG), S[j]); sq = cc.EvalMult(d, d)
            acc = sq if acc is None else cc.EvalAdd(acc, sq)
        D2.append(acc)
    return S, D2

def validate(cc, K, ct):
    slots = cc.GetRingDimension()
    PT = lambda v: cc.MakePackedPlaintext(list(map(int, v)) + [0]*(slots-len(v)))
    def lsum(c):
        acc = c
        for l in range(1, LV): acc = cc.EvalAdd(acc, cc.EvalRotate(c, l*K))
        return acc
    s = cc.EvalSub(lsum(ct), PT([1]*K))
    q = lsum(cc.EvalMult(ct, cc.EvalSub(ct, PT([1]*(LV*K)))))
    r1, r2 = PT(rng.integers(1, P, K)), PT(rng.integers(1, P, K))
    return cc.EvalAdd(cc.EvalMult(s, r1), cc.EvalMult(q, r2))

def run(E=20, K=30, n=3, t=2, absent=(3,)):
    com = Committee(n, t, K); cc = com.cc; slots = cc.GetRingDimension()
    present = [i for i in range(1, n+1) if i not in absent]
    votes = np.clip(rng.integers(1,6,K) + rng.integers(-1,2,(E,K)), 1, 5) - 1
    OH = np.zeros((E, LV, K), int); OH[np.arange(E)[:,None], votes, np.arange(K)[None,:]] = 1
    OH[0,4,3] = 50; OH[1,0,5] = 1; OH[1,4,5] = 1                       # 2 phiếu gian
    PT = lambda v: cc.MakePackedPlaintext(list(map(int, v)) + [0]*(slots-len(v)))
    C = [cc.Encrypt(com.pk, PT(OH[i].reshape(-1))) for i in range(E)]
    receipts = [H(c) for c in C]                                        # chuyên gia giữ biên nhận
    board = list(C)                                                     # máy chủ công bố bản mã

    t0 = time.time()
    valid = [bool(np.all(com.decrypt(validate(cc, K, c), K, present) == 0)) for c in board]
    good = [i for i in range(E) if valid[i]]
    S, D2 = aggregate(cc, K, board, good)
    perm = rng.permutation(len(D2)); D2s = [D2[k] for k in perm]       # xáo trộn
    M = np.stack([com.decrypt(S[j], K, present) for j in range(3)], 1)/(4*len(good))
    dist = np.sqrt(np.array([com.decrypt(x, K, present) for x in D2s])/(3*16*len(good)**2))
    t_total = time.time()-t0
    claimed = [H(s) for s in S]                                         # máy chủ công bố kết quả

    # --- đối chứng bản rõ
    Tp = TFN[votes[good]]/4; Mp = Tp.mean(0); dp = np.sqrt(((Tp-Mp)**2).mean(2))
    exact = np.allclose(M, Mp) and np.allclose(np.sort(dist, 0), np.sort(dp[perm], 0))
    # --- kiểm toán viên độc lập tính lại từ bảng tin
    S_aud, _ = aggregate(cc, K, board, good)
    audit_ok = [H(s) for s in S_aud] == claimed
    # --- thử 1: máy chủ lén bỏ phiếu của chuyên gia số 7 khỏi bảng tin
    board_drop = [c for i, c in enumerate(board) if i != 7]
    missing = [i for i, r in enumerate(receipts) if r not in {H(c) for c in board_drop}]
    # --- thử 2: bảng tin đủ, nhưng máy chủ tính kết quả mà không cộng phiếu số 7
    S_cheat, _ = aggregate(cc, K, board, [i for i in good if i != 7])
    audit_catch = [H(s) for s in S_cheat] != [H(s) for s in S_aud]
    # --- thử 3: chỉ 1 người có mặt -> phải bị từ chối
    try: com.decrypt(S[0], K, present[:1]); solo_blocked = False
    except AssertionError: solo_blocked = True
    return dict(E=E, K=K, n=n, t=t, absent=absent, upload=len(Serialize(C[0], BINARY))/1024,
                t_total=t_total, detect=(valid[:2] == [False, False] and all(valid[2:])),
                exact=exact, audit_ok=audit_ok, drop_caught=(missing == [7]),
                compute_caught=audit_catch, solo_blocked=solo_blocked)

if __name__ == "__main__":
    for E, K, absent in [(20, 30, (3,)), (20, 30, (1,)), (50, 100, (2,)), (50, 100, ())]:
        r = run(E, K, absent=absent)
        ok = lambda b: "đạt" if b else "LỖI"
        print(f"{r['E']} chuyên gia × {r['K']} tiêu chí | {r['t']}/{r['n']}, vắng {list(r['absent']) or 'không ai'} | "
              f"gửi {r['upload']:.0f} KB | tổng {r['t_total']:.1f} s | bắt phiếu gian {ok(r['detect'])} | "
              f"chính xác {ok(r['exact'])} | kiểm toán khớp {ok(r['audit_ok'])} | bắt bỏ phiếu {ok(r['drop_caught'])} | "
              f"bắt tính sai {ok(r['compute_caught'])} | 1 người bị chặn {ok(r['solo_blocked'])}")
