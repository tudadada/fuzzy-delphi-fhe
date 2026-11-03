"""Delphi mờ mã hóa — v0.4: gia cố theo SECURITY.md.

So với v0.3 (07_public_validity.py), giữ nguyên toàn bộ giao thức và phép thử, chỉ thay:
  G2. Phủ nhiễu khi giải mã nhiều bên: NOISE_FLOODING_MULTIPARTY làm mặc định
      (OpenFHE mặc định FIXED_NOISE_MULTIPARTY, không phủ nhiễu).
  G4. Số che sinh bằng SHAKE-256 có tách miền (domain separation) và lấy mẫu loại bỏ
      (rejection sampling) -> phân bố đều chính xác trên [1, p-1], thay cho NumPy PCG64.
  G5. Kiểm phiếu lặp R = 5 lần -> mỗi lần thử của kẻ gian lọt với xác suất <= (p-1)^-5 ~ 2^-97.9.
"""
import hashlib, importlib.util, os, time, numpy as np
from openfhe import *

_here = os.path.dirname(__file__)
_spec = importlib.util.spec_from_file_location("v03", os.path.join(_here, "07_public_validity.py"))
v03 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(v03)
P, LV = v03.P, v03.LV
DOMAIN = b"encrypted-fuzzy-delphi/v0.4/validity-mask"
REPS = 5

# ---- G2: phủ nhiễu
_orig_params = v03.v02.CCParamsBFVRNS
def _flooding_params():
    p = _orig_params(); p.SetMultipartyMode(MultipartyMode.NOISE_FLOODING_MULTIPARTY); return p
v03.v02.CCParamsBFVRNS = _flooding_params

# ---- G4: số che từ SHAKE-256, phân bố đều chính xác trên [1, p-1]
def _uniform_nonzero(xof_input, count):
    """Lấy mẫu loại bỏ: đọc từng 20 bit (2^20 > p-1), giữ giá trị < p-1, trả về giá trị + 1."""
    n_bytes = 3 * count * 2
    while True:
        stream = hashlib.shake_256(xof_input).digest(n_bytes)
        vals = []
        for j in range(0, len(stream) - 2, 3):
            v = int.from_bytes(stream[j:j+3], "big") & 0xFFFFF
            if v < P - 1:
                vals.append(v + 1)
                if len(vals) == count: return np.array(vals, dtype=np.int64)
        n_bytes *= 2                                               # hiếm khi xảy ra: đọc dài hơn

def shake_masks(seed, i, K, rep=0):
    base = DOMAIN + seed + i.to_bytes(4, "big") + rep.to_bytes(1, "big")
    return _uniform_nonzero(base + b"/r1", K), _uniform_nonzero(base + b"/r2", LV * K)

v03.public_masks = shake_masks
# ---- G5: lặp 5 lần
v03.REPS = REPS

def mask_uniformity_check(n=200_000):
    """Kiểm tra nhanh phân bố số che: giá trị nhỏ nhất, lớn nhất, trung bình so với kỳ vọng."""
    v = _uniform_nonzero(DOMAIN + b"/uniformity-test", n)
    return int(v.min()), int(v.max()), float(v.mean()), P / 2

if __name__ == "__main__":
    lo, hi, mean, expect = mask_uniformity_check()
    print(f"Số che SHAKE-256: nhỏ nhất {lo}, lớn nhất {hi} (phải nằm trong [1, {P-1}]), "
          f"trung bình {mean:,.0f} (kỳ vọng {expect:,.0f})")
    for E, K in [(20, 30), (50, 100)]:
        t = time.time(); r = v03.run(E, K); dt = time.time() - t
        com = v03.Committee(3, 2, K); cc = com.cc
        up = len(Serialize(cc.Encrypt(com.pk, cc.MakePackedPlaintext([1]*K)), BINARY)) / 1024
        ok = lambda b: "đạt" if b else "LỖI"
        print(f"\n=== v0.4: {E} chuyên gia × {K} tiêu chí | phủ nhiễu, SHAKE-256, kiểm {REPS} lần, giải mã 2/3 ===")
        print(f"N={cc.GetRingDimension()} | gửi/người {up:.0f} KB | kiểm phiếu {r['t_validate']:.1f} s | tổng {dt:.1f} s")
        print(f"bắt cả 3 phiếu gian: {ok(r['catches_all_3'])} | không báo nhầm: {ok(r['no_false_positive'])} | "
              f"kiểm toán khớp: {ok(r['audit_validity_matches'])} | bắt vu oan: {ok(r['false_claim_caught'] and r['swapped_check_caught'])} | "
              f"bắt phiếu chế sẵn: {ok(r['crafted_caught_with_board_masks'])} | chính xác: {ok(r['exact'])}")
