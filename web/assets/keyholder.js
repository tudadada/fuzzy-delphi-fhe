// Key holder page. The secret key lives only in memory and in the passphrase-locked file
// the holder downloads; reloading the page means loading that file again.
(async function () {
  const t = (k, v) => I18N.t(k, v);
  const { $, api, sid, name } = Fd;
  let me = null, survey = null, holder = null, state = null, unsaved = false, busy = false;

  $("lock").innerHTML = LOCK_ICON;
  const show = (el, on) => { $(el).hidden = !on; };
  const prog = (el, frac) => { show(el, frac !== null); if (frac !== null) $(el).firstElementChild.style.width = `${Math.round(frac * 100)}%`; };
  const fail = (el, e) => { console.error(e); $(el).textContent = t("kh.err.generic", { msg: e.message || String(e) }); };
  const mark = (id, st) => { $(id).classList.toggle("done", st === "done"); $(id).classList.toggle("now", st === "now"); };
  window.addEventListener("beforeunload", (e) => { if (unsaved || busy) { e.preventDefault(); e.returnValue = ""; } });

  async function getHolder() {
    if (!holder) {
      const { m, ccBytes } = await Fd.wasm();
      holder = FdHolder.make({ api, m, ccBytes, sid, member: me });
    }
    return holder;
  }
  const has = (p) => api.has(sid, p);

  // ---------------- setup (status "ceremony")
  async function setup() {
    show("setup", true);
    const mine = await has(`ceremony/${me}/chain.rk`);
    $("t1-wait").textContent = ""; $("t3-wait").textContent = ""; $("t4-wait").textContent = "";
    if (!mine) {
      mark("t1", "now"); mark("t2", ""); mark("t3", ""); mark("t4", "");
      const myTurn = me === 1 || (await has(`ceremony/${me - 1}/chain.rk`));
      show("t1-go", myTurn && !busy);
      if (!myTurn) $("t1-wait").textContent = t("kh.waiting.prev", { n: me - 1 });
      return;
    }
    mark("t1", "done"); show("t1-go", false);
    if (!state) {                               // chain is on the server but the key isn't in memory
      mark("t2", unsaved ? "now" : "done");
      show("loadbox", !unsaved);
      return;
    }
    if (unsaved) { mark("t2", "now"); show("t2-form", true); return; }
    mark("t2", "done"); show("t2-form", false); show("loadbox", false);
    const h = await getHolder();
    const contactsReady = (await Promise.all([1, 2, 3].map((j) => has(`ceremony/${j}/contact.json`)))).every(Boolean);
    if (!(await has(`ceremony/${me}/backup/3.json`))) {
      mark("t3", "now");
      if (!contactsReady) { $("t3-wait").textContent = t("kh.waiting.contacts"); return; }
      $("t3-wait").textContent = t("kh.working");
      await h.backup(state);
      $("t3-wait").textContent = "";
    }
    mark("t3", "done");
    if (!(await has(`ceremony/${me}/mult.bin`))) {
      mark("t4", "now");
      if (!(await has("ceremony/3/chain.rk"))) { $("t4-wait").textContent = t("kh.waiting.last"); return; }
      $("t4-wait").textContent = t("kh.working");
      await h.multShare(state);
    }
    mark("t4", "done");
    $("t4-wait").textContent = t("kh.done.setup");
  }

  $("t1-go").onclick = async () => {
    $("setup-err").textContent = "";
    busy = true; show("t1-go", false);
    $("t1-wait").textContent = t("kh.working");
    try {
      const h = await getHolder();
      state = await h.contact({});
      await h.chain(state, survey.k, (got, total) => prog("t1-prog", total ? got / total : null));
      unsaved = true;
      $("t1-wait").textContent = "";
    } catch (e) { fail("setup-err", e); }
    busy = false; prog("t1-prog", null);
    await refresh();
  };

  $("t2-go").onclick = async () => {
    const a = $("p1").value, b = $("p2").value;
    $("t2-err").textContent = "";
    if (a.length < 10 || a !== b) { $("t2-err").textContent = t("kh.err.pass"); return; }
    $("t2-go").disabled = true;
    try {
      const blob = await FdHolder.exportState(state, a);
      Fd.download(`private-delphi-${sid}-keyholder-${me}.json`, JSON.stringify({ survey: sid, member: me, ...blob }));
      unsaved = false; $("p1").value = ""; $("p2").value = "";
      await refresh();
    } catch (e) { fail("t2-err", e); }
    $("t2-go").disabled = false;
  };

  $("l-go").onclick = async () => {
    $("l-err").textContent = "";
    const f = $("l-file").files[0];
    if (!f) { $("l-err").textContent = t("kh.open.file"); return; }
    try {
      const blob = JSON.parse(await f.text());
      if (blob.survey && (blob.survey !== sid || blob.member !== me)) throw new Error(t("kh.err.token"));
      state = await FdHolder.importState(blob, $("l-pass").value);
      $("l-pass").value = "";
      show("loadbox", false);
      await refresh();
    } catch (e) {
      $("l-err").textContent = /passphrase/.test(e.message) ? t("kh.err.wrongpass") : t("kh.err.generic", { msg: e.message });
    }
  };

  // ---------------- opening (status "opening")
  async function opening() {
    show("opening", true);
    show("loadbox", !state);
    show("o-run", !!state);
    show("absent", !!state);
    if (state) renderAbsent();
  }

  $("o-go").onclick = async () => {
    $("o-err").textContent = ""; $("o-msg").textContent = "";
    busy = true; $("o-go").disabled = true;
    try {
      const h = await getHolder();
      const n = await h.decrypt(state, survey.round, (i, total, b) => {
        prog("o-prog", i / total); $("o-msg").textContent = t("kh.open.progress", { b, n: i, total });
      });
      const batches = await h.batches(survey.round);
      $("o-msg").textContent = batches.length || n ? t("kh.open.done") : t("kh.open.notyet");
    } catch (e) { fail("o-err", e); }
    busy = false; $("o-go").disabled = false; prog("o-prog", null);
  };

  // Two present holders stand in for an absent one: the lower-numbered one rebuilds, the other sends.
  function roles(absent) {
    const present = [1, 2, 3].filter((j) => j !== absent);
    return { rebuilder: present[0], sender: present[1] };
  }
  function renderAbsent() {
    const sel = $("a-who");
    const cur = Number(sel.value) || null;
    sel.innerHTML = [1, 2, 3].filter((j) => j !== me)
      .map((j) => `<option value="${j}"${j === cur ? " selected" : ""}>${esc(t("org.holder.status", { n: j }))}</option>`).join("");
    const r = roles(Number(sel.value));
    $("a-roles").innerHTML = `<p class="small">${esc(me === r.sender ? t("kh.absent.role.send", { n: r.rebuilder }) : t("kh.absent.role.rebuild", { n: r.sender }))}</p>`;
  }
  $("a-who").onchange = renderAbsent;
  $("a-go").onclick = async () => {
    const absent = Number($("a-who").value);
    const r = roles(absent);
    $("a-msg").textContent = t("kh.working");
    busy = true; $("a-go").disabled = true;
    try {
      const h = await getHolder();
      if (me === r.sender) {
        await h.forwardShare(state, absent, r.rebuilder, survey.round);
        $("a-msg").textContent = t("kh.open.done");
      } else {
        const fwd = `rounds/${survey.round}/forward/${r.sender}/${absent}-to-${me}.json`;
        if (!(await has(fwd))) { $("a-msg").textContent = t("kh.absent.waiting", { n: r.sender }); }
        else {
          await h.decryptAs(state, absent, r.sender, survey.round, (i, total, b) => {
            prog("o-prog", i / total); $("a-msg").textContent = t("kh.open.progress", { b, n: i, total });
          });
          $("a-msg").textContent = t("kh.open.done");
        }
      }
    } catch (e) { fail("o-err", e); }
    busy = false; $("a-go").disabled = false; prog("o-prog", null);
  };

  // ---------------- page state
  async function refresh() {
    survey = await api.survey(sid);
    $("s-title").textContent = name(survey.title);
    $("you").textContent = t("kh.you", { n: me });
    $("status").textContent = t("kh.status." + survey.status);
    show("setup", false); show("opening", false); show("idle", false);
    if (survey.status === "ceremony") return setup();
    if (survey.status === "opening") return opening();
    show("loadbox", false);
    show("idle", true);
    $("idle-msg").innerHTML = survey.status === "published"
      ? `<a href="results.html?s=${encodeURIComponent(sid)}">${esc(t("org.viewresults"))}</a>`
      : esc(t(survey.status === "open" ? "kh.done.setup" : "kh.open.notyet"));
  }

  await I18N.init();
  try {
    if (!sid || !Fd.token) throw new Error("no token");
    const w = await api.whoami(sid);
    if (w.role !== "holder") throw new Error("not a holder");
    me = w.member;
  } catch (_) {
    show("fatal", true); $("fatal").textContent = t("kh.err.token");
    return;
  }
  await refresh().catch((e) => fail("setup-err", e));
  setInterval(() => { if (!busy) refresh().catch(() => {}); }, 20000);
  I18N.onChange(() => { if (!busy) refresh().catch(() => {}); });
})();
