// Daily Mind Challenge web app: serves puzzles from pool/, grades with Gemini, writes state back via the GitHub API.
// Mirrors engine/roll.py and engine/dmc.py (pick, hint, close); keep the file formats in sync with them.
"use strict";

const OWNER = "Corvus4012", REPO = "daily-mind-challenge-", BRANCH = "main";
const TZ = "Asia/Ho_Chi_Minh";
const DOMAINS = {1: "Logic & ngụy biện", 2: "Xác suất & thống kê đời thường", 3: "Kinh tế vi mô đời sống",
  4: "Tâm lý học nhận thức", 5: "Khoa học & phương pháp luận", 6: "Ngôn ngữ & ý nghĩa", 7: "Đạo đức & quyết định",
  8: "Toán trong đời", 9: "Lịch sử như bài học quyết định", 10: "Nghệ thuật & thiết kế",
  11: "Cross-cultural reasoning", 12: "Media & information literacy"};
const TAG_LABEL = {reason: "🧠 Reason", lookup: "📖 Lookup", explore: "🔍 Explore"};
const TAGS = [["reason", 0.80], ["lookup", 0.15], ["explore", 0.05]];
const RESULT_LABEL = {correct: "Đạt", partial: "Đúng một phần", incorrect: "Chưa đạt", explore: "Explore", skipped: "Bỏ qua"};
const WARMUP_DAYS = 3, WINDOW = 5, REVIEW_DUE_AFTER_DAYS = 2;

// ---------- settings ----------
const cfg = {
  get gh() { return localStorage.getItem("dmc.gh") || ""; },
  get gemini() { return localStorage.getItem("dmc.gemini") || ""; },
  get model() { return localStorage.getItem("dmc.model") || "gemini-flash-latest"; },
};

// ---------- small helpers ----------
const $ = (s) => document.querySelector(s);
const md = (t) => DOMPurify.sanitize(marked.parse(t || ""));
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
function toast(msg, ms = 3500) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), ms); }
function today() { return new Intl.DateTimeFormat("en-CA", {timeZone: TZ}).format(new Date()); }
function vnDate(iso) { const [y, m, d] = iso.split("-"); return `${d}/${m}/${y}`; }
function daysBetween(a, b) { return Math.round((Date.parse(b) - Date.parse(a)) / 86400000); }
const b64enc = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));
const b64dec = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\s/g, "")), (c) => c.charCodeAt(0)));

// Seeded RNG so re-opening the page on the same day gives the same roll.
function rngFrom(seed) {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) { h = Math.imul(h ^ seed.charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); }
  let a = h >>> 0;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// ---------- GitHub ----------
async function gh(path, opts = {}) {
  if (!cfg.gh) throw new Error("Chưa nhập GitHub token (tab Cài đặt).");
  const r = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}${path}`, {
    ...opts, cache: "no-store",
    headers: {Authorization: `Bearer ${cfg.gh}`, Accept: "application/vnd.github+json", ...(opts.headers || {})},
  });
  if (!r.ok) throw new Error(`GitHub ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.status === 204 ? null : r.json();
}
async function readText(path) {
  try { const f = await gh(`/contents/${path}?ref=${BRANCH}`); return b64dec(f.content); }
  catch (e) { if (String(e.message).includes("404")) return null; throw e; }
}
async function readJSON(path) { const t = await readText(path); return t == null ? null : JSON.parse(t); }
async function listDir(path) {
  try { return await gh(`/contents/${path}?ref=${BRANCH}`); }
  catch (e) { if (String(e.message).includes("404")) return []; throw e; }
}
// One commit with several file writes / deletions (content null = delete).
async function commit(message, changes) {
  const ref = await gh(`/git/ref/heads/${BRANCH}`);
  const base = await gh(`/git/commits/${ref.object.sha}`);
  const tree = await gh(`/git/trees`, {method: "POST", body: JSON.stringify({
    base_tree: base.tree.sha,
    tree: changes.map((c) => c.content == null
      ? {path: c.path, mode: "100644", type: "blob", sha: null}
      : {path: c.path, mode: "100644", type: "blob", content: c.content}),
  })});
  const msg = `${message}\n\nCommitted from the Daily Mind Challenge web app.`;
  const cm = await gh(`/git/commits`, {method: "POST", body: JSON.stringify({message: msg, tree: tree.sha, parents: [ref.object.sha]})});
  await gh(`/git/refs/heads/${BRANCH}`, {method: "PATCH", body: JSON.stringify({sha: cm.sha})});
}
const jsonFile = (o) => JSON.stringify(o, null, 2) + "\n";

