# Encrypted Fuzzy Delphi

Expert consensus with **triangular fuzzy numbers** using the **fuzzy Delphi method**, where **nobody can read an individual expert's ballot** — not the server, not the organiser. Only the aggregate result is decrypted, and only when **the whole committee** agrees. Cheating ballots are detected and discarded without revealing their content.

> **Status:** proof of concept. Simulated data, not yet reviewed by cryptographers, not yet tested with a real panel. Feedback and vulnerability reports are very welcome.

🇻🇳 [Bản tiếng Việt](README.vi.md)

---

## The problem

When experts are consulted (planning, healthcare, competition judging, project evaluation), participants often **follow the majority or their superiors**, or hold back for fear of being identified. Conventional "anonymous" ballots can still be read by whoever compiles them.

The **fuzzy Delphi method** lets experts answer on a linguistic scale (very low → very high), each level mapped to a **triangular fuzzy number** (a, b, c). Its core computations — fuzzy mean, centroid defuzzification, consensus distance — use only **addition, multiplication by constants and squaring**. These are exactly the operations that **fully homomorphic encryption (FHE)** handles most cheaply.

## What the system does

| Role | Task |
|---|---|
| **Expert** | Marks one of 5 levels per criterion. The ballot is **encrypted on their own device** before it is sent. |
| **Server** | Receives ciphertexts only. Validates ballots, maps them to fuzzy numbers, computes fuzzy means, defuzzified scores and per-expert distances — **entirely on ciphertexts**. |
| **Committee (3 members)** | Each holds one key share. **All 3 are required** to decrypt the result. A single member decrypting alone obtains meaningless data. |

**Ballot validation:** experts submit a one-hot "pick 1 of 5" ballot (0/1). On the ciphertext, the server checks (1) the levels sum to 1 and (2) each entry satisfies x(x−1) = 0. The check is multiplied by random values: a valid ballot decrypts to 0, an invalid one to random noise — the committee learns which ballot is invalid but not what it contains. Since the server maps levels to fuzzy numbers itself, a ≤ b ≤ c is guaranteed by construction.

Fuzzy Delphi rules follow Chen (2000) and Cheng & Lin (2002): consensus when distance d ≤ 0.2 for ≥ 75% of experts; a criterion is kept when its defuzzified score ≥ 0.5.

## Measured results (final version: `delphi/04_packed_final.py`)

OpenFHE, BFV, multiplicative depth 2, N = 8192, 3-party threshold decryption. A standard cloud machine, no GPU.

| Experts × Criteria | Upload per expert | Encryption | Validation | Aggregation | Cheaters caught | Matches plaintext |
|---|---|---|---|---|---|---|
| 15 × 20 | 385 KB | 6.5 ms | 0.6 s | 0.9 s | 2/2 | 100% |
| 50 × 100 | 385 KB | 6.4 ms | 2.1 s | 3.3 s | 2/2 | 100% |
| 50 × 800 | 385 KB | 9.7 ms | 2.4 s | 3.1 s | 2/2 | 100% |

- Repeated with 3 different datasets: 3/3 passed. No false positives when there are no cheaters.
- Two cheating strategies tested: stuffing 50 votes into one level; selecting two levels at once.
- Results are **exact** (integer arithmetic), not approximate.

### Optimisation path

| Version | Approach | Upload per expert | Evaluation keys | Notes |
|---|---|---|---|---|
| `01_ckks_baseline.py` | CKKS reals, rotation keys | 836 KB | ~117 MB | approximate, server ~10 s |
| `02_bfv_integer.py` | BFV integers, split a/b/c, no rotation keys | 259 KB | ~0.4 MB | exact; no threshold, no validation |
| `03_threshold_anticheat.py` | + threshold decryption + ballot validation | 1,925 KB | — | 5 ciphertexts per expert |
| `04_packed_final.py` | Pack all 5 levels into 1 ciphertext | **385 KB** | — | final version |

Compressing ciphertexts (zlib, lzma) gave no reduction (385 → 382 KB), as expected for high-entropy data.

## Known limitations

1. The server is assumed **honest-but-curious** (semi-honest). A server that drops ballots or computes incorrectly is not detected.
2. The committee learns **who submitted an invalid ballot** and **how far each expert is from the consensus** (but not ballot contents).
3. Threshold decryption is currently **3-of-3** (one missing member blocks decryption). t-of-n is not implemented.
4. No protection yet against experts submitting **maliciously crafted ciphertexts** (not honestly generated encryptions).
5. Simulated data; no independent security review.

## Prior work

A search (November 2026) found **no prior work** on fuzzy Delphi over homomorphically encrypted data. The individual building blocks are well known:

- **Validating client submissions without revealing them** for aggregate statistics: **Prio** (Corrigan-Gibbs & Boneh, NSDI 2017) — using secret sharing rather than FHE.
- **Secure multi-party summation**, electronic voting: long established.
- **Threshold decryption, SIMD packing**: standard OpenFHE features.

The contribution here is **assembling these into a complete, working fuzzy Delphi pipeline**, with measurements. It is an application and systems contribution, not a new cryptographic technique. **If you know of related work, please open an issue.**

## `exploration/` — earlier attempts (including negative results)

Before fuzzy Delphi, the project tried using fuzzy logic to make FHE lighter for **credit scoring** (German Credit dataset, UCI).

| Experiment | Finding |
|---|---|
| `credit_01`: 8-level fuzzy rules (BFV) vs exact model (CKKS) | ~90% smaller than CKKS with sigmoid, but only ~62% smaller than a minimal CKKS design. Most of the gain comes from dropping the sigmoid, not from "fuzziness". |
| `credit_02`: triangular soft membership vs hard binning | AUC 0.767 vs 0.766 — within noise. **No benefit.** |
| `credit_03`: packing many records into one ciphertext | 51× smaller, ~220× faster, 100% matching results. This is standard SIMD batching, **not new**. |

Lesson: combining "fuzzy logic + FHE" generically produces nothing new. A valuable result appeared only when choosing a problem that **already uses fuzzy numbers natively** (fuzzy Delphi).

To run, download the data into `exploration/german.data`:
```bash
curl -L -o exploration/german.data https://raw.githubusercontent.com/selva86/datasets/master/GermanCredit.csv
```

## Installation and usage

```bash
pip install -r requirements.txt          # Python 3.12 for OpenFHE
python delphi/04_packed_final.py          # final version
python delphi/02_bfv_integer.py           # simple BFV version (TenSEAL)
```

## How this was made

The idea, direction and problem choices are by **Tuda** (ceo@dottheworld.com). The code was written and run with the help of an AI assistant (Claude, Anthropic). Every figure in this README is the actual output of the code in this repository.

## License

MIT — see `LICENSE`.
