"""fdfhe: Encrypted Fuzzy Delphi as a reusable library.

Same protocol as delphi/09_hardened.py (v0.4), split into the pieces each role needs:
  ballot      expert: turn answers into a one-hot vector and encrypt it
  validity    server/auditor: publicly verifiable ballot check (Fiat-Shamir masks)
  aggregate   server/auditor: homomorphic fuzzy mean and squared distances
  results     committee/anyone: turn decrypted sums into scores and consensus
  sim         single-process committee, for tests and demos only
"""
from .params import P, LV, TFN, REPS, LEVEL_NAMES
from .masks import board_seed, receipt, validity_masks
from .crypto import make_context, packed
from .ballot import encode, encrypt_ballot
from .validity import validity_check
from .aggregate import aggregate
from .results import summarize

__version__ = "0.5.0.dev0"
