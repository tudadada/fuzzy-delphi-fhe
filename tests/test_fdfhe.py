"""End-to-end round with the fdfhe library (single-process committee).

Checks: exact fuzzy means and distances vs plaintext, cheating ballots rejected,
honest ballots accepted, auditor recomputation matches, 1 key holder cannot decrypt.
"""
import numpy as np
import pytest
from openfhe import Serialize, BINARY

import fdfhe
from fdfhe.params import TFN, LV, REPS
from fdfhe.sim import SimCommittee

E, K = 8, 6
rng = np.random.default_rng(3)


@pytest.fixture(scope="module")
def round_data():
    com = SimCommittee(K)
    cc = com.cc
    votes = rng.integers(0, LV, (E, K))
    cts = [fdfhe.encrypt_ballot(cc, com.public_key, v) for v in votes]
    # two cheaters: a weight-50 slot, and two levels for one criterion
    bad1 = fdfhe.ballot.encode(votes[0]); bad1[4 * K + 1] = 50
    bad2 = fdfhe.ballot.encode(votes[1]); bad2[0 * K + 2] = 1; bad2[4 * K + 2] = 1
    cts[0] = cc.Encrypt(com.public_key, fdfhe.packed(cc, bad1))
    cts[1] = cc.Encrypt(com.public_key, fdfhe.packed(cc, bad2))
    receipts = [fdfhe.receipt(Serialize(c, BINARY)) for c in cts]
    return com, cc, votes, cts, receipts


def _check_hashes_and_validity(com, cc, cts, receipts):
    seed = fdfhe.board_seed(receipts)
    hashes, valid = [], []
    for i, ct in enumerate(cts):
        ok, hs = True, []
        for rep in range(REPS):
            chk = fdfhe.validity_check(cc, K, ct, *fdfhe.validity_masks(seed, i, K, rep))
            hs.append(fdfhe.receipt(Serialize(chk, BINARY)))
            ok &= bool(np.all(com.decrypt(chk, K) == 0))
        hashes.append(hs); valid.append(ok)
    return hashes, valid


def test_validity_and_audit(round_data):
    com, cc, votes, cts, receipts = round_data
    hashes, valid = _check_hashes_and_validity(com, cc, cts, receipts)
    assert valid[:2] == [False, False]
    assert all(valid[2:])
    seed = fdfhe.board_seed(receipts)
    again = [[fdfhe.receipt(Serialize(fdfhe.validity_check(cc, K, ct, *fdfhe.validity_masks(seed, i, K, r)), BINARY))
              for r in range(REPS)] for i, ct in enumerate(cts)]
    assert again == hashes


def test_aggregate_exact(round_data):
    com, cc, votes, cts, receipts = round_data
    good = list(range(2, E))
    S, D2 = fdfhe.aggregate(cc, K, [cts[i] for i in good])
    S_dec = np.stack([com.decrypt(s, K) for s in S])
    D2_dec = np.stack([com.decrypt(d, K, present=(2, 3)) for d in D2])
    res = fdfhe.summarize(S_dec, D2_dec, len(good))
    Tp = TFN[votes[good]] / 4
    Mp = Tp.mean(0)                                          # (K, 3)
    dp = np.sqrt(((Tp - Mp) ** 2).mean(2))                   # (G, K)
    for k, r in enumerate(res):
        assert np.allclose(r["fuzzy_mean"], Mp[k], atol=1e-4)
        assert abs(r["score"] - Mp[k].mean()) < 1e-4
        assert abs(r["agree_share"] - (dp[:, k] <= 0.2 + 1e-12).mean()) < 1e-4


def test_batched_validity(round_data):
    from fdfhe.batch import combined_checks
    com, cc, votes, cts, receipts = round_data
    seed = fdfhe.board_seed(receipts)
    # with the two cheaters: every repetition must be non-zero
    bad = [com.decrypt(c, K) for c in combined_checks(cc, K, cts, seed)]
    assert all(np.any(v != 0) for v in bad)
    # honest ballots only: every repetition decrypts to exactly zero
    honest = cts[2:]
    seed_h = fdfhe.board_seed(receipts[2:])
    ok = [com.decrypt(c, K) for c in combined_checks(cc, K, honest, seed_h)]
    assert all(np.all(v == 0) for v in ok)


def test_single_holder_blocked(round_data):
    com, cc, votes, cts, receipts = round_data
    with pytest.raises(PermissionError):
        com.decrypt(cts[2], K, present=(1,))


def test_encode_rejects_bad_levels():
    with pytest.raises(ValueError):
        fdfhe.encode([0, 5])
    with pytest.raises(ValueError):
        fdfhe.encode([])
