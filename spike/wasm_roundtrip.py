"""Does a ballot encrypted by openfhe-wasm work with the Python side?

1. Python makes a committee, writes CryptoContext + public key to files.
2. Node (openfhe-wasm) encrypts a ballot from those files.
3. Python reads the ciphertext, runs the validity check, and decrypts with 2 of 3 holders.
"""
import json, os, subprocess, sys, time
import numpy as np
import openfhe
from openfhe import BINARY

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fdfhe
from fdfhe.sim import SimCommittee

K = 30
os.makedirs("out", exist_ok=True)
t = time.time()
com = SimCommittee(K)
cc = com.cc
print(f"committee setup {time.time() - t:.1f}s, ring dim {cc.GetRingDimension()}")
assert openfhe.SerializeToFile("out/cc.bin", cc, BINARY)
assert openfhe.SerializeToFile("out/pk.bin", com.public_key, BINARY)
print("cc.bin", os.path.getsize("out/cc.bin"), "bytes | pk.bin", os.path.getsize("out/pk.bin"), "bytes")

levels = list(np.random.default_rng(1).integers(0, 5, K))
r = subprocess.run(["node", os.path.join(os.path.dirname(__file__), "wasm_encrypt.js"),
                    "out/cc.bin", "out/pk.bin", ",".join(map(str, levels)), "out/ct.bin"],
                   capture_output=True, text=True)
print(r.stdout, r.stderr)
r.check_returncode()
print("wasm:", json.loads(r.stdout.strip().splitlines()[-1]))

res = openfhe.DeserializeCiphertext("out/ct.bin", BINARY)
ct = res[0] if isinstance(res, tuple) else res
dec = com.decrypt(ct, 5 * K)
assert np.array_equal(dec, fdfhe.encode(levels)), "decrypted ballot does not match"
print("decrypt matches: OK")

seed = fdfhe.board_seed([fdfhe.receipt(open("out/ct.bin", "rb").read())])
chk = fdfhe.validity_check(cc, K, ct, *fdfhe.validity_masks(seed, 0, K))
assert np.all(com.decrypt(chk, K) == 0), "valid wasm ballot rejected"
print("validity check on wasm ballot: OK")
