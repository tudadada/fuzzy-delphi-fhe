// Ballot encryption used by vote.js.
//   BallotCrypto.ready({m, ccBytes, pkBytes}) -> true when real encryption is available
//   BallotCrypto.encrypt(levels)              -> Uint8Array serialized ciphertext
//   BallotCrypto.receipt(bytes)               -> SHA-256 hex (same as fdfhe.receipt)
// Without ready() (demo survey), encrypt() returns random bytes so the flow can be tried.
const BallotCrypto = (() => {
  const LV = 5;
  let w = null;

  function encode(levels) {
    const K = levels.length;
    const v = new Array(LV * K).fill(0);
    levels.forEach((l, k) => { v[l * K + k] = 1; });
    return v;
  }

  function ready({ m, ccBytes, pkBytes }) {
    const BIN = m.SerType.BINARY;
    const cc = m.DeserializeCryptoContextFromBuffer(ccBytes, BIN);
    const pk = m.DeserializePublicKeyFromBuffer(pkBytes, BIN);
    if (!cc || !pk) throw new Error("could not load the survey's public key");
    w = { m, cc, pk, BIN };
    return true;
  }

  async function encrypt(levels) {
    if (!w) {
      const fake = new Uint8Array(64);
      crypto.getRandomValues(fake);
      return fake;
    }
    const { m, cc, pk, BIN } = w;
    const pt = cc.MakePackedPlaintext(m.MakeVectorInt64Clipped(encode(levels)), 1, 0);
    return new Uint8Array(m.SerializeCiphertextToBuffer(cc.Encrypt(pk, pt), BIN));
  }

  async function receipt(bytes) {
    const h = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  return { ready, encrypt, receipt, encode, get demo() { return !w; } };
})();
