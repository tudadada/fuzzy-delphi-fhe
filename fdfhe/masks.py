"""Public validity masks, derived from the locked bulletin board (Fiat-Shamir).

Identical to v0.4: SHAKE-256 with domain separation and rejection sampling,
uniform on [1, p-1]. Anyone can recompute them from the board.
"""
import hashlib
import numpy as np
from .params import P, LV, MASK_DOMAIN


def receipt(ct_bytes: bytes) -> str:
    """Receipt an expert keeps: SHA-256 of their serialized ciphertext."""
    return hashlib.sha256(ct_bytes).hexdigest()


def board_seed(receipts) -> bytes:
    """Seed from the locked board. Order matters: use the board's published order."""
    return hashlib.sha256("".join(receipts).encode()).digest()


def _uniform_nonzero(xof_input: bytes, count: int):
    n_bytes = 3 * count * 2
    while True:
        stream = hashlib.shake_256(xof_input).digest(n_bytes)
        vals = []
        for j in range(0, len(stream) - 2, 3):
            v = int.from_bytes(stream[j:j + 3], "big") & 0xFFFFF
            if v < P - 1:
                vals.append(v + 1)
                if len(vals) == count:
                    return np.array(vals, dtype=np.int64)
        n_bytes *= 2


def validity_masks(seed: bytes, i: int, K: int, rep: int = 0):
    """(r1, r2) for ballot i, repetition rep. r1 has K entries, r2 has LV*K."""
    base = MASK_DOMAIN + seed + i.to_bytes(4, "big") + rep.to_bytes(1, "big")
    return _uniform_nonzero(base + b"/r1", K), _uniform_nonzero(base + b"/r2", LV * K)
