"""Probe which OpenFHE-Python APIs exist for a multi-process ceremony."""
import openfhe, inspect
from openfhe import *
names = [n for n in dir(openfhe)]
for kw in ["Serialize", "Deserialize", "ShareKeys", "Recover", "EvalMultKey", "Automorphism", "SERJSON", "BINARY"]:
    print(kw, "->", [n for n in names if kw.lower() in n.lower()])
cc_methods = [n for n in dir(CryptoContext)]
for kw in ["Serialize", "Deserialize", "Share", "Recover", "Insert", "Clear", "Multi"]:
    print("cc." + kw, "->", [n for n in cc_methods if kw.lower() in n.lower()])
p = CCParamsBFVRNS(); p.SetPlaintextModulus(786433); p.SetMultiplicativeDepth(2)
p.SetMultipartyMode(MultipartyMode.NOISE_FLOODING_MULTIPARTY)
cc = GenCryptoContext(p)
for f in (PKESchemeFeature.PKE, PKESchemeFeature.KEYSWITCH, PKESchemeFeature.LEVELEDSHE,
          PKESchemeFeature.ADVANCEDSHE, PKESchemeFeature.MULTIPARTY): cc.Enable(f)
kp = cc.KeyGen()
sh = cc.ShareKeys(kp.secretKey, 3, 2, 1, "shamir")
print("ShareKeys type:", type(sh), {k: type(v) for k, v in sh.items()})
v = next(iter(sh.values()))
print("share attrs:", [a for a in dir(v) if not a.startswith("__")])
for obj, name in [(cc, "cc"), (kp.publicKey, "pk"), (kp.secretKey, "sk")]:
    for fmt in (BINARY, JSON):
        try:
            s = Serialize(obj, fmt); print(name, fmt, "ok", len(s))
        except Exception as e: print(name, fmt, "FAIL", e)
try:
    s = Serialize(v, BINARY); print("share serialize ok", len(s))
except Exception as e: print("share serialize FAIL", repr(e))
print("version:", getattr(openfhe, "__version__", "?"))
