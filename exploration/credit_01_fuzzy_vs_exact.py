"""So sánh FHE: mô hình chính xác (CKKS) vs luật mờ 8 mức (BFV) trên German Credit."""
import time, numpy as np, pandas as pd, tenseal as ts
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

FEATS = ["status","duration","credit_history","amount","savings","employment_duration",
         "installment_rate","age","property","number_credits"]
df = pd.read_csv(__import__("os").path.join(__import__("os").path.dirname(__file__), "german.data"))
for c in FEATS:
    if not pd.api.types.is_numeric_dtype(df[c]): df[c] = pd.factorize(df[c], sort=True)[0]
X = df[FEATS].values.astype(float)
y = pd.factorize(df["credit_risk"], sort=True)[0] if not pd.api.types.is_numeric_dtype(df["credit_risk"]) else df["credit_risk"].values
print("Nhãn:", dict(zip(*np.unique(y, return_counts=True))))
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
mu, sd = Xtr.mean(0), Xtr.std(0)
Ztr, Zte = (Xtr-mu)/sd, (Xte-mu)/sd
NEVAL = 40  # số mẫu chạy mã hóa thật

def sz(b): return len(b)/1024  # KB

def ctx_sizes(ctx):
    full = sz(ctx.serialize(save_public_key=True, save_secret_key=False,
                            save_galois_keys=True, save_relin_keys=True))
    return full

res = {}

# ---------- A. CKKS chính xác + sigmoid đa thức (xuất xác suất) ----------
lr = LogisticRegression(max_iter=1000).fit(Ztr, ytr)
w, b = lr.coef_[0], lr.intercept_[0]
acc_plain = accuracy_score(yte, lr.predict(Zte))
def run_ckks(N, coeffs, sigmoid):
    ctx = ts.context(ts.SCHEME_TYPE.CKKS, N, coeff_mod_bit_sizes=coeffs)
    ctx.global_scale = 2**40; ctx.generate_galois_keys()
    preds, ts_, csz = [], [], None
    for z in Zte[:NEVAL]:
        enc = ts.ckks_vector(ctx, z.tolist())
        csz = sz(enc.serialize())
        t = time.time()
        s = enc.dot(w.tolist()) + b
        if sigmoid:  # xấp xỉ sigmoid bậc 3 quanh [-5,5]
            s = s.polyval([0.5, 0.197, 0, -0.004])
        ts_.append(time.time()-t)
        v = s.decrypt()[0]
        preds.append(int(v > (0.5 if sigmoid else 0)))
    return dict(N=N, ct_KB=csz, key_KB=ctx_sizes(ctx), ms=1000*np.mean(ts_),
                acc=accuracy_score(yte[:NEVAL], preds))
res["A. CKKS chính xác + sigmoid"] = run_ckks(16384, [60,40,40,40,60], True)
res["B. CKKS chính xác tối giản"] = run_ckks(8192, [60,40,60], False)

# ---------- C. Luật mờ 8 mức trên BFV ----------
L = 8
edges = [np.quantile(Xtr[:,j], np.linspace(0,1,L+1)[1:-1]) for j in range(len(FEATS))]
def levels(Xm): return np.stack([np.digitize(Xm[:,j], edges[j]) for j in range(len(FEATS))],1)
Ltr, Lte = levels(Xtr), levels(Xte)
def onehot(Lm):
    o = np.zeros((len(Lm), len(FEATS)*L));
    for j in range(len(FEATS)): o[np.arange(len(Lm)), j*L+Lm[:,j]] = 1
    return o
# học bảng luật: mỗi (đặc trưng, mức) một trọng số, rồi làm tròn về số nguyên nhỏ
fz = LogisticRegression(max_iter=2000, C=0.5).fit(onehot(Ltr), ytr)
scale = 7/np.abs(fz.coef_[0]).max()
Wq = np.round(fz.coef_[0]*scale).astype(int); bq = int(round(fz.intercept_[0]*scale))
acc_fuzzy_plain = accuracy_score(yte, (onehot(Lte)@Wq + bq > 0).astype(int))
def run_bfv(N, pmod):
    ctx = ts.context(ts.SCHEME_TYPE.BFV, N, plain_modulus=pmod)
    ctx.generate_galois_keys()
    preds, ts_, csz = [], [], None
    for oh in onehot(Lte[:NEVAL]).astype(int):
        enc = ts.bfv_vector(ctx, oh.tolist()); csz = sz(enc.serialize())
        t = time.time(); s = enc.dot(Wq.tolist()); ts_.append(time.time()-t)
        v = s.decrypt()[0]; v = v - pmod if v > pmod//2 else v
        preds.append(int(v + bq > 0))
    return dict(N=N, ct_KB=csz, key_KB=ctx_sizes(ctx), ms=1000*np.mean(ts_),
                acc=accuracy_score(yte[:NEVAL], preds))
res["C. Luật mờ 8 mức (BFV)"] = run_bfv(4096, 1032193)

print(f"Độ chính xác bản rõ: logistic={acc_plain:.3f} | luật mờ={acc_fuzzy_plain:.3f} (300 mẫu test)")
print(f"{'Cấu hình':32s} {'N':>6} {'Bản mã KB':>10} {'Khóa KB':>10} {'ms/mẫu':>8} {'Acc(40)':>8}")
for k,r in res.items():
    print(f"{k:32s} {r['N']:6d} {r['ct_KB']:10.1f} {r['key_KB']:10.0f} {r['ms']:8.1f} {r['acc']:8.3f}")
