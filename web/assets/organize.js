// Organizer: create a survey and hand out links; with ?s=...#t=... show the survey dashboard.
(async function () {
  const t = (k, v) => I18N.t(k, v);
  const { $, api, sid, name } = Fd;
  const STAGES = ["ceremony", "open", "closed", "opening", "published"];
  const origin = location.origin + location.pathname.replace(/[^/]*$/, "");
  const link = (page, id, tok) => `${origin}${page}?s=${id}#t=${tok}`;
  let created = null;

  function parseCriteria(text) {
    return text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      const [a, b] = l.split("|").map((x) => x.trim());
      return b ? { en: a, vi: b } : { en: a, vi: a };
    });
  }

  function linkRow(label, url) {
    return `<div class="linkrow"><span class="small muted">${esc(label)}</span>
      <input readonly value="${esc(url)}" onfocus="this.select()">
      <button type="button" data-copy="${esc(url)}">${esc(t("org.links.copy"))}</button></div>`;
  }

  function renderLinks() {
    const { id, tokens } = created;
    $("l-org").innerHTML = linkRow("", link("organize.html", id, tokens.organizer));
    $("l-holders").innerHTML = tokens.holders.map((tk, i) => linkRow(`${i + 1}`, link("keyholder.html", id, tk))).join("");
    $("l-experts").innerHTML = tokens.experts.map((tk, i) => linkRow(`${i + 1}`, link("vote.html", id, tk))).join("");
  }

  document.addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-copy]");
    if (!b) return;
    try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = t("vote.copied"); } catch (_) {}
  });

  $("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("err").textContent = "";
    const criteria = parseCriteria($("criteria").value);
    const experts = parseInt($("experts").value, 10);
    if (!criteria.length) { $("err").textContent = t("org.err.criteria"); return; }
    if (!(experts >= 1)) { $("err").textContent = t("org.err.experts"); return; }
    $("go").disabled = true; $("go").textContent = t("org.creating");
    try {
      created = await api.createSurvey({ admin_key: $("admin").value, title: { en: $("t-en").value, vi: $("t-vi").value || $("t-en").value }, criteria, experts });
      $("create").hidden = true; $("links").hidden = false;
      renderLinks();
    } catch (err) {
      $("err").textContent = t("org.err.create", { msg: err.message });
    } finally {
      $("go").disabled = false; $("go").textContent = t("org.create");
    }
  });

  $("dl").onclick = () => {
    const { id, tokens } = created;
    Fd.download(`survey-${id}-links.json`, JSON.stringify({
      survey: id, organizer: link("organize.html", id, tokens.organizer),
      key_holders: tokens.holders.map((tk) => link("keyholder.html", id, tk)),
      experts: tokens.experts.map((tk) => link("vote.html", id, tk)),
    }, null, 2));
  };

  // ---------------- dashboard
  async function holderStage(i, files) {
    const has = (p) => files.some((f) => f.path === p);
    if (has(`ceremony/${i}/mult.bin`)) return "org.holder.done";
    if (has(`ceremony/${i}/backup/3.json`)) return "org.holder.backup";
    if (has(`ceremony/${i}/chain.rk`)) return "org.holder.chain";
    return "org.holder.waiting";
  }

  async function renderDash() {
    $("d-err").textContent = "";
    const s = await api.survey(sid);
    $("d-title").textContent = name(s.title);
    const cur = STAGES.indexOf(s.status);
    $("timeline").innerHTML = STAGES.map((st, i) =>
      `<li class="${i < cur ? "done" : i === cur ? "now" : ""}">${i < cur ? CHECK_ICON : ""}<span>${esc(t("org.stage." + st))}</span></li>`).join("");
    $("d-round").textContent = t("org.dash.round", { round: s.round });
    $("d-status").textContent = t("org.stage." + s.status);
    $("d-ballots").textContent = `${s.ballots}`;
    const rows = [];
    for (const i of [1, 2, 3]) rows.push(`<div class="crit" style="display:flex;justify-content:space-between"><span>${esc(t("org.holder.status", { n: i }))}</span><b>${esc(t(await holderStage(i, s.files)))}</b></div>`);
    $("d-holders").innerHTML = rows.join("");
    $("d-holders").hidden = s.status !== "ceremony";
    $("b-close").hidden = s.status !== "open";
    $("b-next").hidden = s.status !== "published";
    $("b-next").textContent = t("org.nextround", { round: s.round + 1 });
    $("b-results").hidden = s.status !== "published";
    $("b-results").href = `results.html?s=${sid}`;
  }

  async function act(status, confirmKey) {
    if (confirmKey && !confirm(t(confirmKey))) return;
    try { await api.setStatus(sid, status); await renderDash(); } catch (e) { $("d-err").textContent = t("kh.err.generic", { msg: e.message }); }
  }
  $("b-close").onclick = () => act("closed", "org.close.confirm");
  $("b-next").onclick = () => act("open");
  $("b-refresh").onclick = () => renderDash().catch((e) => { $("d-err").textContent = e.message; });

  await I18N.init();
  if (sid && Fd.token) {
    $("create").hidden = true; $("dash").hidden = false;
    await renderDash().catch((e) => { $("d-err").textContent = t("kh.err.generic", { msg: e.message }); });
    setInterval(() => renderDash().catch(() => {}), 30000);
  }
  I18N.onChange(() => { if (created) renderLinks(); if (!$("dash").hidden) renderDash().catch(() => {}); });
})();
