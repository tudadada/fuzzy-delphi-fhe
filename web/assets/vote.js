// Expert ballot flow: one criterion at a time -> review -> lock (encrypt) -> send -> receipt.
(async function () {
  const t = (k, v) => I18N.t(k, v);
  const $ = (id) => document.getElementById(id);
  const live = !!(Fd.sid && Fd.token);
  const survey = live ? await Fd.api.survey(Fd.sid) : await (await fetch("data/demo-survey.json")).json();
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
    const r = await BallotCrypto.receipt(bytes);
    try {
      if (live) await Fd.api.ballot(Fd.sid, bytes, r);
    } catch (e) {
      console.error(e); show("review"); stage("st-pick");
      $("err2").textContent = t(e.status === 403 ? "vote.err.link" : e.status === 409
        ? (/already/.test(e.message) ? "vote.err.used" : "vote.err.notopen") : "vote.err.send");
      return;
    }
    $("receipt").textContent = r.slice(0, 16).toUpperCase().match(/.{4}/g).join("-");
    $("receipt").title = r;
    show("sent"); stage("st-sent");
  };
  $("copy").onclick = async () => {
    try { await navigator.clipboard.writeText($("receipt").title); $("copy").textContent = t("vote.copied"); } catch (_) {}
  };

  await I18N.init();
  $("demo-note").hidden = live;
  renderPick();
  if (live) {
    // check the invitation and the round, then load the lock while the expert reads
    const gate = (key) => { show("busy"); $("busy-text").textContent = t(key); };
    try {
      const w = await Fd.api.whoami(Fd.sid);
      if (w.role !== "expert") return gate("vote.err.link");
    } catch (_) { return gate("vote.err.link"); }
    if (survey.status !== "open") return gate("vote.err.notopen");
    $("submit").disabled = true;
    try {
      const { m, ccBytes } = await Fd.wasm();
      BallotCrypto.ready({ m, ccBytes, pkBytes: await Fd.api.get(Fd.sid, "keys/pk.bin") });
    } catch (e) {
      console.error(e); $("err2").textContent = t("vote.err.crypto");
    }
    $("submit").disabled = false;
  }
  I18N.onChange(() => { if (!$("pick").hidden) renderPick(); if (!$("review").hidden) renderReview(); });
})();