// ---------- engine (port of roll.py / dmc.py) ----------
async function loadHistory() {
  const t = (await readText("state/history.jsonl")) || "";
  return t.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));
}
function currentLevel(hist) {
  const graded = hist.filter((h) => ["correct", "partial", "incorrect"].includes(h.result));
  if (hist.length < WARMUP_DAYS) return 2;
  const recent = graded.slice(-WINDOW);
  if (recent.length < 3) return 2;
  const score = (h) => h.result === "correct" ? (h.hints_used ? 0.75 : 1) : h.result === "partial" ? 0.5 : 0;
  let level = recent[recent.length - 1].base_level;
  const avg = recent.reduce((s, h) => s + score(h), 0) / recent.length;
  if (avg >= 0.8) level += 1; else if (avg < 0.4) level -= 1;
  return Math.max(1, Math.min(5, level));
}
function roll(t, hist, rng) {
  const base = currentLevel(hist);
  let lvl, mode;
  if (hist.length < WARMUP_DAYS) { lvl = 2; mode = "warmup"; }
  else { const r = rng(); if (r < 0.7) { lvl = base; mode = "core"; } else if (r < 0.9) { lvl = Math.min(5, base + 1); mode = "stretch"; } else { lvl = Math.min(5, base + 2); mode = "wildcard"; } }
  const r2 = rng(); let acc = 0, tag = "reason";
  for (const [name, p] of TAGS) { acc += p; if (r2 < acc) { tag = name; break; } }
  const blocked = new Set(hist.slice(-2).map((h) => h.domain_id));
  const lastUsed = {}; hist.forEach((h, i) => (lastUsed[h.domain_id] = i));
  const eligible = Object.keys(DOMAINS).map(Number).filter((d) => !blocked.has(d))
    .map((d) => [d, lastUsed[d] ?? -1, rng()]).sort((a, b) => a[1] - b[1] || a[2] - b[2]).map((x) => x[0]);
  return {date: t, current_level: base, rolled_level: lvl, level_mode: mode, rolled_tag: tag, eligible_domain_ids: eligible};
}
function dueSkills(hist, onDate) {
  const due = new Map();
  hist.forEach((h, i) => {
    for (const s of h.skills_missed || []) {
      const laterOk = hist.slice(i + 1).some((g) => (g.skills || []).includes(s) && !(g.skills_missed || []).includes(s));
      if (!laterOk && daysBetween(h.date, onDate) >= REVIEW_DUE_AFTER_DAYS) { if (!due.has(s)) due.set(s, h.date); }
      else if (laterOk) due.delete(s);
    }
  });
  return [...due.keys()];
}
async function loadPool() {
  const entries = (await listDir("pool")).filter((e) => e.name.endsWith(".json"));
  return Promise.all(entries.map(async (e) => ({...(await readJSON(e.path)), _path: e.path})));
}

// ---------- state ----------
let S = {hist: [], cur: null, poolCount: 0};

async function refresh() {
  if (!cfg.gh) { showTab("settings"); $("#status").textContent = "Nhập GitHub token và Gemini key để bắt đầu."; return; }
  $("#status").textContent = "Đang tải…";
  const [hist, cur, pool] = await Promise.all([loadHistory(), readJSON("state/current.json"), listDir("pool")]);
  S = {hist, cur, poolCount: pool.filter((e) => e.name.endsWith(".json")).length};
  $("#status").textContent = `${vnDate(today())} · Level nền ${currentLevel(hist)} · Pool còn ${S.poolCount} đề`;
  renderToday();
}

function puzzleCard(c) {
  const hints = (c.hints || []).slice(0, c.hints_revealed || 0)
    .map((h, i) => `<div class="hint"><b>Gợi ý ${i + 1}/${c.hints.length}:</b> ${md(h)}</div>`).join("");
  return `<div class="card">
    <div class="meta">📅 ${vnDate(c.date)} · ${TAG_LABEL[c.tag] || c.tag} · ${esc(DOMAINS[c.domain_id])} · Level ${c.level} · ⏱ ${c.est_minutes} phút</div>
    ${md(c.challenge_md)}${hints}</div>`;
}

