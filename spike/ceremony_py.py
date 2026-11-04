"""Full round with a key ceremony done in openfhe-wasm (3 separate 'machines').

  python: write cc.bin
  node:   3 members make keys in a chain; anyone combines the public eval keys
  python: experts encrypt, server checks validity and aggregates (no secret keys here)
  node:   2 of the 3 members make partial decryptions
  python: fuse partials, compare with the plaintext answer
"""
import json, os, subprocess, sys, time
import numpy as np
import openfhe
from openfhe import BINARY

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fdfhe
from fdfhe.params import TFN, LV, P

D = "out_ceremony"; E, K = 6, 10
NODE = os.path.join(os.path.dirname(__file__), "ceremony_node.js")
os.makedirs(D, exist_ok=True)
J = lambda *p: os.path.join(D, *p)


def node(*args):
    r = subprocess.run(["node", NODE, *args], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-2000:])
    r.check_returncode()
    return json.loads(r.stdout.strip().splitlines()[-1])


def load(fn, path):
    res = fn(path, BINARY)
    return res[0] if isinstance(res, tuple) else res


cc = fdfhe.make_context()
assert openfhe.SerializeToFile(J("cc.bin"), cc, BINARY)

print("keygen:", node("keygen", D, str(K)))

cc = load(openfhe.DeserializeCryptoContext, J("cc.bin"))
pk = load(openfhe.DeserializePublicKey, J("pk.bin"))
assert cc.DeserializeEvalMultKey(J("evalmult.bin"), BINARY), "eval mult key load failed"
assert cc.DeserializeEvalAutomorphismKey(J("evalrot.bin"), BINARY), "rotation key load failed"

rng = np.random.default_rng(5)
votes = rng.integers(0, LV, (E, K))
cts = [fdfhe.encrypt_ballot(cc, pk, v) for v in votes]
bad = fdfhe.encode(votes[0]); bad[4 * K + 1] = 50                       # one cheater
cts[0] = cc.Encrypt(pk, fdfhe.packed(cc, bad))
receipts = [fdfhe.receipt(openfhe.Serialize(c, BINARY)) for c in cts]
seed = fdfhe.board_seed(receipts)

t = time.time()
checks = [fdfhe.validity_check(cc, K, c, *fdfhe.validity_masks(seed, i, K, 0)) for i, c in enumerate(cts)]
good = list(range(1, E))                                                 # what validity should find
S, D2 = fdfhe.aggregate(cc, K, [cts[i] for i in good])
print(f"server compute {time.time() - t:.2f}s")

to_dec = checks + S + D2
names = []
for i, c in enumerate(to_dec):
    assert openfhe.SerializeToFile(J(f"dec_{i}.bin"), c, BINARY)
    names.append(f"dec_{i}.bin")
json.dump(names, open(J("to_decrypt.json"), "w"))

print("partial:", node("partial", D, "1,3,2"))                            # member 1 leads

vals = []
for i in range(len(to_dec)):
    parts = [load(openfhe.DeserializeCiphertext, J(f"part_{m}_{i}.bin")) for m in (1, 3, 2)]
    pt = cc.MultipartyDecryptFusion(parts)
    pt.SetLength(5 * K)
    v = np.array(pt.GetPackedValue(), dtype=np.int64)
    vals.append(np.where(v > P // 2, v - P, v))

valid = [bool(np.all(vals[i][:K] == 0)) for i in range(E)]
assert valid == [False] + [True] * (E - 1), f"validity wrong: {valid}"
print("validity from wasm-made keys: OK", valid)

S_dec = np.stack([vals[E + j][:K] for j in range(3)])
D2_dec = np.stack([vals[E + 3 + g][:K] for g in range(len(good))])
res = fdfhe.summarize(S_dec, D2_dec, len(good))
Tp = TFN[votes[good]] / 4; Mp = Tp.mean(0); dp = np.sqrt(((Tp - Mp) ** 2).mean(2))
for k, r in enumerate(res):
    assert np.allclose(r["fuzzy_mean"], Mp[k], atol=1e-4), (k, r, Mp[k])
    assert abs(r["agree_share"] - (dp[:, k] <= 0.2 + 1e-12).mean()) < 1e-4
print("aggregate exact with wasm-made keys: OK")
print("sizes (KB):", {f: os.path.getsize(J(f)) // 1024 for f in ["pk.bin", "evalmult.bin", "evalrot.bin", "sk1.bin", "dec_0.bin", "part_1_0.bin"]})
