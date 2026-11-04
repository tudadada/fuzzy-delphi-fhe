// Ballot encryption interface used by vote.js.
//   BallotCrypto.ready()            -> Promise<boolean>  real encryption available?
//   BallotCrypto.encrypt(levels)    -> Promise<Uint8Array> serialized ciphertext
//   BallotCrypto.receipt(bytes)     -> Promise<string>   SHA-256 hex (same as fdfhe.receipt)
// The real implementation loads openfhe-wasm plus the survey's CryptoContext and public key.
// Until that is wired in, demo mode returns random bytes so the flow can be tried end to end.
const BallotCrypto = (() => {
  const LV = 5;
  let wasm = null;

  function encode(levels) {
    const K = levels.length;
    const v = new Array(LV * K).fill(0);
    levels.forEach((l, k) => { v[l * K + k] = 1; });
    return v;
  }

  async function ready(survey) {
    if (!survey || !survey.crypto) return false;          // demo survey: no keys published
    try {
      const factory = (await import(survey.crypto.module)).default;
      const m = await factory();
      const get = async (u) => new Uint8Array(await (await fetch(u)).arrayBuffer());
      const BIN = m.SerType.BINARY;
      const cc = m.DeserializeCryptoContextFromBuffer(await get(survey.crypto.context), BIN);
      const pk = m.DeserializePublicKeyFromBuffer(await get(survey.crypto.publicKey), BIN);
      wasm = { m, cc, pk, BIN };
      return true;
    } catch (e) {
      console.error("wasm load failed", e);
      return false;
    }
  }

  async function encrypt(levels) {
    if (!wasm) {
      const fake = new Uint8Array(64);
      crypto.getRandomValues(fake);
      return fake;
    }
    const { m, cc, pk, BIN } = wasm;
    const pt = cc.MakePackedPlaintext(m.MakeVectorInt64Clipped(encode(levels)), 1, 0);
    return new Uint8Array(m.SerializeCiphertextToBuffer(cc.Encrypt(pk, pt), BIN));
  }

  async function receipt(bytes) {
    const h = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  return { ready, encrypt, receipt, encode, get demo() { return !wasm; } };
})();
