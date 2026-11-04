"""Publicly verifiable ballot check (v0.3+ fix: mask every slot before summing).

check = r1 * (sum_l x_lk - 1) + sum_l r2_lk * x_lk (x_lk - 1)
A valid one-hot ballot decrypts to all zeros. Masks come from the locked board,
so anyone can recompute this ciphertext and compare hashes.
"""
from .params import LV
from .crypto import packed, level_sum


def validity_check(cc, K: int, ct, r1, r2):
    s = cc.EvalSub(level_sum(cc, ct, K), packed(cc, [1] * K))
    q = cc.EvalMult(ct, cc.EvalSub(ct, packed(cc, [1] * (LV * K))))
    return cc.EvalAdd(cc.EvalMult(s, packed(cc, r1)),
                      level_sum(cc, cc.EvalMult(q, packed(cc, r2)), K))
