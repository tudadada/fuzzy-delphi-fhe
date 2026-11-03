"""Đo hiệu quả xếp nhiều hồ sơ vào một bản mã (đóng gói theo cột) — luật mờ 8 mức, BFV."""
import time, numpy as np, pandas as pd, tenseal as ts
from sklearn.linear_model import LogisticRegression

FEATS = ["status","duration","credit_history","amount","savings","employment_duration",
         "installment_rate","age","property","number_credits"]
df = pd.read_csv(__import__("os").path.join(__import__("os").path.dirname(__file__), "german.data"))
for c in FEATS:
    if not pd.api.types.is_numeric_dtype(df[c]): df[c] = pd.factorize(df[c], sort=True)[0]
y = pd.factorize(df["credit_risk"], sort=True)[0]; X = df[FEATS].values.astype(float)
L = 8
edges = [np.quantile(X[:,j], np.linspace(0,1,L+1)[1:-1]) for j in range(len(FEATS))]
Lv = np.stack([np.digitize(X[:,j], edges[j]) for j in range(len(FEATS))],1)
OH = np.zeros((len(X), len(FEATS)*L), int)
for j in range(len(FEATS)): OH[np.arange(len(X)), j*L+Lv[:,j]] = 1
m = LogisticRegression(max_iter=2000, C=0.5).fit(OH, y)
s = 7/np.abs(m.coef_[0]).max(); W = np.round(m.coef_[0]*s).astype(int); B = int(round(m.intercept_[0]*s))
ref = (OH@W + B > 0).astype(int)
P = 1032193
KB = lambda b: len(b)/1024

def keysize(ctx):
    return KB(ctx.serialize(save_public_key=True, save_secret_key=False,
                            save_galois_keys=ctx.has_galois_keys(), save_relin_keys=True))

def decode(v): return np.array([x-P if x > P//2 else x for x in v])

out = []
# 1) Cách cũ: mỗi hồ sơ một bản mã, cần khóa xoay để cộng
ctx = ts.context(ts.SCHEME_TYPE.BFV, 4096, plain_modulus=P); ctx.generate_galois_keys()
n1 = 100; t = time.time(); sz = 0; ok = 0
for i in range(n1):
    e = ts.bfv_vector(ctx, OH[i].tolist()); sz += KB(e.serialize())
    ok += int(decode(e.dot(W.tolist()).decrypt())[0] + B > 0) == ref[i]
out.append(("1. Mỗi hồ sơ 1 bản mã (cũ)", sz/n1, keysize(ctx), (time.time()-t)/n1*1000, ok/n1))

# 2) Đóng gói theo cột: mỗi bản mã chứa 1 cột cho 4096 hồ sơ, không cần khóa xoay
for N, pm in [(4096, P), (8192, P)]:
    ctx = ts.context(ts.SCHEME_TYPE.BFV, N, plain_modulus=pm)
    R = N  # số hồ sơ mỗi lô
    Xb = OH[np.arange(R) % len(OH)]; rb = ref[np.arange(R) % len(OH)]
    t = time.time()
    cols = [ts.bfv_vector(ctx, Xb[:,k].tolist()) for k in range(OH.shape[1])]
    sz = sum(KB(c.serialize()) for c in cols)
    acc = None
    for k in range(len(cols)):
        if W[k]:
            term = cols[k] * int(W[k]); acc = term if acc is None else acc + term
    res = decode(acc.decrypt()); ok = np.mean((res + B > 0).astype(int) == rb)
    out.append((f"2. Đóng gói cột, N={N}", sz/R, keysize(ctx), (time.time()-t)/R*1000, ok))

print(f"{'Cách làm':30s} {'KB/hồ sơ':>10} {'Khóa KB':>9} {'ms/hồ sơ':>9} {'Khớp':>6}")
for r in out: print(f"{r[0]:30s} {r[1]:10.2f} {r[2]:9.0f} {r[3]:9.3f} {r[4]:6.3f}")
