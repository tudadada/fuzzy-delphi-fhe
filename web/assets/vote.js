// Expert ballot flow: one criterion at a time -> review -> lock (encrypt) -> send -> receipt.
(async function () {
  const t = (k, v) => I18N.t(k, v);
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const surveyUrl = params.get("survey") || "data/demo-survey.json";
  const survey = await (await fetch(surveyUrl)).json();
  const K = survey.criteria.length;
  const answers = new Array(K).fill(null);
  let cur = 0;

  $("lock-icon").innerHTML = LOCK_ICON;
  document.querySelector(".lock-slot").innerHTML = LOCK_ICON;
  $("sent-icon").innerHTML = CHECK_ICON;

  const name = (c) => c[I18N.lang] || c.en;
  const show = (id) => ["pick", "review", "busy", "sent"].forEach((s) => { $(s).hidden = s !== id; });
  const stage = (id) => ["st-pick", "st-lock", "st-sent"].forEach((s) => $(s).classList.toggle("on", s === id));

  function renderPick() {
    $("survey-title").textContent = `${name(survey.title)} · ${t("vote.round", { round: survey.round })}`;
    $("progress").textContent = t("vote.progress", { n: cur + 1, total: K });
    $("crit-name").textContent = name(survey.criteria[cur]);
    $("levels").innerHTML = [0, 1, 2, 3, 4].map((l) => `
      <button type="button" role="radio" aria-pressed="${answers[cur] === l}" aria-checked="${answers[cur] === l}" data-l="${l}">
        <span>${esc(t("level." + l))}</span><span class="bar"><i style="width:${(l + 1) * 20}%"></i></span>
      </button>`).join("");
    $("dots").innerHTML = survey.criteria.map((c, k) =>
      `<button type="button" class="${answers[k] !== null ? "done" : ""} ${k === cur ? "current" : ""}"
        data-k="${k}" aria-label="${esc(name(c))}" title="${esc(name(c))}">${k + 1}</button>`).join("");
    $("prev").style.visibility = cur === 0 ? "hidden" : "visible";
    $("next").textContent = cur === K - 1 ? t("vote.review") : t("vote.next");
  }

  function missing() {
    return answers.map((a, k) => (a === null ? k + 1 : null)).filter((x) => x !== null);
  }

  function renderReview() {
    $("review-list").innerHTML = survey.criteria.map((c, k) => `
      <div class="crit" style="display:flex;justify-content:space-between;gap:12px;align-items:center">
        <span>${k + 1}. ${esc(name(c))}</span>
        <span style="display:flex;gap:10px;align-items:center;white-space:nowrap">
          <b>${esc(t("level." + answers[k]))}</b>
          <button type="button" data-edit="${k}" style="padding:4px 10px;font-size:13px">${esc(t("vote.review.edit"))}</button>
        </span>
      </div>`).join("");
  }

  $("levels").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-l]");
    if (!b) return;
    answers[cur] = Number(b.dataset.l);
    $("err").textContent = "";
    if (cur < K - 1) { cur++; }
    renderPick();
  });
  $("dots").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-k]");
    if (b) { cur = Number(b.dataset.k); renderPick(); }
  });
  $("prev").onclick = () => { if (cur > 0) { cur--; renderPick(); } };
  $("next").onclick = () => {
    if (cur < K - 1) { cur++; renderPick(); return; }
    const miss = missing();
    if (miss.length) { $("err").textContent = t("vote.err.missing", { list: miss.join(", ") }); return; }
    renderReview(); show("review");
  };
  $("review-list").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-edit]");
    if (b) { cur = Number(b.dataset.edit); show("pick"); renderPick(); }
  });
  $("back-edit").onclick = () => { show("pick"); renderPick(); };

  $("submit").onclick = async () => {
    $("err2").textContent = "";
    show("busy"); stage("st-lock");
    $("busy-text").textContent = t("vote.locking");
    let bytes;
    try {
      bytes = await BallotCrypto.encrypt(answers);
    } catch (e) {
      console.error(e); show("review"); stage("st-pick"); $("err2").textContent = t("vote.err.crypto"); return;
    }
    $("busy-text").textContent = t("vote.sending");
    try {
      if (survey.submitUrl && !BallotCrypto.demo) {
        const token = params.get("invite") || "";
        const res = await fetch(survey.submitUrl, {
          method: "POST", body: bytes,
          headers: { "content-type": "application/octet-stream", "x-invite": token },
        });
        if (!res.ok) throw new Error(res.status);
      }
    } catch (e) {
      console.error(e); show("review"); stage("st-pick"); $("err2").textContent = t("vote.err.send"); return;
    }
    const r = await BallotCrypto.receipt(bytes);
    $("receipt").textContent = r.slice(0, 16).toUpperCase().match(/.{4}/g).join("-");
    $("receipt").title = r;
    show("sent"); stage("st-sent");
  };
  $("copy").onclick = async () => {
    try { await navigator.clipboard.writeText($("receipt").title); $("copy").textContent = t("vote.copied"); } catch (_) {}
  };

  await I18N.init();
  const real = await BallotCrypto.ready(survey);
  $("demo-note").hidden = real;
  renderPick();
  I18N.onChange(() => { if (!$("pick").hidden) renderPick(); if (!$("review").hidden) renderReview(); });
})();
