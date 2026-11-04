"""Round processing, run by the GitHub workflow (no secret keys here: anyone can rerun it).

  python server/round.py process  <survey>   after voting closes: check + aggregate, upload batch 1
  python server/round.py advance  <survey>   after key holders upload partials: fuse; publish, or
                                             upload the next batch when a ballot was invalid

Batches live under rounds/{r}/server/batch{b}/ :
  list.json   {"items": [{"name": "0.bin", "kind": "combined", "rep": 0}, ...], ...}
  {n}.bin     ciphertexts the key holders must partially decrypt
Key holders upload rounds/{r}/partial/{i}/batch{b}/{n}.bin (or .../partial/{i}/as{j}/batch{b}/ when
rebuilding absent holder j's key). Holder 1's key always does the "lead" partial decryption.

batch1: REPS combined validity checks + aggregate over every ballot (S: 3, D2: one per ballot, shuffled)
batch2: only if a combined check was non-zero: per-ballot checks for every ballot, every repetition
batch3: aggregate over the ballots batch2 found valid
"""
import hashlib, json, os, secrets, sys, tempfile, urllib.request, urllib.error
import numpy as np
import openfhe
from openfhe import BINARY

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fdfhe
from fdfhe.params import P, REPS
from fdfhe.batch import combined_checks, per_ballot_checks

BASE = os.environ.get("FDFHE_API", "http://127.0.0.1:8787").rstrip("/")
KEY = os.environ.get("FDFHE_ACTION_KEY", "")
PART = 20 * 1024 * 1024
CC_PATH = os.path.join(os.path.dirname(__file__), "..", "web", "fhe", "cc.bin")
TMP = tempfile.mkdtemp(prefix="fdfhe-")


# ---------------------------------------------------------------- HTTP
def _req(method, path, data=None, headers=None):
    h = {"user-agent": "private-delphi-round"}
    h.update(headers or {})
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=300) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_json(path):
    st, b = _req("GET", path)
    if st != 200:
        raise RuntimeError(f"GET {path}: {st} {b[:200]!r}")
    return json.loads(b)


def get_file(sid, path):
    meta = get_json(f"/api/s/{sid}/f/{path}?meta")
    if meta["done"] != meta["parts"]:
        raise RuntimeError(f"{path} is incomplete")
    out = b""
    for i in range(meta["parts"]):
        st, b = _req("GET", f"/api/s/{sid}/f/{path}?part={i}")
        if st != 200:
            raise RuntimeError(f"GET {path} part {i}: {st}")
        out += b
    return out


def exists(sid, path):
    st, b = _req("GET", f"/api/s/{sid}/f/{path}?meta")
    return st == 200 and json.loads(b)["done"] == json.loads(b)["parts"]


