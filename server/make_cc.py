"""Write web/fhe/cc.bin: the CryptoContext every role loads (parameters only, no keys)."""
import os, sys
import openfhe
from openfhe import BINARY

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fdfhe

out = os.path.join(os.path.dirname(__file__), "..", "web", "fhe", "cc.bin")
os.makedirs(os.path.dirname(out), exist_ok=True)
assert openfhe.SerializeToFile(out, fdfhe.make_context(), BINARY)
print(out, os.path.getsize(out), "bytes")
