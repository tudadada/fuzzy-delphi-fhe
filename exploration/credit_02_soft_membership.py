"""Chia mức cứng (one-hot) vs độ thuộc mờ tam giác — cùng chi phí FHE."""
import time, numpy as np, pandas as pd, tenseal as ts
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, accuracy_score

FEATS = ["status","duration","credit_history","amount","savings","employment_duration",
         "installment_rate","age","property","number_credits"]
df = pd.read_csv(__import__("os").path.join(__import__("os").path.dirname(__file__), "german.data"))
for c in FEATS:
    if not pd.api.types.is_numeric_dtype(df[c]): df[c] = pd.factorize(df[c], sort=True)[0]
y = pd.factorize(df["credit_risk"], sort=True)[0]
X = df[FEATS].values.astype(float)

def centers(Xtr, L):
    return [np.unique(np.quantile(Xtr[:,j], np.linspace(0,1,L))) for j in range(X.shape[1])]

def encode(Xm, C, fuzzy, Q=16):
    cols = []
    for j, c in enumerate(C):
        M = np.zeros((len(Xm), len(c)))
        x = np.clip(Xm[:,j], c[0], c[-1])
        k = np.clip(np.searchsorted(c, x, side="right")-1, 0, len(c)-1)
        if not fuzzy or len(c) == 1:
            k = np.abs(x[:,None]-c[None,:]).argmin(1); M[np.arange(len(x)), k] = 1
        else:
            k = np.minimum(k, len(c)-2)
            t = (x - c[k]) / (c[k+1]-c[k])            # độ thuộc tam giác
            M[np.arange(len(x)), k] = 1-t; M[np.arange(len(x)), k+1] = t
            M = np.round(M*Q)/Q                         # lượng tử hóa độ thuộc (4 bit)
        cols.append(M)
    return np.hstack(cols)

def cv(L, fuzzy, seeds=range(5)):
    aucs, accs = [], []
    for s in seeds:
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=s).split(X, y):
            C = centers(X[tr], L)
            m = LogisticRegression(max_iter=3000, C=0.5).fit(encode(X[tr],C,fuzzy), y[tr])
            p = m.predict_proba(encode(X[te],C,fuzzy))[:,1]
            aucs.append(roc_auc_score(y[te], p)); accs.append(accuracy_score(y[te], p>0.5))
    return np.mean(aucs), np.std(aucs), np.mean(accs)

print(f"{'Số mức':>6} {'Cách':>10} {'AUC':>14} {'Acc':>6}")
for L in [4, 6, 8]:
    for fz in [False, True]:
        a, sd, acc = cv(L, fz)
        print(f"{L:6d} {'mờ' if fz else 'cứng':>10} {a:8.4f} ±{sd:.3f} {acc:6.3f}")

# Kiểm chứng chi phí FHE thật: cùng N, cùng số ô
C = centers(X, 8)
for fz in [False, True]:
    E = encode(X[:20], C, fz)
    ctx = ts.context(ts.SCHEME_TYPE.BFV, 4096, plain_modulus=1032193); ctx.generate_galois_keys()
    W = np.random.randint(-7, 8, E.shape[1]).tolist()
    t = time.time(); sizes = []
    for row in E:
        enc = ts.bfv_vector(ctx, (row*16).astype(int).tolist()); sizes.append(len(enc.serialize()))
        enc.dot(W).decrypt()
    print(f"FHE {'mờ' if fz else 'cứng'}: {E.shape[1]} ô, bản mã {np.mean(sizes)/1024:.1f} KB, {(time.time()-t)/20*1000:.1f} ms/hồ sơ")
