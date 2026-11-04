// Shared header and footer, so every page has the same navigation and language switch.
(function () {
  const page = document.body.dataset.page;
  const link = (href, key) =>
    `<a href="${href}" data-i18n="${key}"${page === key.split(".")[1] ? ' aria-current="page"' : ""}></a>`;
  document.body.insertAdjacentHTML("afterbegin", `
<header class="top"><div class="wrap">
  <a class="brand" href="index.html">
    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
    <span data-i18n="app.name"></span>
  </a>
  <nav class="links">${link("index.html", "nav.home")}${link("vote.html", "nav.vote")}${link("results.html", "nav.results")}${link("how.html", "nav.how")}${link("organize.html", "nav.organize")}</nav>
  <div class="lang" role="group" data-i18n-attr="aria-label:lang.label">
    <button type="button" data-lang="en">EN</button><button type="button" data-lang="vi">VI</button>
  </div>
</div></header>`);
  document.body.insertAdjacentHTML("beforeend", `
<footer><div class="wrap"><span data-i18n="home.note"></span> ·
  <a href="https://github.com/tudadada/fuzzy-delphi-fhe">GitHub</a></div></footer>`);
})();

const LOCK_ICON = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';
const CHECK_ICON = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12l5 5L20 7"/></svg>';
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
