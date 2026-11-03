"""Kiểm chứng Định lý 1 (SECURITY.md) bằng mô phỏng bản rõ với số nguyên tố nhỏ.
Phiếu gian lọt qua bước kiểm R lần với xác suất <= 1/(p-1)^R."""
import numpy as np
rng = np.random.default_rng(0); L, K, N = 5, 4, 400_000
for p, reps in [(101, 1), (101, 2), (13, 3)]:
    passed = trials = 0
    for _ in range(N):
        x = np.zeros((L, K), np.int64); x[rng.integers(L), :] = 1
        k = rng.integers(K); x[:, k] = rng.integers(0, p, L)
        s = (x.sum(0) - 1) % p; q = (x * (x - 1)) % p
        if not (s.any() or q.any()): continue
        trials += 1; ok = True
        for _r in range(reps):
            r1 = rng.integers(1, p, K); r2 = rng.integers(1, p, (L, K))
            if ((r1 * s + (r2 * q).sum(0)) % p).any(): ok = False; break
        passed += ok
    print(f"p={p}, R={reps}: measured {passed/trials:.2e} | bound 1/(p-1)^R = {1/(p-1)**reps:.2e}")