function renderToday() {
  const t = today(), c = S.cur, el = $("#today");
  if (!c || (c.status === "submitted" && c.date !== t)) {
    el.innerHTML = `<p>Chưa có đề hôm nay.</p><div class="row"><button id="pick">Nhận đề hôm nay</button></div>`;
    $("#pick").onclick = () => run(() => pick(false));
    return;
  }
  if (c.status === "open") {
    const old = c.date !== t ? `<p class="muted">Đề này của ngày ${vnDate(c.date)} và chưa nộp. Làm tiếp, hoặc bỏ để nhận đề hôm nay.</p>` : "";
    const left = (c.hints?.length || 0) - (c.hints_revealed || 0);
    el.innerHTML = `${old}${puzzleCard(c)}
      <div class="row">${left > 0 ? `<button class="secondary" id="hint">Mở gợi ý (${c.hints_revealed + 1}/${c.hints.length})</button>` : `<span class="muted">Đã mở hết gợi ý.</span>`}
      ${old ? `<button class="secondary" id="skip">Bỏ đề này</button>` : ""}</div>
      <label>Câu trả lời của bạn<textarea id="answer" rows="10"></textarea></label>
      <div class="row"><button id="submit">Nộp bài</button></div>`;
    const key = `dmc.draft.${c.pool_id}`;
    $("#answer").value = localStorage.getItem(key) || "";
    $("#answer").oninput = (e) => localStorage.setItem(key, e.target.value);
    if (left > 0) $("#hint").onclick = () => run(hint);
    if (old) $("#skip").onclick = () => confirm("Bỏ đề này (ghi là bỏ qua)?") && run(skip);
    $("#submit").onclick = () => run(submit);
    return;
  }
  // submitted today
  el.innerHTML = `${puzzleCard(c)}<div id="fb">${c._feedback_html || ""}</div>
    <p>Hôm nay đã xong. Hẹn mai!</p>
    <div class="row"><button class="secondary" id="extra">Làm thêm một đề</button>
    <button class="secondary" id="appeal">Phản đối cách chấm</button></div>`;
  if (!c._feedback_html) loadFeedback(c);
  $("#extra").onclick = () => run(() => pick(true));
  $("#appeal").onclick = () => run(appeal);
}

async function run(fn) {
  document.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try { await fn(); } catch (e) { console.error(e); toast(e.message || String(e), 8000); }
  finally { document.querySelectorAll("button").forEach((b) => (b.disabled = false)); }
}

// ---------- actions ----------
async function pick(extra) {
  const t = today();
  const hist = await loadHistory();
  const r = roll(t, hist, rngFrom(t + (extra ? "-extra" : "")));
  const due = new Set(dueSkills(hist, t));
  const rank = Object.fromEntries(r.eligible_domain_ids.map((d, i) => [d, i]));
  let pool = await loadPool();
  if (!pool.length) throw new Error("Pool hết đề. Lần chạy hằng tuần sẽ bổ sung.");
  // Prefer an unblocked domain; if none in the pool, accept any domain rather than serve nothing.
  let cands = pool.filter((p) => p.domain_id in rank);
  if (!cands.length) cands = pool;
  const key = (p) => [Math.abs(p.level - r.rolled_level), p.tag !== r.rolled_tag ? 1 : 0,
    (p.skills || []).some((s) => due.has(s)) ? 0 : 1, rank[p.domain_id] ?? 99, p.id];
  cands.sort((a, b) => { const ka = key(a), kb = key(b); for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] < kb[i] ? -1 : 1; return 0; });
  const best = cands[0];
  const cur = {date: t, pool_id: best.id, domain_id: best.domain_id, tag: best.tag, level: best.level,
    base_level: r.current_level, rolled_level: r.rolled_level, level_mode: r.level_mode, est_minutes: best.est_minutes,
    format: best.format, skills: best.skills, challenge_md: best.challenge_md, hints: best.hints, hints_revealed: 0,
    answer_key_b64: best.answer_b64, rubric_b64: best.rubric_b64, review: best.review, status: "open", extra};
  await commit(`Serve challenge ${t}${extra ? " (extra)" : ""}`, [
    {path: "state/current.json", content: jsonFile(cur)}, {path: best._path, content: null}]);
  await refresh();
}

