"""Delphi mờ mã hóa — v0.3: kiểm phiếu kiểm chứng công khai + vá lỗ hổng kiểm phiếu.

1. VÁ LỖ HỔNG (có ở v0.1–v0.2): bản cũ cộng gộp x(x-1) của 5 mức rồi mới che ngẫu nhiên.
   Với số học modulo p, phiếu không phải one-hot như (2, b, c, 0, 0) với b+c = -1, bc = 2 (mod p)
   vẫn thỏa "tổng = 1" và "tổng x(x-1) = 0" -> lọt qua và làm sai kết quả.
   Bản mới che TỪNG Ô bằng một số ngẫu nhiên riêng trước khi cộng -> mọi ô đều phải thỏa x(x-1) = 0.
2. SỐ CHE CÔNG KHAI (Fiat–Shamir): số che không do máy chủ chọn bí mật nữa, mà được sinh từ
   SHA-256 của toàn bộ bảng tin, chỉ SAU KHI mọi phiếu đã được khóa. Ai cũng tính lại được bước
   kiểm phiếu; kẻ gian không biết trước số che nên không chế được phiếu lọt qua.
   Đánh đổi: với số che công khai, hội đồng có thể suy ra nội dung phiếu GIAN (phiếu hợp lệ không lộ gì).
3. CHỐNG "THỬ ĐI THỬ LẠI": p ~ 786.433 nên một lần kiểm có xác suất lọt ~1/786.433. Kẻ nộp cuối có thể
   mã hóa lại hàng triệu lần cho tới khi trúng. Lặp REPS = 3 lần với 3 bộ số che độc lập -> ~1/10^18.
"""
import hashlib, importlib.util, os, time, numpy as np
from openfhe import *

_spec = importlib.util.spec_from_file_location("v02", os.path.join(os.path.dirname(__file__), "05_verifiable_tofn.py"))
v02 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(v02)
P, LV, TFN, H, Committee, aggregate = v02.P, v02.LV, v02.TFN, v02.H, v02.Committee, v02.aggregate
rng = np.random.default_rng(11)
REPS = 3

def board_seed(receipts):
    return hashlib.sha256("".join(receipts).encode()).digest()

def public_masks(seed, i, K, rep=0):
    """Số che tất định, ai cũng tính lại được từ bảng tin."""
    g = np.random.default_rng(int.from_bytes(hashlib.sha256(seed + i.to_bytes(4, "big") + rep.to_bytes(1, "big")).digest()[:16], "big"))
    return g.integers(1, P, K), g.integers(1, P, LV*K)

def lsum(cc, ct, K):
    acc = ct
    for l in range(1, LV): acc = cc.EvalAdd(acc, cc.EvalRotate(ct, l*K))
    return acc

def validate_v3(cc, K, ct, r1, r2):
    slots = cc.GetRingDimension()
    PT = lambda v: cc.MakePackedPlaintext(list(map(int, v)) + [0]*(slots-len(v)))
    s = cc.EvalSub(lsum(cc, ct, K), PT([1]*K))                            # tổng mỗi tiêu chí - 1
    q = cc.EvalMult(ct, cc.EvalSub(ct, PT([1]*(LV*K))))                    # x(x-1) TỪNG ô
    return cc.EvalAdd(cc.EvalMult(s, PT(r1)), lsum(cc, cc.EvalMult(q, PT(r2)), K))  # che từng ô rồi mới cộng

def validate_v2(cc, K, ct):                                                # bản cũ, để chứng minh lỗ hổng
    slots = cc.GetRingDimension()
    PT = lambda v: cc.MakePackedPlaintext(list(map(int, v)) + [0]*(slots-len(v)))
    s = cc.EvalSub(lsum(cc, ct, K), PT([1]*K))
    q = lsum(cc, cc.EvalMult(ct, cc.EvalSub(ct, PT([1]*(LV*K)))), K)       # cộng gộp TRƯỚC khi che
    return cc.EvalAdd(cc.EvalMult(s, PT(rng.integers(1, P, K))), cc.EvalMult(q, PT(rng.integers(1, P, K))))

def weird_ballot_column():
    """(2, b, c, 0, 0) với b + c = -1, bc = 2 mod p: không phải one-hot nhưng qua được kiểm tra cũ."""
    t = next(t for t in range(P) if (t*t + t + 2) % P == 0)
    return [2, t, (P - 1 - t) % P, 0, 0]

def craft_for_masks(r1k, r2k):
    """Kẻ gian BIẾT TRƯỚC số che của một tiêu chí: tìm (a, b, 0, 0, 0) không hợp lệ mà vẫn ra 0."""
    bs = np.arange(P, dtype=np.int64)
    for a in range(2, 50):
        f = (r1k*(a + bs - 1) + r2k[0]*a*(a-1) + (r2k[1]*((bs*bs) % P)) % P - r2k[1]*bs) % P
        hit = np.nonzero(f == 0)[0]
        if len(hit): return [a, int(hit[0]), 0, 0, 0]
    return None

