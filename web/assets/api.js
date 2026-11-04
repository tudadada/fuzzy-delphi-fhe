// Thin client for the Private Delphi API. Browser (global FdApi) and Node 18+ (require).
(function (root) {
  const PART = 20 * 1024 * 1024;

  function client(base, token) {
    base = (base || "").replace(/\/$/, "");
    const auth = token ? { authorization: `Bearer ${token}` } : {};

    async function req(method, path, body, headers = {}) {
      const r = await fetch(base + path, { method, body, headers: { ...auth, ...headers } });
      if (!r.ok) {
        let msg = `${r.status}`;
        try { msg = (await r.json()).error || msg; } catch (_) {}
        const e = new Error(msg); e.status = r.status; throw e;
      }
      return r;
    }
    const getJson = async (path) => (await req("GET", path)).json();

    return {
      survey: (sid) => getJson(`/api/s/${sid}`),
      whoami: (sid) => getJson(`/api/s/${sid}/whoami`),
      board: (sid, round) => getJson(`/api/s/${sid}/board${round ? `?round=${round}` : ""}`),
      list: (sid, prefix) => getJson(`/api/s/${sid}/list?prefix=${encodeURIComponent(prefix)}`),
      setStatus: async (sid, status) =>
        (await req("POST", `/api/s/${sid}/status`, JSON.stringify({ status }), { "content-type": "application/json" })).json(),
      createSurvey: async (body) =>
        (await req("POST", "/api/surveys", JSON.stringify(body), { "content-type": "application/json" })).json(),
      async meta(sid, path) {
        const r = await fetch(`${base}/api/s/${sid}/f/${path}?meta`);
        return r.ok ? r.json() : null;
      },
      async has(sid, path) {
        const m = await this.meta(sid, path);
        return !!m && m.done === m.parts;
      },
      async get(sid, path, onProgress) {
        const m = await this.meta(sid, path);
        if (!m || m.done !== m.parts) { const e = new Error(`${path} not available yet`); e.status = 404; throw e; }
        const chunks = [];
        let got = 0;
        for (let i = 0; i < m.parts; i++) {
          const b = new Uint8Array(await (await req("GET", `/api/s/${sid}/f/${path}?part=${i}`)).arrayBuffer());
          chunks.push(b); got += b.length;
          if (onProgress) onProgress(got, m.size);
        }
        const out = new Uint8Array(got);
        let o = 0;
        for (const c of chunks) { out.set(c, o); o += c.length; }
        return out;
      },
      async getJsonFile(sid, path) {
        return JSON.parse(new TextDecoder().decode(await this.get(sid, path)));
      },
      async put(sid, path, data, onProgress) {
        if (typeof data === "string") data = new TextEncoder().encode(data);
        const parts = Math.max(1, Math.ceil(data.length / PART));
        for (let i = 0; i < parts; i++) {
          try {
            await req("PUT", `/api/s/${sid}/f/${path}?parts=${parts}&part=${i}`, data.subarray(i * PART, (i + 1) * PART),
              { "content-type": "application/octet-stream" });
          } catch (e) {
            if (e.status !== 409) throw e;          // already uploaded (retry after a dropped connection)
          }
          if (onProgress) onProgress(Math.min((i + 1) * PART, data.length), data.length);
        }
      },
      async ballot(sid, bytes, receipt) {
        return (await req("POST", `/api/s/${sid}/ballot?receipt=${receipt}`, bytes, { "content-type": "application/octet-stream" })).json();
      },
    };
  }

  async function sha256hex(bytes) {
    const C = (typeof globalThis !== "undefined" && globalThis.crypto) || require("crypto").webcrypto;
    const h = await C.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  const api = { client, sha256hex };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FdApi = api;
})(typeof self !== "undefined" ? self : this);