async function hint() {
  const cur = await readJSON("state/current.json");
  if (cur.status !== "open" || cur.hints_revealed >= cur.hints.length) return refresh();
  cur.hints_revealed += 1;
  await commit(`Hint ${cur.hints_revealed} for ${cur.date}`, [{path: "state/current.json", content: jsonFile(cur)}]);
  await refresh();
}

async function skip() {
  const cur = await readJSON("state/current.json");
  await closeChallenge(cur, {result: "skipped", skills_missed: [], notes: "Bỏ qua trên web."}, null);
  await refresh();
}

function historyEntry(cur, g) {
  return {date: cur.date, domain_id: cur.domain_id, tag: cur.tag, level: cur.level, base_level: cur.base_level,
    result: g.result, hints_used: cur.hints_revealed || 0, format: cur.format, skills: cur.skills || [],
    skills_missed: g.skills_missed, notes: g.notes || "", pool_id: cur.pool_id, extra: !!cur.extra, domain: DOMAINS[cur.domain_id]};
}
async function closeChallenge(cur, g, archiveExtra) {
  const histText = (await readText("state/history.jsonl")) || "";
  const entry = historyEntry(cur, g);
  const name = cur.date + (cur.extra ? "-extra" : "");
  const changes = [
    {path: "state/history.jsonl", content: histText.replace(/\n*$/, "\n") + JSON.stringify(entry) + "\n"},
    {path: "state/current.json", content: jsonFile({...cur, status: "submitted"})},
  ];
  if (archiveExtra) changes.push({path: `state/archive/${name}.json`, content: jsonFile({...cur, status: "submitted", ...archiveExtra,
    result: g.result, skills_missed: g.skills_missed, notes: entry.notes})});
  await commit(`Submit challenge ${cur.date}: ${g.result}`, changes);
}

// ---------- Gemini ----------
async function gemini(system, user, schema) {
  if (!cfg.gemini) throw new Error("Chưa nhập Gemini API key (tab Cài đặt).");
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(cfg.model)}:generateContent`, {
    method: "POST", headers: {"Content-Type": "application/json", "x-goog-api-key": cfg.gemini},
    body: JSON.stringify({
      systemInstruction: {parts: [{text: system}]},
      contents: [{role: "user", parts: [{text: user}]}],
      generationConfig: {temperature: 0.2, responseMimeType: "application/json", responseSchema: schema},
    }),
  });
  if (!r.ok) throw new Error(`Gemini ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const d = await r.json();
  const text = d.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("") || "";
  return JSON.parse(text);
}

const GRADER_RULES = `Bạn là người chấm bài cho "Daily Mind Challenge", một bài tư duy mỗi ngày. Viết tiếng Việt, thẳng, cụ thể, không phán xét.
Không bao giờ dùng các từ "quiz", "test", "exam"; gọi là "challenge" hoặc "đề". Không cho điểm số kiểu 6/10.
Quy tắc chấm (bắt buộc):
- Chấm từng câu theo rubric: đạt / một phần / chưa đạt. Gộp thành kết quả theo đúng quy tắc gộp trong rubric.
- Câu dạng bảng: chấm từng ô; ô then chốt và ô thường; Đạt = đúng mọi ô then chốt và ≥80% ô thường; Một phần = sai tối đa 1 ô then chốt hoặc <80% ô thường.
- Ô lệch đáp án nhưng có lập luận đúng dựa trên tiền đề của đề → tính đúng. Lý do khác đáp án nhưng đúng logic → đạt.
- Lỗi dây chuyền: số sai ở câu trước kéo theo câu sau mà phương pháp câu sau đúng → chỉ trừ ở câu gốc.
- Lý do đúng nhưng để ngầm → vẫn đạt, nhưng phải viết lại bản tường minh trong "explicit_version".
- Người học dùng mô hình khác mô hình đề cho → trừ ở câu đó, chỉ ra định nghĩa trong đề.
- Nhận xét từng câu: đúng ở đâu → gãy ở đâu → cơ chế phía sau. Dùng số của đề.
- "takeaway": một nguyên tắc chuyển giao được; nếu nối với một lỗi cũ trong hồ sơ người học thì nói ra mối nối.
- "skills_missed": chỉ chọn trong danh sách kỹ năng của đề, kỹ năng người học chưa thể hiện được.
- "notes": 1 dòng cho người ra đề: điểm mạnh và mẫu lỗi.`;

