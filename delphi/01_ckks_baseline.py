"""Delphi mờ trên dữ liệu mã hóa (CKKS).
Mỗi chuyên gia chấm 20 tiêu chí theo thang ngôn ngữ 5 mức -> số mờ tam giác (a,b,c).
Máy chủ chỉ thấy bản mã; chỉ kết quả gộp được giải mã.
Quy tắc Delphi mờ chuẩn (Chen 2000 / Cheng & Lin 2002):
  - trung bình mờ mỗi tiêu chí: (mean a, mean b, mean c)
  - khoảng cách chuyên gia i: d_i = sqrt(((a_i-ā)^2+(b_i-b̄)^2+(c_i-c̄)^2)/3); đồng thuận nếu d_i <= 0.2
  - giải mờ (ā+b̄+c̄)/3 >= 0.5 -> giữ tiêu chí
"""
import time, numpy as np, tenseal as ts
rng = np.random.default_rng(1)
SCALE = {1:(0.0,0.0,0.25), 2:(0.0,0.25,0.5), 3:(0.25,0.5,0.75), 4:(0.5,0.75,1.0), 5:(0.75,1.0,1.0)}
E, K = 15, 20  # số chuyên gia, số tiêu chí
true_q = rng.integers(1, 6, K)
votes = np.clip(true_q + rng.integers(-1, 2, (E, K)), 1, 5)
TFN = np.array([[SCALE[v] for v in row] for row in votes])  # (E,K,3)
flat = TFN.reshape(E, K*3)  # mỗi chuyên gia 1 vectơ 60 ô

# ---- bản rõ (đối chứng) ----
mean = flat.mean(0)
d2 = ((flat - mean)**2).reshape(E, K, 3).mean(2)
defuzz = mean.reshape(K,3).mean(1)

# ---- bản mã hóa ----
ctx = ts.context(ts.SCHEME_TYPE.CKKS, 16384, coeff_mod_bit_sizes=[60, 40, 40, 40, 60])
ctx.global_scale = 2**40; ctx.generate_galois_keys()
t0 = time.time()
cts = [ts.ckks_vector(ctx, row.tolist()) for row in flat]  # mỗi chuyên gia tự mã hóa
t_enc = (time.time()-t0)/E
ct_kb = len(cts[0].serialize())/1024
pub = ctx.copy(); pub.make_context_public()
key_kb = len(pub.serialize(save_galois_keys=True, save_relin_keys=True))/1024

t0 = time.time()
s = cts[0].copy()
for c in cts[1:]: s += c
enc_mean = s * (1/E)                                   # trung bình mờ (đã mã hóa)
enc_def = enc_mean.matmul(np.kron(np.eye(K), np.ones((3,1))/3).tolist())  # giải mờ
enc_d2 = []
for c in cts:                                          # độ lệch từng chuyên gia (đã mã hóa)
    diff = c - enc_mean; sq = diff * diff
    enc_d2.append(sq.matmul(np.kron(np.eye(K), np.ones((3,1))/3).tolist()))
t_srv = time.time()-t0

dm = np.array(enc_mean.decrypt()); dd = np.array(enc_def.decrypt())
dd2 = np.array([v.decrypt() for v in enc_d2])

keep_p = defuzz >= 0.5; keep_e = dd >= 0.5
cons_p = (np.sqrt(np.maximum(d2,0)) <= 0.2).mean(0); cons_e = (np.sqrt(np.maximum(dd2,0)) <= 0.2).mean(0)
print(f"{E} chuyên gia × {K} tiêu chí (60 số/chuyên gia)")
print(f"Bản mã mỗi chuyên gia gửi: {ct_kb:.0f} KB | Khóa công khai+tính toán: {key_kb/1024:.1f} MB")
print(f"Mã hóa: {t_enc*1000:.1f} ms/chuyên gia | Máy chủ tính toàn bộ: {t_srv*1000:.0f} ms")
print(f"Sai số lớn nhất: trung bình {np.abs(dm-mean).max():.1e}, giải mờ {np.abs(dd-defuzz).max():.1e}, độ lệch {np.abs(dd2-d2).max():.1e}")
print(f"Quyết định giữ/bỏ tiêu chí khớp: {(keep_p==keep_e).mean()*100:.0f}% | Tỷ lệ đồng thuận khớp: {np.allclose(cons_p, cons_e)}")
print(f"Giữ {keep_e.sum()}/{K} tiêu chí; tiêu chí đạt đồng thuận >=75%: {(cons_e>=0.75).sum()}/{K}")
