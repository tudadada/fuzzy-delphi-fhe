// Key-holder vault: protects each member's FHE secret key and backs it up 2-of-3.
// Browser (global FdVault) and Node 20+ (require). Uses only WebCrypto.
//
//   lockWithPassphrase(bytes, pass) / unlockWithPassphrase(blob, pass)
//       the secret-key file a key holder downloads: PBKDF2-SHA256 (600k) + AES-256-GCM
//   newContactKey() -> {publicJwk, privateJwk}
//       ECDH P-256 key each member publishes, so others can seal shares to them
//   split(bytes, n, t) / combine(shares, t)
//       Shamir secret sharing over GF(256), byte by byte
//   seal(bytes, recipientPublicJwk) / open(sealed, myPrivateJwk)
//       ECDH P-256 + HKDF-SHA256 + AES-256-GCM with an ephemeral sender key
//
// Same trust as OpenFHE's own ShareKeys/RecoverSharedKey: any t members together can
// rebuild an absent member's key. Pick key holders who are independent of each other.
(function (root) {
  const C = (typeof globalThis !== "undefined" && globalThis.crypto) || require("crypto").webcrypto;
  const S = C.subtle;
  const enc = new TextEncoder();
  const INFO = enc.encode("fdfhe/v1/share-seal");
  const PBKDF2_ITER = 600000;

  // ---- GF(256) with the AES polynomial x^8 + x^4 + x^3 + x + 1
  const EXP = new Uint8Array(512), LOG = new Uint8Array(256);
  (function () {
    let x = 1;
    for (let i = 0; i < 255; i++) {
      EXP[i] = x; LOG[x] = i;
      x ^= (x << 1) ^ ((x & 0x80) ? 0x11b : 0);   // multiply by generator 3
      x &= 0xff;
    }
    for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  })();
  // getRandomValues caps each call at 65536 bytes
  function randomBytes(n) {
    const out = new Uint8Array(n);
    for (let i = 0; i < n; i += 65536) C.getRandomValues(out.subarray(i, Math.min(n, i + 65536)));
    return out;
  }
  const mul = (a, b) => (a === 0 || b === 0) ? 0 : EXP[LOG[a] + LOG[b]];
  const div = (a, b) => { if (b === 0) throw new Error("div by 0"); return a === 0 ? 0 : EXP[LOG[a] + 255 - LOG[b]]; };

  function split(secret, n, t) {
    if (!(t >= 2 && t <= n && n <= 255)) throw new Error("need 2 <= t <= n <= 255");
    const coef = randomBytes(secret.length * (t - 1));
    const shares = [];
    for (let x = 1; x <= n; x++) {
      const y = new Uint8Array(secret.length);
      for (let i = 0; i < secret.length; i++) {
        let acc = 0;                                           // Horner: highest degree first
        for (let d = t - 2; d >= 0; d--) acc = mul(acc, x) ^ coef[i * (t - 1) + d];
        y[i] = mul(acc, x) ^ secret[i];
      }
      shares.push({ x, y });
    }
    return shares;
  }

  function combine(shares, t) {
    if (shares.length < t) throw new Error(`need ${t} shares, got ${shares.length}`);
    const use = shares.slice(0, t);
    const xs = use.map((s) => s.x);
    if (new Set(xs).size !== xs.length) throw new Error("duplicate share");
    const len = use[0].y.length;
    const out = new Uint8Array(len);
    // Lagrange basis at 0: l_j = prod_{m != j} x_m / (x_m ^ x_j)
    const lj = xs.map((xj, j) => xs.reduce((acc, xm, m) => (m === j ? acc : mul(acc, div(xm, xm ^ xj))), 1));
    for (let i = 0; i < len; i++) {
      let acc = 0;
      for (let j = 0; j < t; j++) acc ^= mul(use[j].y[i], lj[j]);
      out[i] = acc;
    }
    return out;
  }

  // ---- passphrase file
  async function lockWithPassphrase(bytes, pass) {
    const salt = C.getRandomValues(new Uint8Array(16));
    const iv = C.getRandomValues(new Uint8Array(12));
    const base = await S.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveKey"]);
    const key = await S.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt, iterations: PBKDF2_ITER },
      base, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
    const ct = new Uint8Array(await S.encrypt({ name: "AES-GCM", iv }, key, bytes));
    return { v: 1, kdf: "PBKDF2-SHA256", iter: PBKDF2_ITER, salt: b64(salt), iv: b64(iv), ct: b64(ct) };
  }

  async function unlockWithPassphrase(blob, pass) {
    const base = await S.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveKey"]);
    const key = await S.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt: unb64(blob.salt), iterations: blob.iter },
      base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
    try {
      return new Uint8Array(await S.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, key, unb64(blob.ct)));
    } catch (_) {
      throw new Error("wrong passphrase or damaged key file");
    }
  }

  // ---- sealing shares to another member
  async function newContactKey() {
    const kp = await S.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    return { publicJwk: await S.exportKey("jwk", kp.publicKey), privateJwk: await S.exportKey("jwk", kp.privateKey) };
  }

  async function aesFromEcdh(privateKey, publicKey, salt, usage) {
    const bits = await S.deriveBits({ name: "ECDH", public: publicKey }, privateKey, 256);
    const hk = await S.importKey("raw", bits, "HKDF", false, ["deriveKey"]);
    return S.deriveKey({ name: "HKDF", hash: "SHA-256", salt, info: INFO }, hk, { name: "AES-GCM", length: 256 }, false, [usage]);
  }

  async function seal(bytes, recipientPublicJwk) {
    const rpub = await S.importKey("jwk", recipientPublicJwk, { name: "ECDH", namedCurve: "P-256" }, false, []);
    const eph = await S.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    const ephPub = new Uint8Array(await S.exportKey("raw", eph.publicKey));
    const iv = C.getRandomValues(new Uint8Array(12));
    const key = await aesFromEcdh(eph.privateKey, rpub, ephPub, "encrypt");
    const ct = new Uint8Array(await S.encrypt({ name: "AES-GCM", iv }, key, bytes));
    return { v: 1, eph: b64(ephPub), iv: b64(iv), ct: b64(ct) };
  }

  async function open(sealed, myPrivateJwk) {
    const priv = await S.importKey("jwk", myPrivateJwk, { name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);
    const ephPub = unb64(sealed.eph);
    const pub = await S.importKey("raw", ephPub, { name: "ECDH", namedCurve: "P-256" }, false, []);
    const key = await aesFromEcdh(priv, pub, ephPub, "decrypt");
    return new Uint8Array(await S.decrypt({ name: "AES-GCM", iv: unb64(sealed.iv) }, key, unb64(sealed.ct)));
  }

  // share <-> bytes: [x][y...]
  const packShare = (s) => { const b = new Uint8Array(1 + s.y.length); b[0] = s.x; b.set(s.y, 1); return b; };
  const unpackShare = (b) => ({ x: b[0], y: b.slice(1) });

  function b64(u8) {
    let s = "";
    for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return btoa(s);
  }
  function unb64(s) {
    const bin = atob(s); const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return u8;
  }

  const api = { split, combine, packShare, unpackShare, lockWithPassphrase, unlockWithPassphrase,
    newContactKey, seal, open, b64, unb64, randomBytes, _gf: { mul, div } };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FdVault = api;
})(typeof self !== "undefined" ? self : this);