const GRADE_SCHEMA = {type: "object", properties: {
  questions: {type: "array", items: {type: "object", properties: {
    label: {type: "string"}, verdict: {type: "string", enum: ["đạt", "một phần", "chưa đạt"]},
    comment: {type: "string"}, explicit_version: {type: "string"}}, required: ["label", "verdict", "comment"]}},
  result: {type: "string", enum: ["correct", "partial", "incorrect", "explore"]},
  headline: {type: "string"}, takeaway: {type: "string"},
  skills_missed: {type: "array", items: {type: "string"}}, notes: {type: "string"}},
  required: ["questions", "result", "headline", "takeaway", "skills_missed", "notes"]};

async function submit() {
  const answer = $("#answer").value.trim();
  if (!answer) throw new Error("Viết câu trả lời trước khi nộp.");
  const cur = await readJSON("state/current.json");
  if (cur.status !== "open") return refresh();
  const lessons = (await readText("state/lessons.md")) || "";
  const profile = (lessons.split("## Hồ sơ người học")[1] || "").split("## Ghi chú hệ thống")[0].trim();
  toast("Đang chấm…", 20000);
  const g = await gemini(GRADER_RULES, [
    `ĐỀ (domain ${DOMAINS[cur.domain_id]}, level ${cur.level}, đã mở ${cur.hints_revealed} gợi ý):\n${cur.challenge_md}`,
    `ĐÁP ÁN:\n${b64dec(cur.answer_key_b64)}`, `RUBRIC:\n${b64dec(cur.rubric_b64)}`,
    `KỸ NĂNG CỦA ĐỀ: ${(cur.skills || []).join(", ")}`, `HỒ SƠ NGƯỜI HỌC:\n${profile}`,
    `CÂU TRẢ LỜI CỦA NGƯỜI HỌC:\n${answer}`].join("\n\n"), GRADE_SCHEMA);
  g.skills_missed = (g.skills_missed || []).filter((s) => (cur.skills || []).includes(s));
  const grading = g.questions.map((q) => `${q.label}: ${q.verdict} — ${q.comment}`).join("\n");
  await closeChallenge(cur, g, {user_answer: answer, grading, feedback: g, grader: `gemini:${cfg.model}`});
  localStorage.removeItem(`dmc.draft.${cur.pool_id}`);
  await refresh();
  S.cur._feedback_html = feedbackHtml(g, cur);
  renderToday();
}

function feedbackHtml(g, cur) {
  const cls = (v) => v === "đạt" ? "v-dat" : v === "một phần" ? "v-mot" : "v-chua";
  const qs = g.questions.map((q) => `<h3>${esc(q.label)} <span class="verdict ${cls(q.verdict)}">${esc(q.verdict)}</span></h3>
    ${md(q.comment)}${q.explicit_version ? `<blockquote>${md("**Đủ ý thì viết thế này:** " + q.explicit_version)}</blockquote>` : ""}`).join("");
  return `<div class="card"><p><b>${esc(RESULT_LABEL[g.result] || g.result)}</b> · ${cur.hints_revealed || 0} gợi ý. ${esc(g.headline)}</p>
    ${qs}<p><b>Rút ra:</b> ${esc(g.takeaway)}</p>
    <p class="muted">Chấm bởi ${esc(cfg.model)}. Lần chạy hằng tuần sẽ chấm lại độc lập; chỗ nào khác sẽ được đưa ra bàn.</p></div>`;
}
async function loadFeedback(c) {
  const a = await readJSON(`state/archive/${c.date}${c.extra ? "-extra" : ""}.json`).catch(() => null);
  if (a?.feedback && S.cur === c) { c._feedback_html = feedbackHtml(a.feedback, c); $("#fb").innerHTML = c._feedback_html; }
  else if (a?.grading && S.cur === c) { $("#fb").innerHTML = `<div class="card"><p><b>${esc(RESULT_LABEL[a.result] || a.result)}</b></p>${md(a.grading)}</div>`; }
}

