// Key-holder workflow, shared by the key holder page and the end-to-end test.
// Each function does one step and is safe to rerun (uploads are write-once; 409 means done).
//
// Ceremony (status "ceremony"):
//   1. contact()        publish an ECDH contact key (others seal backup shares to it)
//   2. chain()          member 1 starts, members 2 and 3 extend: publish pk, ek, rk; keep sk
//   3. backup()         split sk 2-of-3, seal each share to a member's contact key, publish
//   4. multShare()      once member 3's chain is in: publish the mult-key share
// Opening (status "opening"):
//   5. decrypt()        partial-decrypt every server batch not yet done (as myself)
//   6. forwardShare(j)  if member j is absent: send my share of j's key to the rebuilder
//   7. decryptAs(j)     rebuild j's key from 2 shares and decrypt in j's place
(function (root) {
  const isNode = typeof module !== "undefined" && module.exports;
  const Cer = isNode ? require("./ceremony.js") : root.FdCeremony;
  const Vault = isNode ? require("./keyvault.js") : root.FdVault;

  function make({ api, m, ccBytes, sid, member }) {
    const cer = Cer.make(m, ccBytes);
    const me = `ceremony/${member}`;
    const enc = (o) => new TextEncoder().encode(JSON.stringify(o));

    async function contact(state) {
      if (!state.contact) state.contact = await Vault.newContactKey();
      if (!(await api.has(sid, `${me}/contact.json`))) await api.put(sid, `${me}/contact.json`, enc(state.contact.publicJwk));
      return state;
    }

    async function readyForChain(survey) {
      if (member === 1) return true;
      return api.has(sid, `ceremony/${member - 1}/chain.rk`);
    }

    async function chain(state, K, onProgress) {
      if (state.sk) return state;
      let out;
      if (member === 1) {
        out = cer.lead(K);
      } else {
        const prev = `ceremony/${member - 1}`;
        out = cer.join(K, {
          pk: await api.get(sid, `${prev}/chain.pk`),
          ek: await api.get(sid, `${prev}/chain.ek`),
          rk: await api.get(sid, `${prev}/chain.rk`, onProgress),
        });
      }
      state.sk = out.sk;                                   // caller must save it (locked) before going on
      await api.put(sid, `${me}/chain.pk`, out.pk);
      await api.put(sid, `${me}/chain.ek`, out.ek);
      await api.put(sid, `${me}/chain.rk`, out.rk, onProgress);
      return state;
    }

    async function backup(state) {
      const shares = Vault.split(state.sk, 3, 2);
      for (const j of [1, 2, 3]) {
        const path = `${me}/backup/${j}.json`;
        if (await api.has(sid, path)) continue;
        const jwk = await api.getJsonFile(sid, `ceremony/${j}/contact.json`);
        await api.put(sid, path, enc(await Vault.seal(Vault.packShare(shares[j - 1]), jwk)));
      }
      return state;
    }

    async function multShare(state) {
      if (await api.has(sid, `${me}/mult.bin`)) return state;
      const ek = await api.get(sid, "ceremony/3/chain.ek");
      const pk = await api.get(sid, "ceremony/3/chain.pk");
      await api.put(sid, `${me}/mult.bin`, cer.multShare(state.sk, ek, pk));
      return state;
    }

    async function batches(round) {
      const files = await api.list(sid, `rounds/${round}/server/`);
      return files.filter((f) => /\/batch\d+\/list\.json$/.test(f.path) && f.done === f.parts)
        .map((f) => Number(f.path.match(/batch(\d+)/)[1])).sort((a, b) => a - b);
    }

    async function decryptWith(skBytes, asMember, round, onProgress) {
      const base = asMember === member ? `rounds/${round}/partial/${member}` : `rounds/${round}/partial/${member}/as${asMember}`;
      let done = 0;
      for (const b of await batches(round)) {
        const listing = await api.getJsonFile(sid, `rounds/${round}/server/batch${b}/list.json`);
        const last = `${base}/batch${b}/${listing.items.length - 1}.bin`;
        if (await api.has(sid, last)) continue;
        for (const [n, it] of listing.items.entries()) {
          const out = `${base}/batch${b}/${n}.bin`;
          if (await api.has(sid, out)) continue;
          const ct = await api.get(sid, `rounds/${round}/server/batch${b}/${it.name}`);
          const [part] = cer.partial(skBytes, [ct], asMember === 1);   // holder 1's key always leads
          await api.put(sid, out, part);
          done++;
          if (onProgress) onProgress(n + 1, listing.items.length, b);
        }
      }
      return done;
    }

    const decrypt = (state, round, onProgress) => decryptWith(state.sk, member, round, onProgress);

    // Member `absent` is missing. I (a present member) send my share of their key to `rebuilder`.
    async function forwardShare(state, absent, rebuilder, round) {
      const path = `rounds/${round}/forward/${member}/${absent}-to-${rebuilder}.json`;
      if (await api.has(sid, path)) return;
      const mine = await Vault.open(await api.getJsonFile(sid, `ceremony/${absent}/backup/${member}.json`), state.contact.privateJwk);
      const jwk = await api.getJsonFile(sid, `ceremony/${rebuilder}/contact.json`);
      await api.put(sid, path, enc(await Vault.seal(mine, jwk)));
    }

    async function rebuild(state, absent, helper, round) {
      const mine = Vault.unpackShare(await Vault.open(
        await api.getJsonFile(sid, `ceremony/${absent}/backup/${member}.json`), state.contact.privateJwk));
      const theirs = Vault.unpackShare(await Vault.open(
        await api.getJsonFile(sid, `rounds/${round}/forward/${helper}/${absent}-to-${member}.json`), state.contact.privateJwk));
      return Vault.combine([mine, theirs], 2);
    }

    async function decryptAs(state, absent, helper, round, onProgress) {
      const sk = await rebuild(state, absent, helper, round);
      return decryptWith(sk, absent, round, onProgress);
    }

    return { contact, readyForChain, chain, backup, multShare, batches, decrypt, forwardShare, decryptAs };
  }

  // What a member keeps: their FHE secret key and their contact private key, locked with a passphrase.
  async function exportState(state, pass) {
    const raw = new TextEncoder().encode(JSON.stringify({ sk: Vault.b64(state.sk), contact: state.contact }));
    return Vault.lockWithPassphrase(raw, pass);
  }
  async function importState(blob, pass) {
    const o = JSON.parse(new TextDecoder().decode(await Vault.unlockWithPassphrase(blob, pass)));
    return { sk: o.sk ? Vault.unb64(o.sk) : null, contact: o.contact };
  }

  const api = { make, exportState, importState };
  if (isNode) module.exports = api;
  else root.FdHolder = api;
})(typeof self !== "undefined" ? self : this);
