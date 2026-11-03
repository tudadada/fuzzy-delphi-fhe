"""Delphi mờ mã hóa — bản tối ưu: số nguyên (BFV), tách a/b/c thành 3 bản mã, không cần khóa xoay.
Thang ngôn ngữ 5 mức = bội số của 0.25 -> nhân 4 thành số nguyên 0..4. Tính chính xác tuyệt đối.
"""
import time, numpy as np, tenseal as ts
rng = np.random.default_rng(1)
SCALE = {1:(0,0,1), 2:(0,1,2), 3:(1,2,3), 4:(2,3,4), 5:(3,4,4)}  # đơn vị 0.25
P = 786433  # plain modulus (số nguyên tố, hỗ trợ đóng gói)

def run(E, K, N):
    true_q = rng.integers(1, 6, K)
    votes = np.clip(true_q + rng.integers(-1, 2, (E, K)), 1, 5)
    T = np.array([[SCALE[v] for v in row] for row in votes])        # (E,K,3) số nguyên
    # đối chứng bản rõ (đơn vị thật)
    M = T.mean(0)/4; d = np.sqrt((((T/4) - M)**2).mean(2)); df = M.mean(1)
    ctx = ts.context(ts.SCHEME_TYPE.BFV, N, plain_modulus=P)          # có sẵn relin key, không galois
    t0 = time.time()
    cts = [[ts.bfv_vector(ctx, T[i,:,j].tolist()) for j in range(3)] for i in range(E)]
    t_enc = (time.time()-t0)/E
    up_kb = sum(len(c.serialize()) for c in cts[0])/1024
    pub = ctx.copy(); pub.make_context_public()
    key_kb = len(pub.serialize(save_galois_keys=False, save_relin_keys=True))/1024
    t0 = time.time()
    S = [cts[0][j].copy() for j in range(3)]
    for i in range(1, E):
        for j in range(3): S[j] += cts[i][j]
    S_def = S[0] + S[1] + S[2]                                         # tổng để giải mờ
    D2 = []
    for i in range(E):                                                 # E*x_i - S, bình phương, cộng 3 thành phần
        acc = None
        for j in range(3):
            diff = cts[i][j] * E - S[j]; sq = diff * diff
            acc = sq if acc is None else acc + sq
        D2.append(acc)
    t_srv = time.time()-t0
    dec = lambda v: np.array([x-P if x > P//2 else x for x in v.decrypt()])
    Me = np.stack([dec(S[j]) for j in range(3)], 1)/(4*E)
    dfe = dec(S_def)/(12*E)
    de = np.sqrt(np.array([dec(v) for v in D2])/(3*16*E*E))
    ok = np.allclose(Me, M) and np.allclose(dfe, df) and np.allclose(de, d)
    keep = (dfe >= 0.5) == (df >= 0.5); cons = np.allclose((de<=0.2).mean(0), (d<=0.2).mean(0))
    return dict(E=E, K=K, N=N, up=up_kb, key=key_kb, enc=t_enc*1000, srv=t_srv*1000,
                exact=ok, keep=keep.mean(), cons=cons)

print(f"{'Chuyên gia':>10} {'Tiêu chí':>8} {'N':>6} {'Gửi/người KB':>12} {'Khóa MB':>8} {'Mã hóa ms':>9} {'Máy chủ ms':>10} {'Chính xác':>9}")
for E, K, N in [(15, 20, 4096), (15, 20, 8192), (50, 100, 4096), (200, 500, 4096)]:
    r = run(E, K, N)
    print(f"{r['E']:10d} {r['K']:8d} {r['N']:6d} {r['up']:12.0f} {r['key']/1024:8.2f} {r['enc']:9.1f} {r['srv']:10.0f} "
          f"{'100%' if r['exact'] and r['keep']==1 and r['cons'] else 'LỆCH':>9}")
