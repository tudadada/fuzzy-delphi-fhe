"""Đối chứng: cùng bài toán Delphi mờ, dùng chia sẻ bí mật cộng (additive secret sharing) với 3 máy chủ.

Mỗi chuyên gia tách phiếu one-hot thành 3 mảnh ngẫu nhiên (cộng lại mod 2^32 ra phiếu thật),
gửi mỗi máy chủ một mảnh. Mỗi máy chủ cộng các mảnh nó nhận; ghép 3 tổng lại ra tổng thật.
Chỉ đo phần TRUNG BÌNH MỜ (phép cộng). Kiểm tra phiếu hợp lệ cần thêm giao thức kiểu Prio (SNIP),
và độ lệch (bình phương) cần phép nhân bảo mật (bộ ba Beaver) — KHÔNG cài đặt ở đây, chỉ ghi chú.
"""
import time, numpy as np
rng = np.random.default_rng(7)
TFN = np.array([(0,0,1),(0,1,2),(1,2,3),(2,3,4),(3,4,4)]); LV = 5; S = 3; MOD = 2**32

def run(E, K):
    votes = np.clip(rng.integers(1,6,K) + rng.integers(-1,2,(E,K)), 1, 5) - 1
    OH = np.zeros((E, LV, K), np.uint64); OH[np.arange(E)[:,None], votes, np.arange(K)[None,:]] = 1
    t0 = time.time()
    shares = []
    for i in range(E):
        r = rng.integers(0, MOD, (S-1, LV*K), dtype=np.uint64)
        last = (OH[i].reshape(-1) - r.sum(0)) % MOD
        shares.append(np.vstack([r, last]))                  # (S, LV*K)
    t_share = (time.time()-t0)/E
    upload = S * LV * K * 4 / 1024                            # 4 byte mỗi số, gửi tới 3 máy chủ
    t0 = time.time()
    server_sums = [sum(shares[i][s] for i in range(E)) % MOD for s in range(S)]
    total = (sum(server_sums) % MOD).reshape(LV, K).astype(int)
    M = np.stack([(TFN[:, j][:, None] * total).sum(0) for j in range(3)], 1) / (4*E)
    t_agg = time.time()-t0
    Mp = (TFN[votes]/4).mean(0)
    return dict(E=E, K=K, upload=upload, enc=t_share*1000, agg=t_agg*1000, exact=np.allclose(M, Mp))

if __name__ == "__main__":
    for E, K in [(20, 30), (50, 100), (50, 800)]:
        r = run(E, K)
        print(f"{E} × {K} | gửi/người {r['upload']:.1f} KB (tổng 3 máy chủ) | tách mảnh {r['enc']:.3f} ms | "
              f"gộp {r['agg']:.1f} ms | trung bình mờ {'chính xác' if r['exact'] else 'LỆCH'}")
