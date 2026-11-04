# Security analysis — Encrypted Fuzzy Delphi (v0.3–v0.5)

🇻🇳 [Bản tiếng Việt](SECURITY.vi.md)

This document states what the system claims, under which assumptions, and **proves the claims that can be proved today**. Where a proof is only a sketch or a gap remains, it says so explicitly. It has **not been reviewed by an independent cryptographer** — corrections are very welcome.

## 1. Setting and notation

| Symbol | Meaning |
|---|---|
| p = 786,433 | BFV plaintext modulus (prime, verified) |
| L = 5 | linguistic levels per criterion |
| K | number of criteria |
| x ∈ Z_p^{L·K} | an expert's ballot; x_{l,k} is level l of criterion k |
| n = 3, t = 2 | committee size and decryption threshold |
| R = 3 | number of independent validity-check repetitions |
| BB | public bulletin board: the list of all submitted ciphertexts |
| H | SHA-256 |

A ballot is **valid** iff for every criterion k, exactly one level is 1 and the others are 0.

**Validity check (v0.3).** For ballot ciphertext Enc(x) and masks r₁ ∈ (Z_p^*)^K, r₂ ∈ (Z_p^*)^{L·K}, the server computes, homomorphically and per criterion k:

  s_k = Σ_l x_{l,k} − 1,  q_{l,k} = x_{l,k}(x_{l,k} − 1),  c_k = r₁ₖ·s_k + Σ_l r₂_{l,k}·q_{l,k}

The committee decrypts c = (c_1,…,c_K). The ballot is accepted iff c = 0, for all R repetitions.

**Masks.** For ballot i and repetition j: masks = G(H(H(ct₁)‖…‖H(ct_E)) ‖ i ‖ j), computed only after the board is locked. G is a deterministic expander (see Gap G4).

## 2. Threat model

| Party | Trusted for privacy? | Trusted for integrity? |
|---|---|---|
| Experts | — | **No.** May submit any plaintext vector, chosen adaptively after seeing the board. *Assumed* to submit an honestly generated encryption (see Gap G1). |
| Server | Must not collude with the committee | **No.** May drop, alter or miscompute — this must be detected. |
| Committee | At most t − 1 = 1 member corrupted | Decrypts correctly (see Gap G3) |
| Auditor | — | Anyone; needs only public data |

Hardness assumptions: Ring-LWE (security of BFV); SHA-256 collision and second-preimage resistance; H modelled as a random oracle for the Fiat–Shamir step.

## 3. Lemma — the per-slot condition characterises one-hot ballots

**Lemma 1.** For a prime p and a vector v ∈ Z_p^L: (Σ_l v_l = 1 and v_l(v_l − 1) = 0 for all l) ⟺ v is one-hot.

*Proof.* Z_p is a field, so v_l(v_l − 1) = 0 implies v_l ∈ {0, 1}. With every entry in {0, 1}, Σ v_l = 1 (mod p) with L < p forces exactly one entry to be 1. The converse is immediate. ∎

**Remark (the v0.1–v0.2 flaw).** The old check only enforced Σ_l v_l(v_l − 1) = 0, a single equation. Combined with Σ v_l = 1 it is equivalent to Σ v_l² = 1, which has non-one-hot solutions over Z_p — e.g. v = (2, b, c, 0, 0) with b + c = −1, bc = 2, which exist for p = 786,433 (b = 336,448, c = 449,984). Lemma 1 explains why checking **each slot** fixes this.

## 4. Theorem 1 — soundness of ballot validation

**Theorem 1.** Let x be an invalid ballot and let the masks be uniform in Z_p^* and independent of x. Then

  Pr[x is accepted] ≤ (p − 1)^{−R}.

