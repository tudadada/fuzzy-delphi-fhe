"""Deterministic public aggregation. Anyone can rerun it on the published ciphertexts.

Returns
  S   3 ciphertexts: slot k = sum over experts of the (l, m, u) component, 0..4 grid
  D2  one ciphertext per expert: slot k = sum_j (G*A_ij - S_j)^2
"""
import numpy as np
from .params import TFN
from .crypto import packed, level_sum


def aggregate(cc, K: int, ballots):
    if not ballots:
        raise ValueError("no valid ballots to aggregate")
    W = [packed(cc, np.repeat(TFN[:, j], K)) for j in range(3)]
    A = [[level_sum(cc, cc.EvalMult(ct, W[j]), K) for j in range(3)] for ct in ballots]
    S = list(A[0])
    for a in A[1:]:
        S = [cc.EvalAdd(S[j], a[j]) for j in range(3)]
    G = packed(cc, [len(ballots)] * cc.GetRingDimension())
    D2 = []
    for a in A:
        acc = None
        for j in range(3):
            d = cc.EvalSub(cc.EvalMult(a[j], G), S[j])
            sq = cc.EvalMult(d, d)
            acc = sq if acc is None else cc.EvalAdd(acc, sq)
        D2.append(acc)
    return S, D2
