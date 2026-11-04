// Integration test against `wrangler dev --local` (BASE defaults to http://127.0.0.1:8787).
// Needs .dev.vars with ADMIN_KEY=local-admin, ACTION_KEY=local-action.
const test = require("node:test");
const assert = require("node:assert");
const crypto = require("node:crypto");

const BASE = process.env.BASE || "http://127.0.0.1:8787";
const ADMIN = process.env.ADMIN_KEY || "local-admin";
const ACTION = process.env.ACTION_KEY || "local-action";
const api = (p, init = {}) => fetch(BASE + p, init);
const auth = (t) => ({ authorization: `Bearer ${t}` });
const hex = (b) => crypto.createHash("sha256").update(b).digest("hex");

let S, T;

test("admin creates a survey; wrong key refused", async () => {
  const bad = await api("/api/surveys", { method: "POST", body: JSON.stringify({ admin_key: "x", criteria: [{ en: "a" }], experts: 1 }) });
  assert.strictEqual(bad.status, 403);
  const r = await api("/api/surveys", {
    method: "POST",
    body: JSON.stringify({ admin_key: ADMIN, title: { en: "Test", vi: "Thử" },
      criteria: [{ en: "A", vi: "A" }, { en: "B", vi: "B" }], experts: 3 }),
  });
  assert.strictEqual(r.status, 200);
  ({ id: S, tokens: T } = await r.json());
  assert.strictEqual(T.holders.length, 3);
  assert.strictEqual(T.experts.length, 3);
  const v = await (await api(`/api/s/${S}`)).json();
  assert.strictEqual(v.status, "ceremony");
  assert.strictEqual(v.k, 2);
});

test("whoami identifies roles", async () => {
  const h2 = await (await api(`/api/s/${S}/whoami`, { headers: auth(T.holders[1]) })).json();
  assert.deepStrictEqual(h2, { role: "holder", member: 2 });
  assert.strictEqual((await api(`/api/s/${S}/whoami`, { headers: auth("nope") })).status, 403);
});

test("holder writes only its own ceremony folder; files are write-once; multipart works", async () => {
  const body = crypto.randomBytes(1000);
  let r = await api(`/api/s/${S}/f/ceremony/1/chain.pk`, { method: "PUT", headers: auth(T.holders[0]), body });
  assert.strictEqual(r.status, 200);
  r = await api(`/api/s/${S}/f/ceremony/1/chain.pk`, { method: "PUT", headers: auth(T.holders[0]), body });
  assert.strictEqual(r.status, 409);
  r = await api(`/api/s/${S}/f/ceremony/2/chain.pk`, { method: "PUT", headers: auth(T.holders[0]), body });
  assert.strictEqual(r.status, 403);
  const got = Buffer.from(await (await api(`/api/s/${S}/f/ceremony/1/chain.pk`)).arrayBuffer());
  assert.ok(got.equals(body));
  const a = crypto.randomBytes(500), b = crypto.randomBytes(700);
  await api(`/api/s/${S}/f/ceremony/1/chain.rk?parts=2&part=1`, { method: "PUT", headers: auth(T.holders[0]), body: b });
  let meta = await (await api(`/api/s/${S}/f/ceremony/1/chain.rk?meta`)).json();
  assert.strictEqual(meta.done, 1);
  await api(`/api/s/${S}/f/ceremony/1/chain.rk?parts=2&part=0`, { method: "PUT", headers: auth(T.holders[0]), body: a });
  meta = await (await api(`/api/s/${S}/f/ceremony/1/chain.rk?meta`)).json();
  assert.deepStrictEqual([meta.parts, meta.done, meta.size], [2, 2, 1200]);
});

test("action writes keys/; experts vote only while open, once per round", async () => {
  let r = await api(`/api/s/${S}/f/keys/pk.bin`, { method: "PUT", headers: auth(ACTION), body: "pk" });
  assert.strictEqual(r.status, 200);
  const ballot = crypto.randomBytes(2048);
  const rec = hex(ballot);
  r = await api(`/api/s/${S}/ballot?receipt=${rec}`, { method: "POST", headers: auth(T.experts[0]), body: ballot });
  assert.strictEqual(r.status, 409);                         // not open yet
  r = await api(`/api/s/${S}/status`, { method: "POST", headers: auth(T.experts[0]), body: JSON.stringify({ status: "open" }) });
  assert.strictEqual(r.status, 403);
  r = await api(`/api/s/${S}/status`, { method: "POST", headers: auth(T.organizer), body: JSON.stringify({ status: "open" }) });
  assert.strictEqual(r.status, 200);
  r = await api(`/api/s/${S}/ballot?receipt=${rec}`, { method: "POST", headers: auth(T.experts[0]), body: ballot });
  assert.strictEqual(r.status, 200);
  r = await api(`/api/s/${S}/ballot?receipt=${hex(Buffer.from("x"))}`, { method: "POST", headers: auth(T.experts[0]), body: "x" });
  assert.strictEqual(r.status, 409);                         // second ballot, same invite
  r = await api(`/api/s/${S}/ballot?receipt=${rec}`, { method: "POST", headers: auth(T.holders[0]), body: ballot });
  assert.strictEqual(r.status, 403);                         // holders can't vote
  const board = await (await api(`/api/s/${S}/board`)).json();
  assert.deepStrictEqual(board.ballots.map((b) => b.receipt), [rec]);
  const back = Buffer.from(await (await api(`/api/s/${S}/f/rounds/1/ballots/${rec}.bin`)).arrayBuffer());
  assert.ok(back.equals(ballot));
});

test("closing stops voting", async () => {
  let r = await api(`/api/s/${S}/status`, { method: "POST", headers: auth(T.organizer), body: JSON.stringify({ status: "closed" }) });
  assert.strictEqual(r.status, 200);
  const ballot = crypto.randomBytes(100);
  r = await api(`/api/s/${S}/ballot?receipt=${hex(ballot)}`, { method: "POST", headers: auth(T.experts[1]), body: ballot });
  assert.strictEqual(r.status, 409);
});

test("static site is served", async () => {
  const r = await api("/vote.html");
  assert.strictEqual(r.status, 200);
  assert.match(await r.text(), /vote\.js/);
});