*Proof.* By Lemma 1, some criterion k has s_k ≠ 0 or some q_{l,k} ≠ 0. Then c_k is a linear form in the masks (r₁ₖ, r₂_{1,k}, …, r₂_{L,k}) with at least one nonzero coefficient, say on mask r*. Fix all other masks. c_k = 0 holds for at most one value of r*; since r* is uniform over p − 1 values, Pr[c_k = 0] ≤ 1/(p − 1). The R repetitions use independent masks, so the probability that all accept is ≤ (p − 1)^{−R}. ∎

**Completeness.** A valid ballot gives s = 0 and q = 0, hence c = 0 in every repetition (assuming BFV decryption correctness, Gap G7).

**Empirical check** (`tests/soundness_simulation.py`, plaintext simulation, 400,000 random invalid ballots):

| p | R | Measured pass rate | Bound (p − 1)^{−R} |
|---|---|---|---|
| 101 | 1 | 1.01 × 10⁻² | 1.00 × 10⁻² |
| 101 | 2 | 1.10 × 10⁻⁴ | 1.00 × 10⁻⁴ |
| 13 | 3 | 4.68 × 10⁻⁴ | 5.79 × 10⁻⁴ |

The R = 2 row is slightly above the bound (44 passes observed vs. 40 expected, standard deviation ≈ 6.3), which is within sampling noise.

**Corollary 1 (grinding).** Masks depend on the whole board, including the attacker's own ciphertext. Modelling H as a random oracle, an expert who tries Q different ciphertexts before submitting succeeds with probability at most

  Q · (p − 1)^{−R} + negl.

For p = 786,433 and R = 3, (p − 1)^{−3} ≈ 2.06 × 10⁻¹⁸ ≈ 2^{−58.8}. An attacker making Q = 2^{30} attempts (each requiring a fresh encryption) succeeds with probability ≈ 2^{−28.8}. For a stronger margin, R = 5 gives ≈ 2^{−97.9} per attempt (Gap G5).

## 5. Theorem 2 — verifiability against a cheating server

Each expert keeps a receipt h_i = H(ct_i). The server publishes BB, the list of accepted ballots, the validity-check ciphertext hashes, the decrypted check values, and the hash of each aggregate ciphertext.

**Theorem 2.** Assuming the committee decrypts correctly, an auditor detects, except with probability negligible in the collision resistance of SHA-256:

1. **Dropped or altered ballot** — a receipt h_i that does not appear among H(ct) for ct ∈ BB.
2. **Wrong validity verdict** — the validity check is a deterministic function of (ct_i, masks), and the masks are a deterministic function of BB. The auditor recomputes each check ciphertext and compares its hash. A ballot declared invalid whose published decrypted check is 0 (or valid with a nonzero check) is a contradiction.
3. **Wrong aggregation** — the aggregation is a deterministic public function of BB and the accepted set, using no secret input. The auditor recomputes it and compares hashes.

*Proof.* (1) Altering ct_i to ct′ ≠ ct_i with H(ct′) = h_i requires a second preimage. (2)–(3) The auditor's recomputation produces the exact ciphertext the honest server would produce, because every operation is deterministic (verified empirically: recomputed hashes match byte-for-byte). A server publishing a different ciphertext with the same hash finds a collision. ∎

**Not covered:** the shuffle of consensus distances uses server randomness and is a privacy measure, not a verifiable step; and the committee's decryptions are trusted (Gap G3).

## 6. Ballot privacy — proof sketch and gaps

**Claim.** An adversary corrupting at most one committee member, and observing everything public, learns about honest valid ballots nothing beyond the leakage

  𝓛 = (aggregate fuzzy means and defuzzified scores; one validity bit per ballot; the multiset of consensus distances, if the server does not collude; the content of invalid ballots).

**Sketch.**
1. **Shamir shares.** With t = 2, one member holds one share of each other member's key share; a single Shamir share is independent of the secret. The corrupted member's view of the key material is simulatable.
2. **Ciphertexts.** Hybrid argument: replace each honest expert's ciphertext by an encryption of 0. Each step is indistinguishable under the IND-CPA security of BFV with the joint public key, i.e. Ring-LWE.
3. **Decryption shares.** The simulator must produce the honest members' partial decryptions given only the plaintext result. This is the **standard smudging (noise-flooding) argument**: partial decryptions must carry fresh noise large enough to hide the secret-key-dependent noise term.

