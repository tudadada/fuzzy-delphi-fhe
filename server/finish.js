// Finish a key ceremony (public step, no secrets): combine the 3 mult-key shares and the
// final rotation keys, upload keys/pk.bin, keys/evalmult.bin, keys/evalrot.bin, open voting.
//   FDFHE_API=... FDFHE_ACTION_KEY=... node server/finish.js <survey>
const fs = require("fs");
const path = require("path");
const FdCeremony = require("../web/assets/ceremony.js");

const BASE = (process.env.FDFHE_API || "http://127.0.0.1:8787").replace(/\/$/, "");
const KEY = process.env.FDFHE_ACTION_KEY || "";
const PART = 20 * 1024 * 1024;
const LIB = process.env.OWASM_LIB || path.join(__dirname, "..", "web", "vendor", "openfhe");

async function getFile(sid, p) {
  const meta = await (await fetch(`${BASE}/api/s/${sid}/f/${p}?meta`)).json();
  if (meta.done !== meta.parts) throw new Error(`${p} incomplete`);
  const bufs = [];
  for (let i = 0; i < meta.parts; i++) {
    const r = await fetch(`${BASE}/api/s/${sid}/f/${p}?part=${i}`);
    if (!r.ok) throw new Error(`GET ${p}#${i}: ${r.status}`);
    bufs.push(Buffer.from(await r.arrayBuffer()));
  }
  return new Uint8Array(Buffer.concat(bufs));
}

async function putFile(sid, p, data) {
  const parts = Math.max(1, Math.ceil(data.length / PART));
  for (let i = 0; i < parts; i++) {
    const r = await fetch(`${BASE}/api/s/${sid}/f/${p}?parts=${parts}&part=${i}`, {
      method: "PUT", headers: { authorization: `Bearer ${KEY}` }, body: data.subarray(i * PART, (i + 1) * PART),
    });
    if (!r.ok) throw new Error(`PUT ${p}#${i}: ${r.status} ${await r.text()}`);
  }
}

async function main(sid) {
  const factory = require(path.join(LIB, "openfhe_pke.js"));
  const m = await factory();
  const cer = FdCeremony.make(m, new Uint8Array(fs.readFileSync(path.join(__dirname, "..", "web", "fhe", "cc.bin"))));
  const shares = [];
  for (const i of [1, 2, 3]) shares.push(await getFile(sid, `ceremony/${i}/mult.bin`));
  const rk = await getFile(sid, "ceremony/3/chain.rk");
  const pk = await getFile(sid, "ceremony/3/chain.pk");
  const fin = cer.finish(shares, rk);
  await putFile(sid, "keys/pk.bin", pk);
  await putFile(sid, "keys/evalmult.bin", fin.evalMult);
  await putFile(sid, "keys/evalrot.bin", fin.evalRot);
  const r = await fetch(`${BASE}/api/s/${sid}/status`, {
    method: "POST", headers: { authorization: `Bearer ${KEY}`, "content-type": "application/json" },
    body: JSON.stringify({ status: "open" }),
  });
  if (!r.ok) throw new Error(`status: ${r.status} ${await r.text()}`);
  console.log(`finished ceremony for ${sid}: pk ${pk.length} B, evalmult ${fin.evalMult.length} B, evalrot ${fin.evalRot.length} B`);
}

main(process.argv[2]).catch((e) => { console.error(e); process.exit(1); });
