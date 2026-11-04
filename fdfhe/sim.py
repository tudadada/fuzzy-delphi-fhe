"""Single-process committee (all key holders in one Python process).

FOR TESTS AND DEMOS ONLY: whoever runs this holds every secret key.
The real deployment runs each member's steps on their own machine (see ceremony.py).
"""
import numpy as np
from .params import P
from .crypto import make_context, rotation_indices


class SimCommittee:
    def __init__(self, K: int, n: int = 3, t: int = 2):
        self.n, self.t, self.K = n, t, K
        cc = self.cc = make_context()
        idx = rotation_indices(K)
        kps = [cc.KeyGen()]
        ek = cc.KeySwitchGen(kps[0].secretKey, kps[0].secretKey)
        cc.EvalAtIndexKeyGen(kps[0].secretKey, idx)
        rk = cc.GetEvalAutomorphismKeyMap(kps[0].secretKey.GetKeyTag())
        for _ in range(1, n):
            kp = cc.MultipartyKeyGen(kps[-1].publicKey)
            tag = kp.publicKey.GetKeyTag()
            ek = cc.MultiAddEvalKeys(ek, cc.MultiKeySwitchGen(kp.secretKey, kp.secretKey, ek), tag)
            rk = cc.MultiAddEvalAutomorphismKeys(
                rk, cc.MultiEvalAtIndexKeyGen(kp.secretKey, rk, idx, tag), tag)
            kps.append(kp)
        tag = kps[-1].publicKey.GetKeyTag()
        parts = [cc.MultiMultEvalKey(kp.secretKey, ek, tag) for kp in kps]
        fin = parts[0]
        for x in parts[1:]:
            fin = cc.MultiAddEvalMultKeys(fin, x, fin.GetKeyTag())
        cc.InsertEvalMultKey([fin])
        cc.InsertEvalAutomorphismKey(rk)
        self.kps, self.public_key = kps, kps[-1].publicKey
        self.held = {j: {} for j in range(1, n + 1)}       # held[j][i]: share of i's key held by j
        for i in range(1, n + 1):
            for j, s in cc.ShareKeys(kps[i - 1].secretKey, n, t, i, "shamir").items():
                self.held[j][i] = s

    def decrypt(self, ct, length: int, present=(1, 2)):
        present = list(present)
        if len(present) < self.t:
            raise PermissionError(f"need at least {self.t} key holders, got {len(present)}")
        cc = self.cc
        keys = {}
        for i in range(1, self.n + 1):
            if i in present:
                keys[i] = self.kps[i - 1].secretKey
            else:
                rec = cc.KeyGen().secretKey
                cc.RecoverSharedKey(rec, {j: self.held[j][i] for j in present[:self.t]},
                                    self.n, self.t, "shamir")
                keys[i] = rec
        shares = [cc.MultipartyDecryptLead([ct], keys[1])[0]] + \
                 [cc.MultipartyDecryptMain([ct], keys[i])[0] for i in range(2, self.n + 1)]
        pt = cc.MultipartyDecryptFusion(shares)
        pt.SetLength(length)
        v = np.array(pt.GetPackedValue(), dtype=np.int64)
        return np.where(v > P // 2, v - P, v)