**Gap G2 — step 3 does not hold with the default settings.** OpenFHE's default `MultipartyMode` is `FIXED_NOISE_MULTIPARTY`, which does **not** flood. Without flooding, partial decryptions can leak information about key shares over many decryptions, and the simulation argument fails. OpenFHE provides `NOISE_FLOODING_MULTIPARTY`. Measured cost (`delphi/08_noise_flooding_check.py`, 20 × 30, two runs):

| Mode | N | Upload per expert | Total time | Correct |
|---|---|---|---|---|
| FIXED_NOISE (default, used in v0.3) | 8,192 | 385 KB | 8.9–10.3 s | ✓ |
| NOISE_FLOODING | 16,384 | 1,281 KB | 32.5–41.2 s | ✓ |

**Addressed in v0.4:** `NOISE_FLOODING_MULTIPARTY` is the default in `delphi/09_hardened.py`. For v0.3 and earlier, the privacy claim is *conditional on adding noise flooding*.

**Further leakage.**
- **Invalid ballots.** With public masks the check values are public functions of small unknowns; the committee can brute-force an invalid ballot's content. Valid ballots always decrypt to 0 and leak nothing.
- **Key recovery.** When a member is absent, the present members reconstruct the absent member's key share (OpenFHE `RecoverSharedKey`). That share is then exposed to whoever reconstructs it. **Use fresh keys for each consultation.**
- **Shuffling** hides which distance belongs to which expert only if the server does not collude with the committee.

## 7. Open gaps

| # | Gap | Effect | Path forward |
|---|---|---|---|
| G1 | Malformed ciphertexts | An expert could submit a ciphertext that is not an honest encryption | Zero-knowledge proof of correct encryption (e.g. Greco, IACR ePrint 2024/594), which could also prove one-hotness and replace the validity check |
| G2 | ~~No noise flooding by default~~ | ~~Privacy proof (step 3) fails~~ | **Addressed in v0.4** |
| G3 | No proof of correct partial decryption | A corrupted member could falsify results | Verifiable decryption / ZK proofs of partial decryption |
| G4 | ~~Mask expander uses NumPy PCG64~~ | ~~Not a cryptographic PRG~~ | **Addressed in v0.4:** SHAKE-256 with domain separation and rejection sampling (exactly uniform on [1, p − 1]) |
| G5 | ~~Grinding margin at R = 3~~ | ~~≈ 2^{−58.8} per attempt~~ | **Addressed in v0.4:** R = 5, ≈ 2^{−97.9} per attempt |
| G6 | Key recovery exposes a share | Reduces security in later sessions | Fresh keys per consultation |
| G7 | BFV correctness relies on OpenFHE parameter selection | Verified empirically only | Formal noise analysis |
| G8 | Security level | OpenFHE default (128-bit classical) not independently checked | Explicit parameter audit |
| G9 | No composition proof (e.g. UC) | Proofs above are per-property | Formal model of the whole protocol |
| G10 | Metadata, timing, side channels | Out of scope | Deployment hardening |

## 8. Summary

- **Proved:** soundness of ballot validation (Theorem 1, with grinding bound) and verifiability against a cheating server (Theorem 2), under standard assumptions and correct committee decryption.
- **Sketched:** ballot privacy, which requires noise flooding (G2) — **enabled from v0.4**.
- **Open:** malformed ciphertexts (G1) and verifiable decryption (G3) are the most important remaining gaps.

## 9. App layer (v0.5, branch `app-layer`) — what changes

The web app keeps the v0.4 protocol and adds four application-level changes. They are **not yet reviewed**.

