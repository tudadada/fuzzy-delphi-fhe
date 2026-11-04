"""Expert side: answers -> one-hot vector -> ciphertext. Runs on the expert's device."""
import numpy as np
from .params import LV
from .crypto import packed


def encode(levels) -> np.ndarray:
    """levels[k] in 0..4 for criterion k. Slot l*K + k is 1 when criterion k got level l."""
    levels = np.asarray(levels, dtype=np.int64)
    if levels.ndim != 1 or levels.size == 0:
        raise ValueError("levels must be a non-empty 1-D list")
    if levels.min() < 0 or levels.max() >= LV:
        raise ValueError(f"each level must be in 0..{LV - 1}")
    K = levels.size
    oh = np.zeros((LV, K), dtype=np.int64)
    oh[levels, np.arange(K)] = 1
    return oh.reshape(-1)


def encrypt_ballot(cc, public_key, levels):
    return cc.Encrypt(public_key, packed(cc, encode(levels)))
