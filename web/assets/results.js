// Results view: score bar against the keep line, agreement share, and the fuzzy range in words.
(async function () {
  const t = (k, v) => I18N.t(k, v);
  const $ = (id) => document.getElementById(id);
  // ?s=ID shows the latest published round of a real survey; without it, the demo data
  const live = !!Fd.sid;
  const survey = live ? await Fd.api.survey(Fd.sid) : await (await fetch("data/demo-survey.json")).json();
  let res = null;
  try {
    if (live) {
      const round = survey.status === "published" ? survey.round : survey.round - 1;
      if (round >= 1) res = await Fd.api.getJsonFile(Fd.sid, `rounds/${round}/results.json`);
      if (res) survey.round = res.round;
    } else {
      const r = await fetch("data/demo-results.json");
      if (r.ok) res = await r.json();
    }
  } catch (_) {}

  const name = (c) => c[I18N.lang] || c.en;
  const num = (x) => x.toLocaleString(I18N.lang === "vi" ? "vi-VN" : "en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const word = (x) => t("level." + Math.max(0, Math.min(4, Math.round(x * 4))));

  // Small triangle: where the group's fuzzy view sits on the Very low .. Very high scale
  function tri([l, m, u], ok) {
    const X = (v) => 4 + v * 292;
    const col = ok ? "var(--ok-fill)" : "var(--bad-fill)";
    return `<svg class="tri" viewBox="0 0 300 34" preserveAspectRatio="none" aria-hidden="true">
      <line x1="4" y1="30" x2="296" y2="30" stroke="var(--border-strong)" stroke-width="1"/>
      ${[0, 0.25, 0.5, 0.75, 1].map((v) => `<line x1="${X(v)}" y1="27" x2="${X(v)}" y2="33" stroke="var(--border-strong)"/>`).join("")}
      <polygon points="${X(l)},30 ${X(m)},4 ${X(u)},30" fill="${col}" fill-opacity=".25" stroke="${col}" stroke-width="1.5"/>
    </svg>`;
  }

  function render() {
    $("survey-title").textContent = name(survey.title);
    $("title").textContent = t("results.title", { round: survey.round });
    if (!res) { $("empty").hidden = false; $("body").hidden = true; return; }
    $("empty").hidden = true; $("body").hidden = false;
    $("opened").innerHTML = `${LOCK_ICON}<span>${esc(t("results.opened", { n: res.opened_by }))}</span>`;
    $("m-voted").textContent = `${res.voted}`;
    $("m-invalid").textContent = `${res.invalid}`;
    $("m-kept").textContent = `${res.criteria.filter((c) => c.keep).length}/${res.criteria.length}`;
    $("board").href = res.board_url || "#";
    $("rows").innerHTML = res.criteria.map((c) => {
      const pct = Math.round(c.agree_share * 100);
      const [l, m, u] = c.fuzzy_mean;
      return `<div class="crit">
        <div class="crit-head"><span>${esc(name(survey.criteria[c.criterion]))}</span>
          <span class="tag ${c.keep ? "ok" : "bad"}">${esc(t(c.keep ? "results.keep" : "results.drop"))}</span></div>
        <div class="meter" role="img" aria-label="${esc(t("results.score"))} ${num(c.score)}">
          <i style="width:${(c.score * 100).toFixed(1)}%;background:var(${c.keep ? "--ok-fill" : "--bad-fill"})"></i><span class="line"></span></div>
        <div class="crit-meta"><span>${esc(t("results.score"))} ${num(c.score)}</span>
          <span>${esc(t("results.agree", { pct }))} · ${c.consensus ? CHECK_ICON.replace('class="icon"', 'class="icon" style="width:14px;height:14px;vertical-align:-2px"') + " " + esc(t("results.agreed")) : esc(t("results.round2"))}</span></div>
        ${tri(c.fuzzy_mean, c.keep)}
        <div class="crit-meta"><span>${esc(t("results.range", { low: word(l), high: word(u), mid: word(m) }))}</span></div>
      </div>`;
    }).join("");
  }

  await I18N.init();
  render();
  I18N.onChange(render);
})();