### 9.1 Batched validity check (`fdfhe/batch.py`)

Opening E · R validity checks costs each key holder E · R partial decryptions of about 640 KB. The server therefore first opens one ciphertext per repetition:

  C_r = Σ_i w_{i,r} · c_{i,r},  where c_{i,r} is ballot i's v0.4 check and w_{i,r} ∈ Z_p^* comes from SHAKE-256 over the locked board, in a domain separate from the masks.

Because the check is linear in its masks, w · check(ct, r₁, r₂) = check(ct, w·r₁, w·r₂). The weight is folded into the masks, so the batch adds no ciphertext multiplication and no noise.

**Theorem 1′.** Let C be a non-empty set of invalid ballots on the board. Modelling the mask and weight expanders as independent random oracles,

  Pr[C_r = 0 for all r] ≤ (2/(p − 1))^R.

*Proof.* Fix r. Honest checks are exactly 0 (completeness), so C_r = Σ_{i∈C} w_{i,r} c_{i,r}. Either (a) every c_{i,r} with i ∈ C is 0, which for any single i ∈ C has probability ≤ 1/(p − 1) by Theorem 1, or (b) some slot k has c_{i,k} ≠ 0 for some i ∈ C. In case (b), C_{r,k} is a non-zero linear form in the weights, which are uniform on Z_p^* and independent of the c's, so it vanishes with probability ≤ 1/(p − 1). A union bound gives ≤ 2/(p − 1) per repetition. The repetitions use independent masks and weights. ∎

For R = 5 this is ≈ 2^{−92.9} per attempt, and the grinding bound becomes Q · (2/(p − 1))^R. If any C_r ≠ 0, the server falls back to the v0.4 per-ballot checks (batch 2) and re-aggregates over the valid ballots (batch 3).

**Leakage improves in the honest case.** When every ballot is valid, the committee learns one bit ("all valid") instead of one validity bit per ballot. In the fallback case the leakage is the same as v0.4.

### 9.2 Key generation in the browser

Key holders run the multiparty key generation in their own browser through openfhe-wasm, built from OpenFHE v1.6.1 with extra bindings (`wasm/fdfhe_extra_em.inc`): multiparty rotation keys, key-map serialization, EvalKey serialization. The chain order and key tags match `fdfhe/sim.py`. CI checks that wasm-made keys give exact results with the Python server.

### 9.3 Application-level 2-of-3 backup (`web/assets/keyvault.js`)

OpenFHE's `ShareKeys` output can't be serialized from Python or wasm. Instead, each holder splits the bytes of their serialized secret key with Shamir sharing over GF(256) (t = 2, n = 3). They seal share j to holder j's ECDH P-256 contact key, using an ephemeral key, HKDF-SHA256, and AES-256-GCM. To stand in for an absent holder, one present holder forwards their share (re-sealed) to the other, who rebuilds the key.

This gives the same trust as `RecoverSharedKey`: any two holders can rebuild a third holder's key, and the rebuilt key is then exposed to the rebuilder (G6). Each holder's own key file is locked with PBKDF2-SHA256 (600,000 iterations) and AES-256-GCM.

### 9.4 Fixed lead holder

Holder 1's key always does the "lead" partial decryption, whether used by holder 1 or rebuilt by someone else. Exactly one lead share per ciphertext is needed, so this removes any coordination.

### 9.5 New gaps

| # | Gap | Effect | Path forward |
|---|---|---|---|
| G11 | Code delivery | Experts and holders trust the JavaScript and wasm the site serves. A malicious host could serve code that leaks answers or keys | Publish hashes of each release, use subresource integrity, allow self-hosting, and offer an offline holder tool |
| G12 | Link tokens | Anyone with a link acts in that role. Tokens stay in the URL fragment, which is never sent to the server | Short-lived tokens, optional sign-in |
| G13 | Batched check reviewed only here | Theorem 1′ is new | Independent review |
