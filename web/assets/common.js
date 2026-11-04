// Shared page helpers: survey id and token from the URL, wasm loader, small DOM helpers.
// Tokens travel in the URL fragment (#t=...), which browsers never send to the server.
const Fd = (() => {
  const params = new URLSearchParams(location.search);
  const frag = new URLSearchParams(location.hash.slice(1));
  const sid = params.get("s");
  const token = frag.get("t") || "";
  const api = FdApi.client("", token);
  let wasmPromise = null;

  function loadScript(src) {
    return new Promise((ok, bad) => {
      const s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = () => bad(new Error(`could not load ${src}`));
      document.head.appendChild(s);
    });
  }

  // openfhe-wasm (with fdfhe bindings) + the shared crypto context
  function wasm() {
    if (!wasmPromise) {
      wasmPromise = (async () => {
        await loadScript("vendor/openfhe/openfhe_pke.js");
        const factory = window.Module;
        const m = await factory({ locateFile: (f) => `vendor/openfhe/${f}` });
        const ccBytes = new Uint8Array(await (await fetch("fhe/cc.bin")).arrayBuffer());
        return { m, ccBytes };
      })();
    }
    return wasmPromise;
  }

  const name = (o) => (o && (o[I18N.lang] || o.en || o.vi)) || "";
  const $ = (id) => document.getElementById(id);
  const mb = (n) => (n / 1048576).toLocaleString(I18N.lang === "vi" ? "vi-VN" : "en-US", { maximumFractionDigits: 1 });

  function download(filename, text) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
    a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  return { sid, token, api, wasm, name, $, mb, download };
})();
