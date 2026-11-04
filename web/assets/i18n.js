// Tiny i18n: <el data-i18n="key">, <el data-i18n-attr="placeholder:key">, t("key", {vars}).
// Language: ?lang= > saved choice > browser language > English.
const I18N = (() => {
  const SUPPORTED = ["en", "vi"];
  const listeners = [];
  let lang = "en";
  let dict = {};
  let fallback = {};

  function pick() {
    const q = new URLSearchParams(location.search).get("lang");
    if (SUPPORTED.includes(q)) return q;
    try {
      const saved = localStorage.getItem("lang");
      if (SUPPORTED.includes(saved)) return saved;
    } catch (_) {}
    const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
    return SUPPORTED.includes(nav) ? nav : "en";
  }

  async function load(code) {
    const res = await fetch(`i18n/${code}.json`);
    return res.json();
  }

  function t(key, vars = {}) {
    let s = dict[key] ?? fallback[key] ?? key;
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
    return s;
  }

  function apply(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      el.dataset.i18nAttr.split(";").forEach((pair) => {
        const [attr, key] = pair.split(":");
        el.setAttribute(attr, t(key));
      });
    });
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-lang]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
    });
  }

  async function set(code) {
    if (!SUPPORTED.includes(code)) code = "en";
    lang = code;
    dict = await load(code);
    try { localStorage.setItem("lang", code); } catch (_) {}
    apply();
    listeners.forEach((fn) => fn(lang));
  }

  async function init() {
    fallback = await load("en");
    document.querySelectorAll("[data-lang]").forEach((b) => {
      b.addEventListener("click", () => set(b.dataset.lang));
    });
    await set(pick());
  }

  return { init, t, set, apply, onChange: (fn) => listeners.push(fn), get lang() { return lang; } };
})();
