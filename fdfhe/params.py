"""Protocol constants. Changing any of these changes every hash and every result."""
import numpy as np

P = 786433            # BFV plaintext modulus (prime, NTT-friendly)
LV = 5                # linguistic levels per criterion
REPS = 5              # validity-check repetitions: cheat survives with prob <= (p-1)^-5 ~ 2^-97.9
MULT_DEPTH = 2

# Triangular fuzzy numbers on a 0..4 grid (divide by 4 for the 0..1 scale)
TFN = np.array([(0, 0, 1), (0, 1, 2), (1, 2, 3), (2, 3, 4), (3, 4, 4)])
LEVEL_NAMES = {
    "en": ["Very low", "Low", "Medium", "High", "Very high"],
    "vi": ["Rất thấp", "Thấp", "Trung bình", "Cao", "Rất cao"],
}

# Fuzzy Delphi decision rules (Chen 2000; Cheng and Lin 2002)
CONSENSUS_DISTANCE = 0.2
CONSENSUS_SHARE = 0.75
KEEP_THRESHOLD = 0.5

MASK_DOMAIN = b"encrypted-fuzzy-delphi/v0.4/validity-mask"