async function appeal() {
  const text = prompt("Bạn phản đối điểm nào, vì sao?");
  if (!text) return;
  const c = S.cur, path = `state/archive/${c.date}${c.extra ? "-extra" : ""}.json`;
  const a = await readJSON(path);
  if (!a) throw new Error("Không tìm thấy bài đã lưu.");
  a.appeal = [a.appeal, `(${today()}) ${text}`].filter(Boolean).join("\n");
  await commit(`Appeal for ${c.date}`, [{path, content: jsonFile(a)}]);
  toast("Đã ghi lời phản đối. Lần chạy hằng tuần sẽ xét lại.");
}

// ---------- talk tab ----------
const ASK_RULES = `Bạn trả lời câu hỏi về cách hiểu một đề tư duy, bằng tiếng Việt. Bạn KHÔNG có đáp án và không được gợi ý hướng giải.
- Hỏi về hình thức trả lời hoặc câu chữ mơ hồ: trả lời rõ, nêu cách đọc đúng mà không nghiêng về đáp án nào.
- Hỏi điều đề đã nói rõ, hoặc trả lời sẽ làm lộ hướng giải: từ chối ngắn gọn, chỉ ra đoạn đề liên quan, nhắc dùng gợi ý nếu cần.
- Ví dụ minh hoạ (nếu có) phải nằm ngoài đề và không chung cơ chế với lời giải.
- Không dùng các từ "quiz", "test", "exam".
Trả về JSON {"answer": "...", "declined": true|false, "wording_issue": true|false}. wording_issue = true khi câu chữ của đề thật sự mơ hồ.`;

async function ask() {
  const q = $("#ask-text").value.trim();
  if (!q) return;
  const cur = await readJSON("state/current.json");
  if (!cur || cur.status !== "open") throw new Error("Không có đề đang mở.");
  const r = await gemini(ASK_RULES, `ĐỀ:\n${cur.challenge_md}\n\nCÂU HỎI:\n${q}`, {type: "object",
    properties: {answer: {type: "string"}, declined: {type: "boolean"}, wording_issue: {type: "boolean"}}, required: ["answer", "declined", "wording_issue"]});
  $("#ask-out").hidden = false; $("#ask-out").innerHTML = md(r.answer);
  if (r.wording_issue) await appendInbox(`**[Câu chữ mơ hồ — đề ${cur.date}]** ${q}\n\n> ${r.answer.replace(/\n/g, "\n> ")}`);
}

async function appendInbox(text) {
  const cur = (await readText("state/inbox.md")) || "# Hộp thư /discuss\n\nGóp ý từ web; lần chạy hằng tuần trả lời ngay dưới mỗi mục.\n";
  await commit(`Inbox: ${today()}`, [{path: "state/inbox.md", content: cur.replace(/\n*$/, "\n") + `\n## ${today()}\n${text}\n`}]);
  await loadInbox();
}
async function discuss() {
  const t = $("#discuss-text").value.trim();
  if (!t) return;
  await appendInbox(t);
  $("#discuss-text").value = "";
  toast("Đã gửi. Lần chạy hằng tuần sẽ trả lời ở đây.");
}
async function loadInbox() {
  const t = await readText("state/inbox.md");
  $("#inbox").innerHTML = t ? md(t) : `<p class="muted">Chưa có góp ý nào.</p>`;
}

// ---------- wiring ----------
function showTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  for (const n of ["today", "talk", "settings"]) $(`#tab-${n}`).hidden = n !== name;
  if (name === "talk" && cfg.gh) loadInbox().catch((e) => toast(e.message));
}
document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
$("#ask-btn").onclick = () => run(ask);
$("#discuss-btn").onclick = () => run(discuss);
$("#cfg-gh").value = cfg.gh; $("#cfg-gemini").value = cfg.gemini; $("#cfg-model").value = localStorage.getItem("dmc.model") || "";
$("#cfg-save").onclick = () => {
  localStorage.setItem("dmc.gh", $("#cfg-gh").value.trim());
  localStorage.setItem("dmc.gemini", $("#cfg-gemini").value.trim());
  const m = $("#cfg-model").value.trim(); m ? localStorage.setItem("dmc.model", m) : localStorage.removeItem("dmc.model");
  $("#cfg-msg").textContent = "Đã lưu.";
  showTab("today"); run(refresh);
};
run(refresh);
