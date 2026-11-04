// node --test tests/keyvault.test.js
const test = require("node:test");
const assert = require("node:assert");
const V = require("../web/assets/keyvault.js");

const rand = V.randomBytes;

test("GF(256) mul/div are inverses and match AES test vector", () => {
  assert.strictEqual(V._gf.mul(0x57, 0x83), 0xc1);          // FIPS-197 example
  for (let a = 1; a < 256; a++) for (const b of [1, 2, 3, 0x53, 0xff]) {
    assert.strictEqual(V._gf.div(V._gf.mul(a, b), b), a);
  }
});

test("Shamir 2-of-3: every pair rebuilds the secret, one share does not", () => {
  const secret = rand(4096);
  const sh = V.split(secret, 3, 2);
  for (const [i, j] of [[0, 1], [0, 2], [1, 2], [2, 0]]) {
    assert.deepStrictEqual(V.combine([sh[i], sh[j]], 2), secret);
  }
  assert.throws(() => V.combine([sh[0]], 2));
  assert.notDeepStrictEqual(sh[0].y, secret);
});

test("Shamir 3-of-5 round trip through pack/unpack", () => {
  const secret = rand(1000);
  const sh = V.split(secret, 5, 3).map(V.packShare).map(V.unpackShare);
  assert.deepStrictEqual(V.combine([sh[4], sh[1], sh[3]], 3), secret);
});

test("seal/open between two contact keys; wrong key fails", async () => {
  const alice = await V.newContactKey(), bob = await V.newContactKey();
  const msg = rand(70000);
  const sealed = await V.seal(msg, bob.publicJwk);
  assert.deepStrictEqual(await V.open(sealed, bob.privateJwk), msg);
  await assert.rejects(V.open(sealed, alice.privateJwk));
});

test("passphrase lock/unlock; wrong passphrase fails", async () => {
  const sk = rand(5000);
  const blob = await V.lockWithPassphrase(sk, "correct horse battery staple");
  assert.deepStrictEqual(await V.unlockWithPassphrase(blob, "correct horse battery staple"), sk);
  await assert.rejects(V.unlockWithPassphrase(blob, "nope"), /wrong passphrase/);
});

test("full backup flow: member 2 absent, members 1 and 3 rebuild its key", async () => {
  const contacts = [await V.newContactKey(), await V.newContactKey(), await V.newContactKey()];
  const sk2 = rand(656356);                                   // real OpenFHE sk size
  // member 2, at setup: split its key, seal share j to member j
  const sealed = V.split(sk2, 3, 2).map(async (s, j) => V.seal(V.packShare(s), contacts[j].publicJwk));
  const box = await Promise.all(sealed);
  // later: members 1 and 3 open their shares; member 3 forwards its share sealed to member 1
  const s1 = V.unpackShare(await V.open(box[0], contacts[0].privateJwk));
  const s3raw = await V.open(box[2], contacts[2].privateJwk);
  const fwd = await V.seal(s3raw, contacts[0].publicJwk);
  const s3 = V.unpackShare(await V.open(fwd, contacts[0].privateJwk));
  assert.deepStrictEqual(V.combine([s1, s3], 2), sk2);
});