def put_file(sid, path, data: bytes):
    parts = max(1, -(-len(data) // PART))
    for i in range(parts):
        chunk = data[i * PART:(i + 1) * PART]
        st, b = _req("PUT", f"/api/s/{sid}/f/{path}?parts={parts}&part={i}", chunk,
                     {"authorization": f"Bearer {KEY}", "content-type": "application/octet-stream"})
        if st != 200:
            raise RuntimeError(f"PUT {path} part {i}: {st} {b[:200]!r}")


def set_status(sid, status):
    st, b = _req("POST", f"/api/s/{sid}/status", json.dumps({"status": status}).encode(),
                 {"authorization": f"Bearer {KEY}", "content-type": "application/json"})
    if st != 200:
        raise RuntimeError(f"status {status}: {st} {b[:200]!r}")


# ---------------------------------------------------------------- crypto helpers
def _file(name, data):
    p = os.path.join(TMP, name)
    with open(p, "wb") as f:
        f.write(data)
    return p


def _load(fn, data, name):
    res = fn(_file(name, data), BINARY)
    return res[0] if isinstance(res, tuple) else res


def load_context(sid):
    cc = _load(openfhe.DeserializeCryptoContext, open(CC_PATH, "rb").read(), "cc.bin")
    pk = _load(openfhe.DeserializePublicKey, get_file(sid, "keys/pk.bin"), "pk.bin")
    if not cc.DeserializeEvalMultKey(_file("em.bin", get_file(sid, "keys/evalmult.bin")), BINARY):
        raise RuntimeError("could not load eval mult key")
    if not cc.DeserializeEvalAutomorphismKey(_file("er.bin", get_file(sid, "keys/evalrot.bin")), BINARY):
        raise RuntimeError("could not load rotation keys")
    return cc, pk


def load_ballots(sid, survey, cc):
    r = survey["round"]
    board = get_json(f"/api/s/{sid}/board?round={r}")["ballots"]
    kept, receipts, dropped = [], [], []
    for b in board:
        data = get_file(sid, f"rounds/{r}/ballots/{b['receipt']}.bin")
        if hashlib.sha256(data).hexdigest() != b["receipt"]:
            dropped.append({"receipt": b["receipt"], "reason": "hash mismatch"})
            continue
        try:
            kept.append(_load(openfhe.DeserializeCiphertext, data, "ballot.bin"))
            receipts.append(b["receipt"])
        except Exception:
            dropped.append({"receipt": b["receipt"], "reason": "unreadable"})
    return kept, receipts, dropped


def upload_batch(sid, r, b, items, meta):
    """items: list of (ciphertext, info dict). Uploads ciphertexts then list.json (last = complete)."""
    listing = []
    for n, (ct, info) in enumerate(items):
        data = openfhe.Serialize(ct, BINARY)
        put_file(sid, f"rounds/{r}/server/batch{b}/{n}.bin", data)
        listing.append({"name": f"{n}.bin", "sha256": hashlib.sha256(data).hexdigest(), **info})
    put_file(sid, f"rounds/{r}/server/batch{b}/list.json",
             json.dumps({"batch": b, "items": listing, **meta}).encode())


def aggregate_items(cc, K, ballots, indices):
    S, D2 = fdfhe.aggregate(cc, K, [ballots[i] for i in indices])
    order = list(range(len(D2)))
    secrets.SystemRandom().shuffle(order)          # unlink distances from experts
    return [(s, {"kind": "S", "j": j}) for j, s in enumerate(S)] + \
           [(D2[g], {"kind": "D2"}) for g in order]


# ---------------------------------------------------------------- phases
def process(sid):
    s = get_json(f"/api/s/{sid}")
    if s["status"] != "closed":
        raise SystemExit(f"survey is '{s['status']}', expected 'closed'")
    r, K = s["round"], s["k"]
    cc, _ = load_context(sid)
    ballots, receipts, dropped = load_ballots(sid, s, cc)
    if not ballots:
        raise SystemExit("no readable ballots")
    seed = fdfhe.board_seed(receipts)
    items = [(c, {"kind": "combined", "rep": rep}) for rep, c in enumerate(combined_checks(cc, K, ballots, seed))]
    items += aggregate_items(cc, K, ballots, list(range(len(ballots))))
    upload_batch(sid, r, 1, items, {"receipts": receipts, "dropped": dropped, "seed": seed.hex(),
                                    "included": list(range(len(ballots))), "K": K})
    set_status(sid, "opening")
    print(f"batch1: {len(items)} ciphertexts for {len(ballots)} ballots ({len(dropped)} dropped)")


def _fuse_batch(sid, cc, r, b, n_items, K):
    """Returns decrypted vectors, or None if not every holder's partial is in yet."""
    files = get_json(f"/api/s/{sid}/list?prefix=rounds/{r}/partial/")
    have = {f["path"] for f in files if f["done"] == f["parts"]}
    sets = {}
    for j in (1, 2, 3):
        cands = [f"rounds/{r}/partial/{j}/batch{b}"] + \
                [f"rounds/{r}/partial/{i}/as{j}/batch{b}" for i in (1, 2, 3) if i != j]
        for c in cands:
            if all(f"{c}/{n}.bin" in have for n in range(n_items)):
                sets[j] = c
                break
    if len(sets) < 3:
        print(f"batch{b}: partials from holders {sorted(sets)} only; waiting")
        return None
    vals = []
    for n in range(n_items):
        parts = [_load(openfhe.DeserializeCiphertext, get_file(sid, f"{sets[j]}/{n}.bin"), f"p{j}.bin") for j in (1, 2, 3)]
        pt = cc.MultipartyDecryptFusion(parts)
        pt.SetLength(K)
        v = np.array(pt.GetPackedValue(), dtype=np.int64)
        vals.append(np.where(v > P // 2, v - P, v))
    return vals


def _publish(sid, s, listing, vals, invalid, opened_by):
    K = listing["K"]
    S = np.stack([vals[i] for i, it in enumerate(listing["items"]) if it["kind"] == "S"])
    D2 = np.stack([vals[i] for i, it in enumerate(listing["items"]) if it["kind"] == "D2"])
    G = D2.shape[0]
    res = {"survey": sid, "round": s["round"], "opened_by": opened_by, "voted": len(listing["receipts"]) + len(listing["dropped"]),
           "invalid": invalid + len(listing["dropped"]), "board_url": f"/api/s/{sid}/board?round={s['round']}",
           "criteria": fdfhe.summarize(S, D2, G)}
    put_file(sid, f"rounds/{s['round']}/results.json", json.dumps(res, ensure_ascii=False, indent=1).encode())
    set_status(sid, "published")
    print("published", json.dumps(res)[:500])


def advance(sid):
    s = get_json(f"/api/s/{sid}")
    if s["status"] != "opening":
        raise SystemExit(f"survey is '{s['status']}', expected 'opening'")
    r, K = s["round"], s["k"]
    cc, _ = load_context(sid)
    b = 1
    while exists(sid, f"rounds/{r}/server/batch{b + 1}/list.json"):
        b += 1
    listing = json.loads(get_file(sid, f"rounds/{r}/server/batch{b}/list.json"))
    vals = _fuse_batch(sid, cc, r, b, len(listing["items"]), K)
    if vals is None:
        return
    opened_by = 2   # holders who took part directly; refined by the UI later
    if b == 1:
        combined = [vals[i] for i, it in enumerate(listing["items"]) if it["kind"] == "combined"]
        if all(np.all(v == 0) for v in combined):
            return _publish(sid, s, listing, vals, 0, opened_by)
        ballots, receipts, _ = load_ballots(sid, s, cc)
        seed = fdfhe.board_seed(receipts)
        checks = per_ballot_checks(cc, K, ballots, seed)
        items = [(checks[i][rep], {"kind": "check", "ballot": i, "rep": rep}) for i in range(len(ballots)) for rep in range(REPS)]
        upload_batch(sid, r, 2, items, {**{k: listing[k] for k in ("receipts", "dropped", "seed")}, "K": K})
        print(f"batch2: {len(items)} per-ballot checks")
    elif b == 2:
        bad = sorted({it["ballot"] for i, it in enumerate(listing["items"]) if it["kind"] == "check" and np.any(vals[i] != 0)})
        good = [i for i in range(len(listing["receipts"])) if i not in bad]
        ballots, _, _ = load_ballots(sid, s, cc)
        upload_batch(sid, r, 3, aggregate_items(cc, K, ballots, good),
                     {**{k: listing[k] for k in ("receipts", "dropped", "seed")}, "K": K, "invalid": bad, "included": good})
        print(f"batch3: aggregate over {len(good)} valid ballots; invalid {bad}")
    else:
        _publish(sid, s, listing, vals, len(listing.get("invalid", [])), opened_by)


if __name__ == "__main__":
    phase, sid = sys.argv[1], sys.argv[2]
    {"process": process, "advance": advance}[phase](sid)
