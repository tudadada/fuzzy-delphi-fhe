"""Batched validity: one ciphertext per repetition instead of one per ballot per repetition.

Key holders must partially decrypt (and upload ~640 KB for) every ciphertext they open.
Opening E * REPS validity checks is too heavy for 50+ experts, so we first open

    combined_r = sum_i w_{i,r} * check_{i,r}        for r = 0..REPS-1

with public weights w drawn from the locked board (separate domain from the masks).
The check is linear in its masks, so w * check(ct, r1, r2) = check(ct, w*r1, w*r2): the
weight is folded into the masks and costs no extra ciphertext multiplication or noise.

Honest checks decrypt to exactly 0, so combined_r is 0 unless some ballot is invalid.
For an invalid set, combined_r is 0 only if (a) every cheater's own masked check is 0
(prob <= 1/(p-1), as in v0.3) or (b) the weighted sum of the non-zero checks cancels
(prob <= 1/(p-1) over the weights). So a cheat survives one repetition with prob
<= 2/(p-1) and all REPS = 5 with prob <= (2/(p-1))^5 ~ 2^-92.9.

If any combined_r is non-zero, the server falls back to per-ballot checks, which
identify the invalid ballots exactly as in v0.4.

This is an application-level change to the v0.4 protocol; SECURITY.md must be updated
before any real use.
"""
from .params import REPS, P
from .masks import _uniform_nonzero, validity_masks
from .validity import validity_check

WEIGHT_DOMAIN = b"encrypted-fuzzy-delphi/v0.5/batch-weight"


def batch_weights(seed: bytes, E: int, rep: int):
    return _uniform_nonzero(WEIGHT_DOMAIN + seed + rep.to_bytes(1, "big"), E)


def combined_checks(cc, K, ballots, seed):
    """REPS ciphertexts; each decrypts to all zeros iff (w.h.p.) every ballot is valid."""
    E = len(ballots)
    out = []
    for r in range(REPS):
        w = batch_weights(seed, E, r)
        acc = None
        for i, ct in enumerate(ballots):
            r1, r2 = validity_masks(seed, i, K, r)
            term = validity_check(cc, K, ct, (r1 * int(w[i])) % P, (r2 * int(w[i])) % P)
            acc = term if acc is None else cc.EvalAdd(acc, term)
        out.append(acc)
    return out


def per_ballot_checks(cc, K, ballots, seed, reps=REPS):
    """checks[i][r]: the v0.4 validity ciphertext of ballot i, repetition r (fallback)."""
    return [[validity_check(cc, K, ct, *validity_masks(seed, i, K, r)) for r in range(reps)]
            for i, ct in enumerate(ballots)]
