// Encrypt a ballot with openfhe-wasm, using a CryptoContext and public key made by Python.
// Usage: node wasm_encrypt.js <cc.bin> <pk.bin> <levels comma list> <out ct.bin>
const fs = require("fs");
const path = require("path");

const LV = 5;

function encode(levels) {
  const K = levels.length;
  const v = new Array(LV * K).fill(0);
  levels.forEach((l, k) => { v[l * K + k] = 1; });
  return v;
}

async function main() {
  const [ccPath, pkPath, levelsArg, outPath] = process.argv.slice(2);
  const factory = require(path.join(process.env.OWASM, "lib", "openfhe_pke"));
  const m = await factory();
  const BIN = m.SerType.BINARY;
  const t0 = Date.now();
  const cc = m.DeserializeCryptoContextFromBuffer(new Uint8Array(fs.readFileSync(ccPath)), BIN);
  const pk = m.DeserializePublicKeyFromBuffer(new Uint8Array(fs.readFileSync(pkPath)), BIN);
  const t1 = Date.now();
  const levels = levelsArg.split(",").map(Number);
  const pt = cc.MakePackedPlaintext(m.MakeVectorInt64Clipped(encode(levels)), 1, 0);
  const ct = cc.Encrypt(pk, pt);
  const buf = m.SerializeCiphertextToBuffer(ct, BIN);
  const t2 = Date.now();
  fs.writeFileSync(outPath, Buffer.from(buf));
  console.log(JSON.stringify({ load_ms: t1 - t0, encrypt_ms: t2 - t1, bytes: buf.length }));
}

main().catch((e) => { console.error(e); process.exit(1); });
