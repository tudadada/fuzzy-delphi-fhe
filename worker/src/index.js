// Private Delphi API on Cloudflare Workers (free tier: Workers + KV + D1).
//
// Storage: file bytes in KV (parts <= 20 MB, KV max is 25 MiB), metadata in D1.
// Reads are public: every stored file is either public by design (ciphertexts, public keys,
// results) or encrypted to its recipient (sealed key shares). Writes need a bearer token,
// and every file is write-once, so the bulletin board can't be edited after the fact.
//
// Roles and what they may write (r = round, i = holder number):
//   expert     rounds/{r}/ballots/{receipt}.bin           one per invite per round, while open
//   holder i   ceremony/{i}/...  rounds/{r}/partial/{i}/...  rounds/{r}/forward/{i}/...
//   action     keys/...  rounds/{r}/server/...  rounds/{r}/results.json   (env.ACTION_KEY)
//   admin      create surveys                                             (env.ADMIN_KEY)
//   organizer  change survey status (open, close)

const MAX_PART = 20 * 1024 * 1024;
const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", ...CORS } });
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, PUT, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, x-invite",
};
const err = (status, message) => json({ error: message }, status);

async function sha256hex(s) {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function newToken() {
  const b = new Uint8Array(18);
  crypto.getRandomValues(b);
  return btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_");
}
function newId() {
  const b = new Uint8Array(6);
  crypto.getRandomValues(b);
  return [...b].map((x) => x.toString(36).padStart(2, "0")).join("").slice(0, 10);
}
function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
const bearer = (req) => (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();

async function who(req, env, sid) {
  const tok = bearer(req);
  if (!tok) return null;
  if (env.ACTION_KEY && safeEqual(tok, env.ACTION_KEY)) return { role: "action" };
  const row = await env.DB.prepare("SELECT role, member FROM tokens WHERE hash = ? AND survey = ?")
    .bind(await sha256hex(tok), sid).first();
  return row ? { ...row, hash: await sha256hex(tok) } : null;
}

function canWrite(actor, path, survey) {
  if (!actor) return false;
  const r = survey.round;
  if (actor.role === "action") {
    return path.startsWith("keys/") || path.startsWith(`rounds/${r}/server/`) || path === `rounds/${r}/results.json`;
  }
  if (actor.role === "holder") {
    const i = actor.member;
    return path.startsWith(`ceremony/${i}/`) || path.startsWith(`rounds/${r}/partial/${i}/`) ||
      path.startsWith(`rounds/${r}/forward/${i}/`);
  }
  return false;   // experts use the ballot endpoint
}

const VALID_PATH = /^[a-zA-Z0-9._\/-]{1,200}$/;
const kvKey = (sid, path, idx) => `${sid}/${path}#${idx}`;

async function putPart(env, sid, path, idx, parts, body, size) {
  if (size > MAX_PART) return err(413, `part too large (max ${MAX_PART} bytes)`);
  const now = Date.now();
  await env.DB.prepare("INSERT OR IGNORE INTO files (survey, path, parts, created) VALUES (?, ?, ?, ?)")
    .bind(sid, path, parts, now).run();
  const f = await env.DB.prepare("SELECT parts FROM files WHERE survey = ? AND path = ?").bind(sid, path).first();
  if (f.parts !== parts) return err(409, "part count does not match the first upload");
  if (idx < 0 || idx >= parts) return err(400, "bad part index");
  try {
    await env.DB.prepare("INSERT INTO file_parts (survey, path, idx, size) VALUES (?, ?, ?, ?)")
      .bind(sid, path, idx, size).run();
  } catch (_) {
    return err(409, "this file is already on the board and can't be replaced");
  }
  await env.FILES.put(kvKey(sid, path, idx), body);
  await env.DB.prepare(
    "UPDATE files SET done = (SELECT COUNT(*) FROM file_parts WHERE survey = ?1 AND path = ?2), " +
    "size = (SELECT COALESCE(SUM(size),0) FROM file_parts WHERE survey = ?1 AND path = ?2) WHERE survey = ?1 AND path = ?2")
    .bind(sid, path).run();
  return json({ ok: true, path, idx });
}

async function getSurvey(env, sid) {
  const s = await env.DB.prepare("SELECT * FROM surveys WHERE id = ?").bind(sid).first();
  if (!s) return null;
  return { ...s, title: JSON.parse(s.title), criteria: JSON.parse(s.criteria) };
}

async function surveyView(env, s) {
  const files = await env.DB.prepare("SELECT path, parts, done, size FROM files WHERE survey = ? AND done = parts")
    .bind(s.id).all();
  const ballots = await env.DB.prepare("SELECT COUNT(*) AS n FROM ballots WHERE survey = ? AND round = ?")
    .bind(s.id, s.round).first();
  return { id: s.id, title: s.title, criteria: s.criteria, k: s.k, round: s.round, status: s.status,
    ballots: ballots.n, files: files.results };
}

async function createSurvey(req, env) {
  const body = await req.json().catch(() => null);
  if (!body || !env.ADMIN_KEY || !safeEqual(body.admin_key || "", env.ADMIN_KEY)) return err(403, "wrong admin key");
  const criteria = Array.isArray(body.criteria) ? body.criteria.filter((c) => c && (c.en || c.vi)) : [];
  const experts = Math.min(Math.max(parseInt(body.experts, 10) || 0, 1), 500);
  if (criteria.length < 1 || criteria.length > 800) return err(400, "add between 1 and 800 criteria");
  const id = newId();
  const now = Date.now();
  const tokens = { organizer: newToken(), holders: [newToken(), newToken(), newToken()], experts: [] };
  for (let i = 0; i < experts; i++) tokens.experts.push(newToken());
  const stmts = [env.DB.prepare("INSERT INTO surveys (id, title, criteria, k, created) VALUES (?, ?, ?, ?, ?)")
    .bind(id, JSON.stringify(body.title || {}), JSON.stringify(criteria), criteria.length, now)];
  const add = async (t, role, member = null) =>
    stmts.push(env.DB.prepare("INSERT INTO tokens (hash, survey, role, member) VALUES (?, ?, ?, ?)")
      .bind(await sha256hex(t), id, role, member));
  await add(tokens.organizer, "organizer");
  for (const [i, t] of tokens.holders.entries()) await add(t, "holder", i + 1);
  for (const t of tokens.experts) await add(t, "expert");
  await env.DB.batch(stmts);
  return json({ id, tokens });
}

const NEXT = { ceremony: ["open"], open: ["closed"], closed: ["opening", "open"], opening: ["published"], published: ["open"] };

async function setStatus(req, env, s) {
  const actor = await who(req, env, s.id);
  if (!actor || !["organizer", "action"].includes(actor.role)) return err(403, "not allowed");
  const { status } = await req.json().catch(() => ({}));
  if (!(NEXT[s.status] || []).includes(status)) return err(409, `can't go from ${s.status} to ${status}`);
  if (status === "open" && s.status === "published") {
    await env.DB.prepare("UPDATE surveys SET status = 'open', round = round + 1 WHERE id = ?").bind(s.id).run();
  } else {
    await env.DB.prepare("UPDATE surveys SET status = ? WHERE id = ?").bind(status, s.id).run();
  }
  if (status === "closed" && env.GH_DISPATCH_TOKEN && env.GH_REPO) {
    await fetch(`https://api.github.com/repos/${env.GH_REPO}/actions/workflows/round.yml/dispatches`, {
      method: "POST",
      headers: { authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`, accept: "application/vnd.github+json",
        "user-agent": "private-delphi-worker" },
      body: JSON.stringify({ ref: env.GH_REF || "main", inputs: { survey: s.id, phase: "process" } }),
    }).catch(() => {});
  }
  return json(await surveyView(env, await getSurvey(env, s.id)));
}

async function submitBallot(req, env, s) {
  if (s.status !== "open") return err(409, "voting is not open");
  const actor = await who(req, env, s.id);
  if (!actor || actor.role !== "expert") return err(403, "invitation not recognized");
  const receipt = (new URL(req.url).searchParams.get("receipt") || "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(receipt)) return err(400, "missing receipt");
  const size = parseInt(req.headers.get("content-length") || "0", 10);
  if (!size || size > MAX_PART) return err(413, "ballot size not accepted");
  try {
    await env.DB.prepare("INSERT INTO ballots (survey, round, token, receipt, created) VALUES (?, ?, ?, ?, ?)")
      .bind(s.id, s.round, actor.hash, receipt, Date.now()).run();
  } catch (_) {
    return err(409, "this invitation has already voted in this round");
  }
  // The receipt is the client's SHA-256 of the bytes; the round workflow re-hashes and drops mismatches.
  return putPart(env, s.id, `rounds/${s.round}/ballots/${receipt}.bin`, 0, 1, req.body, size);
}

async function getFile(env, sid, path, url) {
  const f = await env.DB.prepare("SELECT parts, done, size FROM files WHERE survey = ? AND path = ?").bind(sid, path).first();
  if (!f) return err(404, "not found");
  if (url.searchParams.has("meta")) return json(f);
  const idx = parseInt(url.searchParams.get("part") || "0", 10);
  const v = await env.FILES.get(kvKey(sid, path, idx), "stream");
  if (!v) return err(404, "part not found");
  return new Response(v, { headers: { "content-type": "application/octet-stream", "cache-control": "public, max-age=31536000, immutable", ...CORS } });
}

// Work for the scheduled round workflow: finish ceremonies, process closed rounds, advance openings.
async function pending(env) {
  const rows = await env.DB.prepare(
    "SELECT s.id, s.status, s.round, " +
    "(SELECT COUNT(*) FROM files f WHERE f.survey = s.id AND f.path LIKE 'ceremony/_/mult.bin' AND f.done = f.parts) AS mult, " +
    "(SELECT COUNT(*) FROM files f WHERE f.survey = s.id AND f.path = 'keys/evalrot.bin' AND f.done = f.parts) AS keys " +
    "FROM surveys s WHERE s.status IN ('ceremony', 'closed', 'opening')").all();
  const jobs = [];
  for (const r of rows.results) {
    if (r.status === "ceremony" && r.mult === 3 && r.keys === 0) jobs.push({ survey: r.id, phase: "finish" });
    if (r.status === "closed") jobs.push({ survey: r.id, phase: "process" });
    if (r.status === "opening") jobs.push({ survey: r.id, phase: "advance" });
  }
  return json(jobs);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(req);

    const seg = url.pathname.split("/").filter(Boolean);   // ["api", ...]
    try {
      if (req.method === "POST" && seg[1] === "surveys" && seg.length === 2) return await createSurvey(req, env);
      if (req.method === "GET" && seg[1] === "pending" && seg.length === 2) return await pending(env);
      if (seg[1] !== "s" || !seg[2]) return err(404, "not found");
      const s = await getSurvey(env, seg[2]);
      if (!s) return err(404, "survey not found");
      const rest = seg.slice(3);

      if (rest.length === 0 && req.method === "GET") return json(await surveyView(env, s));
      if (rest[0] === "status" && req.method === "POST") return await setStatus(req, env, s);
      if (rest[0] === "ballot" && req.method === "POST") return await submitBallot(req, env, s);
      if (rest[0] === "whoami" && req.method === "GET") {
        const a = await who(req, env, s.id);
        return a ? json({ role: a.role, member: a.member ?? null }) : err(403, "token not recognized");
      }
      if (rest[0] === "board" && req.method === "GET") {
        const round = parseInt(url.searchParams.get("round") || s.round, 10);
        const rows = await env.DB.prepare("SELECT receipt, created FROM ballots WHERE survey = ? AND round = ? ORDER BY created, receipt")
          .bind(s.id, round).all();
        return json({ survey: s.id, round, status: s.status, ballots: rows.results });
      }
      if (rest[0] === "list" && req.method === "GET") {
        const prefix = url.searchParams.get("prefix") || "";
        const rows = await env.DB.prepare("SELECT path, parts, done, size FROM files WHERE survey = ? AND path LIKE ? ORDER BY path")
          .bind(s.id, prefix.replace(/[%_]/g, "") + "%").all();
        return json(rows.results);
      }
      if (rest[0] === "f") {
        const path = rest.slice(1).join("/");
        if (!VALID_PATH.test(path) || path.includes("..")) return err(400, "bad path");
        if (req.method === "GET") return await getFile(env, s.id, path, url);
        if (req.method === "PUT") {
          const actor = await who(req, env, s.id);
          if (!canWrite(actor, path, s)) return err(403, "not allowed to write here");
          const parts = parseInt(url.searchParams.get("parts") || "1", 10);
          const idx = parseInt(url.searchParams.get("part") || "0", 10);
          const size = parseInt(req.headers.get("content-length") || "0", 10);
          if (!size) return err(411, "content-length required");
          return await putPart(env, s.id, path, idx, parts, req.body, size);
        }
      }
      return err(404, "not found");
    } catch (e) {
      return err(500, "server error");
    }
  },
};