def run(E=20, K=30, present=(1, 2)):
    com = Committee(3, 2, K); cc = com.cc; slots = cc.GetRingDimension(); present = list(present)
    PT = lambda v: cc.MakePackedPlaintext(list(map(int, v)) + [0]*(slots-len(v)))
    dec = lambda ct: com.decrypt(ct, K, present)
    votes = np.clip(rng.integers(1,6,K) + rng.integers(-1,2,(E,K)), 1, 5) - 1
    OH = np.zeros((E, LV, K), np.int64); OH[np.arange(E)[:,None], votes, np.arange(K)[None,:]] = 1
    OH[0,4,3] = 50; OH[1,0,5] = 1; OH[1,4,5] = 1                          # 2 phiếu gian kiểu cũ
    OH[2,:,7] = weird_ballot_column()                                     # phiếu lạ khai thác lỗ hổng
    honest = list(range(3, E))
    out = {}

    # ---------- A. lỗ hổng ở bản cũ
    C = [cc.Encrypt(com.pk, PT(OH[i].reshape(-1))) for i in range(E)]
    out["weird_passes_v2"] = bool(np.all(dec(validate_v2(cc, K, C[2])) == 0))
    S_bad, _ = aggregate(cc, K, C, [2] + honest)
    M_bad = np.stack([dec(S_bad[j]) for j in range(3)], 1) / (4*(len(honest)+1))
    out["v2_max_error"] = float(np.abs(M_bad - (TFN[votes[honest]]/4).mean(0)).max())

    # ---------- B. v0.3: khóa bảng tin -> sinh số che công khai -> kiểm phiếu
    receipts = [H(c) for c in C]; seed = board_seed(receipts)
    t0 = time.time()
    masks = [public_masks(seed, i, K) for i in range(E)]
    checks = [[validate_v3(cc, K, C[i], *public_masks(seed, i, K, rep)) for rep in range(REPS)] for i in range(E)]
    published_all = [[(H(ct), dec(ct)) for ct in row] for row in checks]   # máy chủ công bố hash + kết quả giải mã
    valid = [all(bool(np.all(v == 0)) for _, v in row) for row in published_all]
    published = [row[0] for row in published_all]
    out["t_validate"] = time.time() - t0
    out["catches_all_3"] = valid[:3] == [False, False, False]
    out["no_false_positive"] = all(valid[3:])

    # ---------- C. kiểm toán viên tính lại bước kiểm phiếu từ bảng tin
    seed_a = board_seed([H(c) for c in C])
    re_all = [[H(validate_v3(cc, K, C[i], *public_masks(seed_a, i, K, rep))) for rep in range(REPS)] for i in range(E)]
    out["audit_validity_matches"] = re_all == [[h for h, _ in row] for row in published_all]
    re_hash = [row[0] for row in re_all]

    # ---------- D. máy chủ vu oan phiếu hợp lệ số 5
    claim = list(valid); claim[5] = False                                  # (D1) chỉ sửa lời tuyên bố
    out["false_claim_caught"] = (not claim[5]) and bool(np.all(published[5][1] == 0))
    fake = validate_v3(cc, K, C[0], *masks[0])                             # (D2) thay bản mã kiểm tra bằng của phiếu gian
    out["swapped_check_caught"] = H(fake) != re_hash[5]

    # ---------- E. kẻ gian thích ứng
    r1, r2 = masks[4]; k = 9
    col = craft_for_masks(int(r1[k]), [int(r2[l*K + k]) for l in range(LV)])
    known = OH[4].copy(); known[:, k] = col                                # biết trước số che thật
    out["crafted_passes_if_masks_known"] = bool(np.all(dec(validate_v3(cc, K,
        cc.Encrypt(com.pk, PT(known.reshape(-1))), r1, r2)) == 0))
    # thực tế: số che chỉ có SAU khi bảng tin khóa, và bảng tin chứa chính phiếu của kẻ gian
    C2 = list(C); C2[4] = cc.Encrypt(com.pk, PT(known.reshape(-1)))
    seed2 = board_seed([H(c) for c in C2])
    out["crafted_caught_with_board_masks"] = not all(bool(np.all(dec(validate_v3(cc, K, C2[4],
        *public_masks(seed2, 4, K, rep))) == 0)) for rep in range(REPS))

    # ---------- F. gộp kết quả với phiếu hợp lệ: phải khớp bản rõ
    good = [i for i in range(E) if valid[i]]
    S, _ = aggregate(cc, K, C, good)
    M = np.stack([dec(S[j]) for j in range(3)], 1) / (4*len(good))
    out["exact"] = bool(np.allclose(M, (TFN[votes[good]]/4).mean(0)))
    out["E"], out["K"] = E, K
    return out

if __name__ == "__main__":
    for E, K in [(20, 30), (50, 100)]:
        r = run(E, K)
        ok = lambda b: "đạt" if b else "LỖI"
        print(f"\n=== {r['E']} chuyên gia × {r['K']} tiêu chí (giải mã 2/3) ===")
        print(f"[bản cũ v0.2] phiếu lạ lọt qua kiểm tra: {'CÓ (lỗ hổng)' if r['weird_passes_v2'] else 'không'} | "
              f"sai số trung bình mờ khi phiếu lạ được cộng: {r['v2_max_error']:.1f} (thang 0–1)")
        print(f"[v0.3] bắt cả 3 phiếu gian (gồm phiếu lạ): {ok(r['catches_all_3'])} | không báo nhầm: {ok(r['no_false_positive'])} | "
              f"kiểm phiếu ({REPS} lần) {r['t_validate']:.1f} s")
        print(f"[v0.3] kiểm toán tính lại bước kiểm phiếu khớp: {ok(r['audit_validity_matches'])} | "
              f"bắt vu oan (sửa tuyên bố): {ok(r['false_claim_caught'])} | bắt vu oan (tráo bản mã): {ok(r['swapped_check_caught'])}")
        print(f"[v0.3] kẻ gian biết trước số che thì lọt: {'có' if r['crafted_passes_if_masks_known'] else 'không'} "
              f"-> với số che từ bảng tin thì bị bắt: {ok(r['crafted_caught_with_board_masks'])} | kết quả chính xác: {ok(r['exact'])}")
