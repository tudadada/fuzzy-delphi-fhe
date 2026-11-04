// Node side of the ceremony test. Each member's step reloads everything from bytes,
// as if it ran on a separate machine.
//   node ceremony_node.js keygen <dir> <K>
//   node ceremony_node.js partial <dir> <member ids, e.g. 1,2>
const fs = require("fs");
const path = require("path");
const FdCeremony = require("../web/assets/ceremony.js");

const rd = (d, f) => new Uint8Array(fs.readFileSync(path.join(d, f)));
const wr = (d, f, b) => fs.writeFileSync(path.join(d, f), Buffer.from(b));

async function fresh(dir) {
  // a new module instance per member = no shared memory between "machines"
  const factory = require(path.join(process.env.OWASM, "lib", "openfhe_pke"));
  const m = await factory();
  return FdCeremony.make(m, rd(dir, "cc.bin"));
}

async function keygen(dir, K, n = 3) {
  const t = {};
  let s = Date.now();
  let cur = (await fresh(dir)).lead(K);
  t.lead_ms = Date.now() - s;
  const pub = [cur];
  wr(dir, "sk1.bin", cur.sk);
  for (let i = 2; i <= n; i++) {
    s = Date.now();
    cur = (await fresh(dir)).join(K, cur);
    t[`join${i}_ms`] = Date.now() - s;
    pub.push(cur);
    wr(dir, `sk${i}.bin`, cur.sk);
  }
  const last = pub[pub.length - 1];
  const shares = [];
  for (let i = 1; i <= n; i++) {
    s = Date.now();
    shares.push((await fresh(dir)).multShare(rd(dir, `sk${i}.bin`), last.ek, last.pk));
    t[`mult${i}_ms`] = Date.now() - s;
  }
  s = Date.now();
  const fin = (await fresh(dir)).finish(shares, last.rk);
  t.finish_ms = Date.now() - s;
  wr(dir, "pk.bin", last.pk);
  wr(dir, "evalmult.bin", fin.evalMult);
  wr(dir, "evalrot.bin", fin.evalRot);
  const sizes = {
    sk: pub[0].sk.length, pk: last.pk.length, ek_chain: last.ek.length, rk_chain: last.rk.length,
    mult_share: shares[0].length, evalmult: fin.evalMult.length, evalrot: fin.evalRot.length,
  };
  console.log(JSON.stringify({ timings: t, sizes }));
}

async function partial(dir, members) {
  const list = JSON.parse(fs.readFileSync(path.join(dir, "to_decrypt.json"), "utf8"));
  const cts = list.map((f) => rd(dir, f));
  const out = {};
  for (const [j, id] of members.entries()) {
    const s = Date.now();
    const parts = (await fresh(dir)).partial(rd(dir, `sk${id}.bin`), cts, j === 0);
    parts.forEach((b, i) => wr(dir, `part_${id}_${i}.bin`, b));
    out[`member${id}_ms`] = Date.now() - s;
    out.part_bytes = parts[0].length;
  }
  console.log(JSON.stringify(out));
}

const [cmd, dir, arg] = process.argv.slice(2);
(cmd === "keygen" ? keygen(dir, Number(arg)) : partial(dir, arg.split(",").map(Number)))
  .catch((e) => { console.error(e); process.exit(1); });
