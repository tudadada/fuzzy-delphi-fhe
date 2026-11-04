// End-to-end: Worker (wrangler dev) + wasm key holders + wasm experts + python round processing.
//   BASE=http://127.0.0.1:8787 ADMIN_KEY=... ACTION_KEY=... node tests/e2e.js
// Expects web/fhe/cc.bin and web/vendor/openfhe/openfhe_pke.js to exist.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const assert = require("assert");
const { client, sha256hex } = require("../web/assets/api.js");
const Holder = require("../web/assets/holder.js");

const BASE = process.env.BASE || "http://127.0.0.1:8787";
const ROOT = path.join(__dirname, "..");
const ccBytes = new Uint8Array(fs.readFileSync(path.join(ROOT, "web", "fhe", "cc.bin")));
const factory = require(path.join(ROOT, "web", "vendor", "openfhe", "openfhe_pke.js"));
const env = { ...process.env, FDFHE_API: BASE, FDFHE_ACTION_KEY: process.env.ACTION_KEY };
const LV = 5, K = 4, E = 6;
const TFN = [[0, 0, 1], [0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 4]];
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const t0 = Date.now();

function py(...args) { log("$ python", args.join(" ")); execFileSync("python", [path.join(ROOT, "server", "round.py"), ...args], { env, stdio: "inherit" }); }
function nodeRun(script, ...args) { execFileSync("node", [path.join(ROOT, script), ...args], { env, stdio: "inherit" }); }

async function main() {
  const admin = client(BASE);
  const { id: sid, tokens } = await admin.createSurvey({
    admin_key: process.env.ADMIN_KEY, title: { en: "E2E", vi: "E2E" },
    criteria: Array.from({ length: K }, (_, k) => ({ en: `C${k}`, vi: `C${k}` })), experts: E,
  });
  log("survey", sid);

  // ---- key ceremony: each holder has its own wasm instance and API token
  const H = {}, S = {};
  for (const i of [1, 2, 3]) {
    H[i] = Holder.make({ api: client(BASE, tokens.holders[i - 1]), m: await factory(), ccBytes, sid, member: i });
    S[i] = await H[i].contact({});
  }
  for (const i of [1, 2, 3]) { await H[i].chain(S[i], K); log(`holder ${i} chain done`); }
  for (const i of [1, 2, 3]) await H[i].backup(S[i]);
  // the saved key file must round-trip
  const blob = await Holder.exportState(S[2], "pass phrase two");
  const back = await Holder.importState(blob, "pass phrase two");
  assert.deepStrictEqual(Buffer.from(back.sk), Buffer.from(S[2].sk));
  for (const i of [1, 2, 3]) await H[i].multShare(S[i]);
  log("ceremony shares done");
  nodeRun("server/finish.js", sid);
  assert.strictEqual((await admin.survey(sid)).status, "open");

  // ---- experts vote in wasm; expert 0 cheats
  const m = await factory();
  const BIN = m.SerType.BINARY;
  const cc = m.DeserializeCryptoContextFromBuffer(ccBytes, BIN);
  const pk = m.DeserializePublicKeyFromBuffer(await admin.get(sid, "keys/pk.bin"), BIN);
  const votes = Array.from({ length: E }, (_, e) => Array.from({ length: K }, (_, k) => (e * 7 + k * 3) % LV));
  for (let e = 0; e < E; e++) {
    const v = new Array(LV * K).fill(0);
    votes[e].forEach((l, k) => { v[l * K + k] = 1; });
    if (e === 0) v[4 * K + 1] = 2;                                    // invalid: weight 2
    const bytes = new Uint8Array(m.SerializeCiphertextToBuffer(cc.Encrypt(pk, cc.MakePackedPlaintext(m.MakeVectorInt64Clipped(v), 1, 0)), BIN));
    await client(BASE, tokens.experts[e]).ballot(sid, bytes, await sha256hex(bytes));
  }
  log("ballots in:", (await admin.board(sid)).ballots.length);
  await client(BASE, tokens.organizer).setStatus(sid, "closed");

  // ---- process; holder 2 is absent: 3 forwards its share of 2's key to 1, 1 decrypts as 2
  py("process", sid);
  for (let step = 0; step < 4; step++) {
    const s = await admin.survey(sid);
    if (s.status === "published") break;
    assert.strictEqual(s.status, "opening");
    await H[1].decrypt(S[1], s.round);
    await H[3].decrypt(S[3], s.round);
    await H[3].forwardShare(S[3], 2, 1, s.round);
    await H[1].decryptAs(S[1], 2, 3, s.round);
    log(`partials for batches ${await H[1].batches(s.round)} done`);
    py("advance", sid);
  }
  const s = await admin.survey(sid);
  assert.strictEqual(s.status, "published");
  const res = await admin.getJsonFile(sid, `rounds/${s.round}/results.json`);
  log("results", JSON.stringify(res));

  // ---- compare with plaintext over the honest experts
  const good = votes.slice(1);
  assert.strictEqual(res.invalid, 1);
  for (let k = 0; k < K; k++) {
    const mean = [0, 1, 2].map((j) => good.reduce((a, v) => a + TFN[v[k]][j] / 4, 0) / good.length);
    res.criteria[k].fuzzy_mean.forEach((x, j) => assert.ok(Math.abs(x - mean[j]) < 1e-3, `criterion ${k}: ${x} vs ${mean[j]}`));
    const dist = good.map((v) => Math.sqrt([0, 1, 2].reduce((a, j) => a + (TFN[v[k]][j] / 4 - mean[j]) ** 2, 0) / 3));
    const share = dist.filter((d) => d <= 0.2 + 1e-12).length / good.length;
    assert.ok(Math.abs(res.criteria[k].agree_share - share) < 1e-3, `criterion ${k} agree ${res.criteria[k].agree_share} vs ${share}`);
  }
  log(`E2E OK in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
}

main().catch((e) => { console.error(e); process.exit(1); });
