// Key-holder cryptography on top of openfhe-wasm (with the fdfhe extra bindings).
// Works in the browser (global FdCeremony) and in Node (require).
// Every input and output is a Uint8Array, so each step can run on a different machine.
//
// Ceremony for n key holders (same order as fdfhe/sim.py):
//   A. member 1: lead()            -> {sk, pk, ek, rk}
//      member i: join(prev)        -> {sk, pk, ek, rk}     (chained: uses the previous member's pk, ek, rk)
//   B. every member: multShare(sk, ekFull, pkFinal) -> share
//   C. anyone: finish(shares, rkFull) -> {evalMult, evalRot}  (public; the server needs these)
// Opening results: each present member: partial(sk, cts, isLead); anyone: fuse(partials)
(function (root) {
  const LV = 5;
  const rotIdx = (K) => Array.from({ length: LV - 1 }, (_, i) => (i + 1) * K);

  function make(m, ccBytes) {
    const BIN = m.SerType.BINARY;
    const cc = m.DeserializeCryptoContextFromBuffer(ccBytes, BIN);
    if (!cc) throw new Error("could not load the survey's crypto context");
    const ser = {
      pk: (x) => m.SerializePublicKeyToBuffer(x, BIN),
      sk: (x) => m.SerializePrivateKeyToBuffer(x, BIN),
      ct: (x) => m.SerializeCiphertextToBuffer(x, BIN),
      ek: (x) => m.FdSerializeEvalKey(x, BIN),
      map: (x) => m.FdSerializeKeyMap(x, BIN),
    };
    const de = {
      pk: (b) => m.DeserializePublicKeyFromBuffer(b, BIN),
      sk: (b) => m.DeserializePrivateKeyFromBuffer(b, BIN),
      ct: (b) => m.DeserializeCiphertextFromBuffer(b, BIN),
      ek: (b) => m.FdDeserializeEvalKey(b, BIN),
      map: (b) => m.FdDeserializeKeyMap(b, BIN),
    };

    function lead(K) {
      const kp = cc.KeyGen();
      const ek = cc.KeySwitchGen(kp.secretKey, kp.secretKey);
      cc.EvalAtIndexKeyGen(kp.secretKey, rotIdx(K));
      const rk = m.FdGetEvalAutomorphismKeyMap(cc, kp.secretKey.GetKeyTag());
      return { sk: ser.sk(kp.secretKey), pk: ser.pk(kp.publicKey), ek: ser.ek(ek), rk: ser.map(rk) };
    }

    function join(K, prev) {
      const prevEk = de.ek(prev.ek);
      const prevRk = de.map(prev.rk);
      const kp = cc.MultipartyKeyGen(de.pk(prev.pk));
      const tag = kp.publicKey.GetKeyTag();
      const ek = cc.MultiAddEvalKeys(prevEk, cc.MultiKeySwitchGen(kp.secretKey, kp.secretKey, prevEk), tag);
      const rk = m.FdMultiAddEvalAutomorphismKeys(cc, prevRk,
        m.FdMultiEvalAtIndexKeyGen(cc, kp.secretKey, prevRk, rotIdx(K), tag), tag);
      return { sk: ser.sk(kp.secretKey), pk: ser.pk(kp.publicKey), ek: ser.ek(ek), rk: ser.map(rk) };
    }

    function multShare(skBytes, ekFullBytes, pkFinalBytes) {
      const tag = de.pk(pkFinalBytes).GetKeyTag();
      return ser.ek(cc.MultiMultEvalKey(de.sk(skBytes), de.ek(ekFullBytes), tag));
    }

    function finish(shareBytesList, rkFullBytes) {
      let fin = de.ek(shareBytesList[0]);
      for (const b of shareBytesList.slice(1)) fin = cc.MultiAddEvalMultKeys(fin, de.ek(b), fin.GetKeyTag());
      cc.ClearEvalMultKeys();
      cc.InsertEvalMultKey([fin]);
      m.FdInsertEvalAutomorphismKey(cc, de.map(rkFullBytes));
      return {
        evalMult: cc.SerializeEvalMultKeyToBuffer(BIN),
        evalRot: cc.SerializeEvalAutomorphismKeyToBuffer(BIN),
      };
    }

    function partial(skBytes, ctBytesList, isLead) {
      const sk = de.sk(skBytes);
      return ctBytesList.map((b) => {
        const v = isLead ? cc.MultipartyDecryptLead(sk, [de.ct(b)]) : cc.MultipartyDecryptMain(sk, [de.ct(b)]);
        return ser.ct(v.get(0));
      });
    }

    function fuse(partialBytesPerMember, length, p) {
      const n = partialBytesPerMember[0].length;
      const out = [];
      for (let i = 0; i < n; i++) {
        const pt = cc.MultipartyDecryptFusion(partialBytesPerMember.map((list) => de.ct(list[i])));
        pt.SetLength(length);
        const v = pt.GetPackedValue();
        const len = Array.isArray(v) ? v.length : v.size();
        const at = Array.isArray(v) ? (j) => v[j] : (j) => v.get(j);
        const arr = [];
        for (let j = 0; j < len; j++) { const x = Number(at(j)); arr.push(x > p / 2 ? x - p : x); }
        out.push(arr);
      }
      return out;
    }

    return { cc, lead, join, multShare, finish, partial, fuse };
  }

  const api = { make, rotIdx };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FdCeremony = api;
})(typeof self !== "undefined" ? self : this);
