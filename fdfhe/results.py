"""Plain arithmetic on decrypted aggregates. No secrets here."""
import numpy as np
from .params import CONSENSUS_DISTANCE, CONSENSUS_SHARE, KEEP_THRESHOLD


def summarize(S_dec, D2_dec, G: int):
    """S_dec: (3, K) decrypted sums. D2_dec: (G, K) decrypted squared distances (any order).

    Returns one dict per criterion with the fuzzy mean (0..1), defuzzified score,
    share of experts within the consensus distance, and the keep/consensus verdicts.
    """
    S_dec = np.asarray(S_dec, dtype=np.float64)
    D2_dec = np.asarray(D2_dec, dtype=np.float64)
    mean = S_dec / (4 * G)                                  # (3, K)
    score = mean.mean(0)                                    # (l + m + u) / 3
    dist = np.sqrt(np.clip(D2_dec, 0, None) / (3 * 16 * G * G))
    share = (dist <= CONSENSUS_DISTANCE + 1e-12).mean(0)
    out = []
    for k in range(S_dec.shape[1]):
        out.append({
            "criterion": k,
            "fuzzy_mean": [round(float(x), 4) for x in mean[:, k]],
            "score": round(float(score[k]), 4),
            "agree_share": round(float(share[k]), 4),
            "consensus": bool(share[k] >= CONSENSUS_SHARE),
            "keep": bool(score[k] >= KEEP_THRESHOLD),
        })
    return out
