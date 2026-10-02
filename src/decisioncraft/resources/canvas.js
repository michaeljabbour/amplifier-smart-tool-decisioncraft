/* Decisioncraft canvas engine. Reads a decision model from #dc-model and draws it.
   No outside requests. Plain DOM, no libraries.
   The page: one quiet top bar; a numbered story list on the left; the map in the middle;
   a detail panel on the right; zoom buttons bottom right; a walk-through card.
   Maps that hold a plan can be read three ways: Today, Planned, and What changes (one map
   where each box says whether it is new, changed or goes away), plus Side by side. */
/* Inside an MCP App host (Claude, ChatGPT, VS Code, Cursor) the page has no model until the
   host delivers the tool result, so the view sets window.DC_DEFER and calls __dcBoot itself.
   window.DC_HOST, when set, is that host bridge: saveReview(review) and askExperts(note,
   roles) go through the host's tools/call instead of a download or a local session. */
window.__dcBoot = function () {
"use strict";
const HOST = window.DC_HOST || null;

const $ = (s, r) => (r || document).querySelector(s);
const read = id => { const n = document.getElementById(id); return n && n.textContent.trim() ? JSON.parse(n.textContent) : null; };
const MODEL = read("dc-model");
const SESSION = read("dc-session");
const MERGED = read("dc-merged");
const SINCE = read("dc-since");
const META = read("dc-meta") || {};

const STATUS = {works:"Works today", partial:"Partly there", missing:"Missing", planned:"Planned", addon:"Add-on", unsure:"Not sure"};
const URG = {must:"Must decide", should:"Should decide", info:"For information"};
const URG_ORDER = {must:0, should:1, info:2};
const FEEL = {good:"Feels good", ok:"Mixed feelings", bad:"Feels bad"};
const DSTATUS = {open:"Open", decided:"Decided", deferred:"Deferred"};
const DEFAULT_ROLES = [
  {id:"designer",label:"Designer",color:"#e86a92"},{id:"analyst",label:"Analyst",color:"#4f7fd8"},
  {id:"engineer",label:"Engineer",color:"#2f9e6a"},{id:"owner",label:"Product owner",color:"#8a5cd6"},
  {id:"security",label:"Security and privacy",color:"#d1543f"},{id:"voice",label:"Customer voice",color:"#d99a1e"},
  {id:"agent",label:"AI agent teammate",color:"#1f9aa6"},{id:"finance",label:"Finance",color:"#7a7a72"}];
const KIND = {"system-journeys":"journeys","customer-journey":"journeys","service-blueprint":"journeys",
  "decision-chain":"chain","opportunity-tree":"tree","scoring-table":"scoring","cost-over-time":"costs"};
const TREE_LEVELS = ["What we want","What needs attention","Possible next step","How we will check"];
const MIN_Z = 0.25, MAX_Z = 2.2;
const STORY_W = 320, PANEL_W = 480, TOP_H = 52;

const ROLES = (MODEL.roles && MODEL.roles.length ? MODEL.roles : DEFAULT_ROLES);
const ROLE = Object.fromEntries(ROLES.map(r => [r.id, r]));
const EVID = Object.fromEntries((MODEL.evidence || []).map(e => [e.id, e]));
const SRC = Object.fromEntries((MODEL.sources || []).map(s => [s.id, s]));
const GAPS = MODEL.gaps || [];
const NOTES = MODEL.notes || [];
const DECISIONS = MODEL.decisions || [];
const GLOSS = MODEL.glossary || {};
const DOT_BUDGET = MODEL.dots || 5;
const FRESH_DAYS = MODEL.freshness_days || 60;
const KEY = "decisioncraft:" + (SESSION ? SESSION.id : META.fingerprint || MODEL.title);

const sinceAdded = new Set((SINCE && SINCE.added || []).map(x => x.id));
const sinceChanged = Object.fromEntries((SINCE && SINCE.changed || []).map(x => [x.id, x.fields]));

/* ---------- saved state ---------- */
let saved = {}, storageOK = true;
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { saved = {}; storageOK = false; }
const seed = SESSION ? {answers:SESSION.review.answers || {}, votes:SESSION.review.dots || {},
  decisions:SESSION.review.decisions || {}, reviewer:SESSION.review.reviewer || "", myNotes:SESSION.review.notes || [],
  weights:SESSION.review.weights || {}, whatifs:SESSION.review.whatifs || []} : {};
/* The model can choose how the map first opens (display.notes_on_map, display.start_view).
   Anything the reviewer picks later in View is saved here and wins from then on. */
const DISPLAY = MODEL.display || {};
const S = Object.assign({map:0, mode:["today", "planned", "changes"].includes(DISPLAY.start_view) ? DISPLAY.start_view : "changes", sbs:false, sbsJourney:null, sbsAll:false, journey:-1, tech:false, notesOnMap:DISPLAY.notes_on_map === true, lines:false, dots:true, story:typeof window === "undefined" || window.innerWidth >= 760,
  hintSeen:false, roles:Object.fromEntries(ROLES.map(r => [r.id, true])),
  answers:{}, votes:{}, decisions:{}, reviewer:"", myNotes:[], weights:{}, whatifs:[], costView:"chart", horizon:0}, seed, saved);
if (SESSION && saved.syncedVersion !== SESSION.version) Object.assign(S, seed);
if (SESSION) { S.syncedVersion = SESSION.version; S.sessionFinished = SESSION.state === "finished"; }
ROLES.forEach(r => { if (!(r.id in S.roles)) S.roles[r.id] = true; });
if (S.map >= MODEL.maps.length) S.map = 0;
if (S.mode === "compare" || S.mode === "both") S.mode = "changes";
let completedHandoff = SESSION && SESSION.handoff || null;
let syncVersion = SESSION ? SESSION.version : 0, syncPromise = null, syncTimer = null;
let syncState = SESSION ? "saved" : "", syncError = "", finishing = false;
const snapshot = () => JSON.stringify([S.answers, S.votes, S.decisions, S.reviewer, S.myNotes, S.weights, S.whatifs]);
let lastWritten = SESSION ? JSON.stringify([seed.answers, seed.votes, seed.decisions, seed.reviewer, seed.myNotes, seed.weights, seed.whatifs]) : "";
function queueSync() {
  if (!SESSION || finishing || snapshot() === lastWritten) return;
  S.sessionFinished = false;
  syncState = "pending"; clearTimeout(syncTimer);
  syncTimer = setTimeout(() => syncReview(), 200);
}
async function syncReview(finish = false) {
  if (!SESSION) return true;
  if (syncPromise) { const ok = await syncPromise; return ok ? syncReview(finish) : false; }
  const sent = snapshot();
  if (!finish && sent === lastWritten) return true;
  syncState = "saving"; updateReviewStatus();
  syncPromise = (async () => {
    try {
      const response = await fetch(SESSION.base + (finish ? "/finish" : "/answers"), {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({version:syncVersion, review:reviewData()})});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "The answers could not be saved.");
      if (value.handoff) completedHandoff = value.handoff;
      syncVersion = value.version; S.syncedVersion = syncVersion;
      try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
      lastWritten = sent; syncState = "saved"; syncError = "";
      return true;
    } catch (error) { syncState = "failed"; syncError = error.message; return false; }
  })();
  const ok = await syncPromise; syncPromise = null; updateReviewStatus();
  if (ok && snapshot() !== lastWritten) return syncReview(finish);
  return ok;
}
async function finishReview() {
  if (finishing) return;
  finishing = true; clearTimeout(syncTimer);
  const controls = [...document.querySelectorAll("#panel input,#panel textarea,#panel button,#panel select,#tsave")];
  controls.forEach(el => el.disabled = true);
  const ok = await syncReview(true);
  controls.forEach(el => el.disabled = false); finishing = false;
  if (ok) { S.sessionFinished = true; persist(); open("sessiondone"); }
  else toast("Your answers have not reached the agent. Keep this page open and try Finish review again.");
}
addEventListener("beforeunload", event => {
  if (SESSION && snapshot() !== lastWritten) { event.preventDefault(); event.returnValue = ""; }
});
const persist = () => {
  try { localStorage.setItem(KEY, JSON.stringify(S)); storageOK = true; }
  catch (e) { storageOK = false; }
  queueSync(); updateReviewStatus();
};
function answerDone(n) {
  const a = S.answers[n.id] || {};
  return n.answer_type === "stance" ? !!a.choice : !!String(a.answer || "").trim() || a.choice === "unsure";
}
function updateReviewStatus() {
  const save = $("#tsave"); if (save && SESSION && !finishing) save.textContent = S.sessionFinished ? "Read my answers" : "Finish review";
  const el = $("#review-progress");
  if (!el) return;
  const all = NOTES.filter(n => String(n.question || "").trim());
  const done = all.filter(answerDone).length;
  const unsure = all.filter(n => (S.answers[n.id] || {}).choice === "unsure").length;
  el.textContent = `${done} of ${all.length} reviewed${unsure ? ` · ${unsure} not sure yet` : ""}. ` +
    (SESSION ? syncState === "failed" ? "Not saved for your agent. " + syncError : syncState === "saved" ? "Saved for your agent automatically." : "Saving for your agent…" :
      storageOK ? "Kept in this browser. Save a file to share." : "Browser storage is unavailable. Save a file before leaving.");
  document.querySelectorAll("[data-local-copy]").forEach(el => el.textContent = SESSION ? "Answers save for your agent automatically. Finish review when you are ready." : "Answers stay in this browser. Save a file to share.");
  const status = $("#save-status");
  const changed = JSON.stringify([S.answers, S.votes, S.decisions, S.reviewer]) !== (S.lastExport || JSON.stringify([{}, {}, {}, ""]));
  if (status) status.textContent = SESSION ? "No file handoff needed. Finish review when you are ready." : changed ? "Changes since your last saved file" : "";
}

/* ---------- text helpers ---------- */
const esc = t => String(t == null ? "" : t).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const TERMS = Object.keys(GLOSS).sort((a, b) => b.length - a.length);
const TERM_RE = TERMS.length ? new RegExp("\\b(" + TERMS.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")\\b", "i") : null;
function gl(text, focusable = true) {
  if (!TERM_RE) return esc(text);
  return String(text || "").split(TERM_RE).map((part, i) => {
    if (!(i % 2)) return esc(part);
    const key = TERMS.find(t => t.toLowerCase() === part.toLowerCase());
    return `<span class="term" data-term="${esc(key)}"${focusable ? ' tabindex="0"' : ""}>${esc(part)}</span>`;
  }).join("");
}

const pill = (s, why) => s && STATUS[s] ? `<span class="pill ${s}"${why ? ` title="${esc(why)}"` : ""}>${STATUS[s]}</span>` : "";
const bpill = b => pill(b.status, b.status_reason);
const kindLabel = b => b.kind ? `<div class="kind">${esc(b.kind)}</div>` : "";
const days = (a, b) => (new Date(a) - new Date(b)) / 864e5;
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

/* ---------- index of boxes ---------- */
const BOX = {};
MODEL.maps.forEach((m, mi) => {
  (m.journeys || []).forEach((j, ji) => {
    BOX[j.id] = {box:j, mi, kind:"journey", ji};
    (j.steps || []).forEach((s, k) => BOX[s.id] = {box:s, mi, kind:"step", ji, k});
  });
  (m.stages || []).forEach((st, si) => {
    BOX[st.id] = {box:st, mi, kind:"stage", si};
    (st.items || []).forEach(it => BOX[it.id] = {box:it, mi, kind:"item", si, stage:st.id});
  });
  (m.bands || []).forEach(b => BOX[b.id] = {box:b, mi, kind:"band"});
  if (m.root) {
    const walk = (n, d, bi) => { BOX[n.id] = {box:n, mi, kind:"node", depth:d, bi}; (n.children || []).forEach((c, i) => walk(c, d + 1, d === 0 ? i : bi)); };
    walk(m.root, 0, -1);
  }
});
GAPS.forEach(g => BOX[g.id] = {box:g, mi:-1, kind:"gap"});
{ const sm = MODEL.maps.findIndex(m => m.template === "scoring-table"), cm = MODEL.maps.findIndex(m => m.template === "cost-over-time");
  (MODEL.options || []).forEach(o => BOX[o.id] = {box:o, mi:sm, kind:"option"});
  (MODEL.criteria || []).forEach(c => BOX[c.id] = {box:c, mi:sm, kind:"criterion"});
  (MODEL.whatifs || []).forEach(w => BOX[w.id] = {box:w, mi:cm, kind:"whatif"}); }
const notesOn = id => NOTES.filter(n => n.anchor === id && S.roles[n.role] !== false);

/* ---------- today, planned and what changes ---------- */
const MODES = {today:"Today", planned:"Planned", changes:"What changes"};
const CHANGE_WORD = {new:"New", changed:"Changed", gone:"Goes away"};
const groupsOf = m => [...(m.journeys || []).map(j => j.steps || []), ...(m.stages || []).map(st => st.items || [])];
const hasChanges = m => groupsOf(m).some(g => g.some(b => b.when === "today" || b.when === "planned"));
const modeOf = m => hasChanges(m) ? (MODES[S.mode] ? S.mode : "changes") : "all";
const sbsOn = () => !!S.sbs && modeOf(MODEL.maps[S.map]) === "changes" && innerWidth >= 1000;
/* Side by side on a journey map shows one journey at a time, as a single readable column. */
const sbsJourneys = () => sbsOn() && KIND[MODEL.maps[S.map].template] === "journeys";
const journeyChanges = j => arrange(j.steps || [], "changes").filter(s => s.change !== "same");
/* One journey's steps or one stage's items, as slots for the mode. In What changes every
   thing gets one slot in the plan's order: a planned box that replaces a today box is one
   "changed" slot that carries both versions. */
function arrange(boxes, mode) {
  const byId = Object.fromEntries(boxes.map(b => [b.id, b]));
  const replaced = new Set(boxes.filter(b => b.replaces && b.when === "planned").map(b => b.replaces));
  const out = [];
  boxes.forEach(b => {
    const when = b.when || "both";
    if (mode === "all") out.push({box:b, change:""});
    else if (mode === "today") { if (when !== "planned") out.push({box:b, change:""}); }
    else if (mode === "planned") { if (when !== "today") out.push({box:b, change:""}); }
    else if (when === "today") { if (!replaced.has(b.id)) out.push({box:b, change:"gone"}); }
    else if (when === "planned") { const before = b.replaces ? byId[b.replaces] : null; out.push({box:b, change:before ? "changed" : "new", before}); }
    else out.push({box:b, change:"same"});
  });
  return out;
}
const changeList = m => groupsOf(m).flatMap(g => arrange(g, "changes").filter(s => s.change !== "same"));
const CHANGE_INFO = {};
MODEL.maps.forEach(m => changeList(m).forEach(s => {
  CHANGE_INFO[s.box.id] = s;
  if (s.before) CHANGE_INFO[s.before.id] = {change:"replaced", box:s.before, by:s.box};
}));
function changeCounts(list) {
  const n = k => list.filter(s => s.change === k).length;
  return [["new", n("new"), "new"], ["changed", n("changed"), "changed"], ["gone", n("gone"), n("gone") === 1 ? "goes away" : "go away"]].filter(c => c[1]);
}
const countsText = list => changeCounts(list).map(([, n, w]) => `${n} ${w}`).join(" · ");
const countsHtml = list => changeCounts(list).map(([k, n, w]) => `<span class="ribbon ${k}">${n} ${w}</span>`).join("");
/* A changed box carries both versions in one grid cell, so it is as tall as the taller one
   and rows line up in Side by side. */
const RIBBON = s => s.change && s.change !== "same"
  ? `<span class="ribbon ${s.change}">${CHANGE_WORD[s.change]}</span>${s.change === "new" ? "" : `<span class="ribbon-today ${s.change}">${s.change === "changed" ? "Will change" : "Goes away"}</span>`}` : "";
const GHOST = s => s.change === "new" ? `<span class="ghostlabel">Not there today</span>` : s.change === "gone" ? `<span class="ghostlabel">Goes away</span>` : "";
function slotHtml(s, inner) {
  const now = inner(s.box);
  return RIBBON(s) + (s.before ? `<div class="vwrap"><div class="v-now">${now}</div><div class="v-before">${inner(s.before)}</div></div>` : now) + GHOST(s);
}
const slotLabel = (s, text) => (s.change && s.change !== "same" ? CHANGE_WORD[s.change] + ": " : "") + text;

/* ---------- reviewers' rough notes and the experts' replies ---------- */
const EXPERTS = !!(SESSION && SESSION.experts) || !!(HOST && HOST.askExperts);
const MERGED_NOTES = (MERGED && MERGED.notes) || [];
const cleanNote = n => { const c = Object.assign({}, n); delete c._waiting; delete c._error; return c; };
const sameAnchor = (a, b) => (a || null) === (b || null);
const roughOn = id => S.myNotes.filter(n => sameAnchor(n.anchor, id)).length + MERGED_NOTES.filter(n => sameAnchor(n.anchor, id)).length;
const newNoteId = () => "R" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
function whereTitle(anchor) {
  if (!anchor) return "the whole map";
  const [gid, k] = String(anchor).split("#story-");
  const g = GAPS.find(x => x.id === gid);
  if (k != null && g && (g.stories || [])[+k]) return `a story in ${g.id}: ${g.stories[+k].as}`;
  return BOX[anchor] ? titleOf(BOX[anchor].box) : anchor;
}
/* Every expert reply with a question becomes a question to decide, marked as coming from a reviewer note. */
function replyQuestions() {
  return [...S.myNotes.map(n => ({n, who:"you"})), ...MERGED_NOTES.map(n => ({n, who:n.who || n.author || "a reviewer"}))]
    .flatMap(({n, who}) => (n.replies || []).filter(r => String(r.question || "").trim()).map(r => ({
      id:r.id, role:r.role, anchor:n.anchor, title:"On a reviewer note", body:r.view, question:r.question,
      urgency:r.urgency || "info", author:r.author || "AI assistant", fromNote:{text:n.text, who}})));
}
function noteState(n) {
  if (n._waiting) return `<span class="rn-state waiting">Waiting for experts…</span>`;
  const k = (n.replies || []).length;
  if (k) return `<span class="rn-state">${plural(k, "reply")}</span>`.replace("replys", "replies");
  if (n.ask) return `<span class="rn-state waiting">Waiting for experts</span>`;
  return "";
}
function replyHtml(r, answerable) {
  const role = ROLE[r.role] || {label:r.role, color:"#888"};
  const q = {id:r.id, role:r.role, question:r.question, urgency:r.urgency || "info"};
  return `<div class="reply ${r.urgency || "info"}" style="background:${tint(role.color)};--role:${role.color}">
    <div class="small"><span class="swatch" style="background:${role.color}"></span><b>${esc(role.label)}</b> · ${URG[r.urgency || "info"]} · ${esc(r.author || "AI assistant")}</div>
    <p>${gl(r.view || "", true)}</p>${r.question ? `<p><b>${gl(r.question, true)}</b></p>` : ""}
    ${answerable && r.question ? answerHtml(q) : ""}</div>`;
}
function roughNoteHtml(n, mine) {
  const by = mine ? (n.author || S.reviewer || "You") : (n.who || n.author || "A reviewer");
  return `<div class="rough-note" data-rnote="${esc(n.id)}">
    <div class="rn-head"><b>${mine ? "Your note" : `${esc(by)}’s note`}</b>${mine && (n.author || S.reviewer) ? ` · ${esc(by)}` : ""} ${noteState(n)}</div>
    <p class="rn-text">${esc(n.text)}</p>
    ${mine ? `<div class="rn-actions"><button class="mini" data-editnote="${esc(n.id)}">Edit</button>
      <button class="mini" data-delnote="${esc(n.id)}">Delete</button>
      <button class="mini ask" data-asknote="${esc(n.id)}">Ask the experts</button></div>
      <div class="askbox" data-askbox="${esc(n.id)}" hidden><p class="small">Who should reply? Each gives a short view and one question.</p>
        <div class="askroles">${ROLES.map(r => `<label><input type="checkbox" data-askrole="${esc(r.id)}" checked><span class="swatch" style="background:${r.color}"></span>${esc(r.label)}</label>`).join("")}</div>
        <button class="save-primary" data-askgo="${esc(n.id)}">Ask</button> <button class="mini" data-askcancel="${esc(n.id)}">Cancel</button></div>` : ""}
    ${(n.replies || []).length ? `<div class="replies">${n.replies.map(r => replyHtml(r, true)).join("")}</div>` : ""}
    ${mine && n.ask && !(n.replies || []).length && !n._waiting ? `<button class="mini" data-getreplies="${esc(n.id)}">How to get the replies</button>` : ""}
  </div>`;
}
function roughHtml(anchor, heading) {
  const mine = S.myNotes.filter(n => sameAnchor(n.anchor, anchor)), others = MERGED_NOTES.filter(n => sameAnchor(n.anchor, anchor));
  return `<section class="rough">${heading !== false ? `<h3>${heading || "Reviewer notes"}</h3>` : ""}
    ${others.map(n => roughNoteHtml(n, false)).join("")}${mine.map(n => roughNoteHtml(n, true)).join("")}
    <button class="mini addnote" data-addnote="${esc(anchor || "")}">+ Add a sticky note</button>
    <div class="noteeditor" data-editor="${esc(anchor || "")}" hidden>
      <label class="answer-label" for="ne-${esc(anchor || "map")}">Your note</label>
      <textarea id="ne-${esc(anchor || "map")}" data-notetext placeholder="A rough thought is fine. You can ask the experts about it afterwards."></textarea>
      ${S.reviewer ? "" : `<label class="small" for="nn-${esc(anchor || "map")}">Your name or role (optional)</label><input type="text" id="nn-${esc(anchor || "map")}" data-notename>`}
      <div class="row"><button class="save-primary" data-savenote="${esc(anchor || "")}">Save note</button><button class="mini" data-cancelnote>Cancel</button></div>
    </div></section>`;
}
/* Everything an AI agent needs to write the replies itself, for people without a live session. */
function expertPrompt(notes) {
  const asked = notes.map(n => ({id:n.id, text:n.text, on:whereTitle(n.anchor), roles:(n.ask && n.ask.roles) || ROLES.map(r => r.id)}));
  return `You are a panel of experts reviewing a decision. Each expert speaks for one role.\n\n` +
    `The decision: ${MODEL.question}\n${MODEL.summary ? "Summary: " + MODEL.summary + "\n" : ""}\n` +
    `Roles:\n${ROLES.map(r => `- ${r.id}: ${r.label}${r.asks ? " (always asks: " + r.asks + ")" : ""}`).join("\n")}\n\n` +
    `A reviewer left these rough notes. For each note and each role listed for it, write one reply: a short view in that role's voice ` +
    `(one or two plain sentences reacting to the note) and one question whose answer could change the choice.\n\n` +
    `Notes:\n${JSON.stringify(asked, null, 2)}\n\n` +
    `Add the replies to the matching notes in the reviewer's answers file, as "replies": [{"id": "<note id>-<role id>", "role": "<role id>", ` +
    `"view": "...", "question": "...", "urgency": "must|should|info", "author": "AI assistant"}]. Keep everything else in the file as it is. ` +
    `Or run: decisioncraft perspectives MODEL.json --notes ANSWERS.json --out replies.json`;
}

/* Word-level differences between two short texts, for the Before and After view. */
function wordDiff(a, b) {
  const A = String(a || "").split(/(\s+)/).filter(Boolean), B = String(b || "").split(/(\s+)/).filter(Boolean);
  const n = A.length, m = B.length;
  const dp = Array.from({length:n + 1}, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const mark = (t, tag) => /^\s+$/.test(t) ? esc(t) : `<${tag}>${esc(t)}</${tag}>`;
  let i = 0, j = 0, oa = "", ob = "";
  while (i < n && j < m) {
    if (A[i] === B[j]) { oa += esc(A[i]); ob += esc(B[j]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) oa += mark(A[i++], "del");
    else ob += mark(B[j++], "ins");
  }
  while (i < n) oa += mark(A[i++], "del");
  while (j < m) ob += mark(B[j++], "ins");
  return [oa, ob];
}
const mapOfAnchor = a => BOX[a] ? (BOX[a].mi >= 0 ? BOX[a].mi : mapOfAnchor((BOX[a].box.anchors || [])[0])) : -1;
const titleOf = b => b.title || b.name || b.label || b.text || b.id;

function badges(b) {
  const out = [];
  if (sinceAdded.has(b.id)) out.push(`<span class="chip since">New since last review</span>`);
  else if (sinceChanged[b.id]) out.push(`<span class="chip since">Changed since last review</span>`);
  const ref = (MODEL.checked || {}).date;
  if (b.checked && ref && days(ref, b.checked) > FRESH_DAYS) out.push(`<span class="chip stale" title="Checked ${esc(b.checked)}">May be out of date</span>`);
  if (b.moment) out.push(`<span class="chip moment">Moment that matters</span>`);
  if (b.pain) out.push(`<span class="chip pain">Pain point</span>`);
  if (b.feeling) out.push(`<span class="chip"><i class="feel ${b.feeling}"></i>${FEEL[b.feeling]}</span>`);
  const ev = (b.evidence || []).length;
  if (ev) out.push(`<span class="chip">Evidence: ${ev}</span>`);
  const rough = roughOn(b.id);
  if (rough) out.push(`<span class="chip rough">✎ ${plural(rough, "reviewer note")}</span>`);
  const notes = notesOn(b.id);
  if (notes.length) {
    const colours = [...new Set(notes.map(n => (ROLE[n.role] || {}).color || "#888"))].slice(0, 3);
    out.push(`<span class="notebadge${notes.some(n => n.urgency === "must") ? " must" : ""}"><span class="stack" aria-hidden="true">${colours.map(c => `<i style="background:${tint(c)};border-color:${c}"></i>`).join("")}</span>${plural(notes.length, "note")}</span>`);
  }
  return out.join("");
}
const tech = b => S.tech && b.detail ? `<span class="techname">${esc(b.detail)}</span>` : "";

/* ---------- DOM helpers ---------- */
const world = $("#world"), viewport = $("#viewport");
let nodes = {}, rows = [], svg, K = 0;
function place(cls, x, y, w, html, data, label) {
  const d = document.createElement("div");
  d.className = cls; d.style.left = x + "px"; d.style.top = y + "px";
  if (w) d.style.width = w + "px";
  d.innerHTML = html;
  if (data) { d.tabIndex = 0; d.setAttribute("role", "button"); d.setAttribute("aria-label", label || ""); d._data = data; d.dataset.k = ++K; }
  world.appendChild(d);
  return d;
}
function link(x1, y1, x2, y2, cls, label) {
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  const my = (y1 + y2) / 2;
  p.setAttribute("d", Math.abs(x1 - x2) < 2 ? `M${x1},${y1} L${x2},${y2}` : `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`);
  if (cls) p.setAttribute("class", cls);
  svg.appendChild(p);
  if (label) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", (x1 + x2) / 2 + 16); t.setAttribute("y", my + 5); t.textContent = label;
    t.setAttribute("class", "verb");
    svg.appendChild(t);
  }
  return p;
}
function arrowHead(x, y) {
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", `M${x - 6},${y - 9} L${x},${y} L${x + 6},${y - 9}`);
  svg.appendChild(p);
}
function tint(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16) || 0x888888;
  const mix = c => Math.round(c * 0.16 + 255 * 0.84);
  return `rgb(${mix(n >> 16 & 255)},${mix(n >> 8 & 255)},${mix(n & 255)})`;
}

/* Notes beside a row (only when "Show all notes on the map" is on): a column to the right of
   every box, sized from the real cards, so a note never sits over any text. */
const NOTE_W = 250, NOTE_GAP = 12, NOTES_W = 2 * NOTE_W + NOTE_GAP;
function notePile(anchors, x, y, max, rowKey, cols = 2) {
  if (!S.notesOnMap) return 0;
  const list = NOTES.filter(n => anchors.includes(n.anchor) && S.roles[n.role] !== false)
    .sort((a, b) => URG_ORDER[a.urgency || "info"] - URG_ORDER[b.urgency || "info"]);
  const shown = list.slice(0, max);
  const colH = [0, 0];
  shown.forEach((n, i) => {
    const c = cols === 1 || colH[0] <= colH[1] ? 0 : 1;
    const r = ROLE[n.role] || {label:n.role, color:"#888"};
    const el = place(`notecard ${n.urgency || "info"} inj`, x + c * (NOTE_W + NOTE_GAP), y + colH[c], NOTE_W,
      `<div class="notehead"><span class="who"><i style="background:${r.color}"></i>${esc(r.label)}</span><span class="urg">${URG[n.urgency || "info"]}</span></div>
       <h5>${esc(n.title)}</h5><div class="q">${esc(n.question || n.body || "")}</div>`,
      {type:"note", n}, `${r.label} note: ${n.title}`);
    el.style.background = tint(r.color);
    el.style.setProperty("--note-tilt", [-1.1, 0.8, -0.5, 1][i % 4] + "deg");
    el.style.setProperty("--role", r.color);
    el.dataset.row = rowKey; el.dataset.anchor = n.anchor;
    colH[c] += el.offsetHeight + NOTE_GAP;
  });
  let h = Math.max(colH[0], colH[1]);
  if (list.length > shown.length) {
    const more = place("morenotes inj", x, y + h, cols === 1 ? NOTE_W : NOTES_W, `+ ${plural(list.length - shown.length, "more note")} here`,
      {type:"notes", anchors, title:"Notes here"}, `${list.length - shown.length} more notes`);
    more.dataset.row = rowKey;
    h += more.offsetHeight + NOTE_GAP;
  }
  return h;
}
const notesWidth = () => S.notesOnMap ? NOTES_W + 48 : 0;

function header(m, width) {
  place("stamp", 0, 6, 0, (MODEL.checked && MODEL.checked.date) ? `Checked against the sources on ${esc(MODEL.checked.date)}` : "Not yet checked against sources");
  const t = place("maptitle", 0, 40, Math.max(width, 600), esc(m.title || MODEL.title));
  const q = place("mapintro", 0, 40 + t.offsetHeight + 8, Math.min(Math.max(width, 600), 900), gl(m.intro || ""));
  let y = 40 + t.offsetHeight + 8 + q.offsetHeight;
  const mode = modeOf(m);
  if (mode !== "all") {
    const list = changeList(m);
    const text = mode === "today" ? "<b>Today.</b> What exists now, before any change." :
      mode === "planned" ? "<b>Planned.</b> How it works once the plan is done." :
      `<b>What changes.</b> The plan, with every change marked. ${countsHtml(list)}`;
    const lg = place("modebar", 0, y + 14, 0, `${text}${mode === "changes" ? `<span class="hint-sbs">${sbsOn() ? "Left: today. Right: the plan. Rows line up." : "Faded boxes go away. Open a box to compare before and after."}</span>` : ""}`);
    y += 14 + lg.offsetHeight;
  }
  return y + 40;
}

/* ---------- journeys ---------- */
/* Each lane keeps one colour, so a step's edge says which part of the system it runs in. */
const LANE_COLORS = ["#4f7fd8", "#8a5cd6", "#d99a1e", "#2f9e6a", "#d1543f", "#1f9aa6", "#b5568c", "#7a7a72"];
function okColour(c) {
  if (!/^#[0-9a-f]{6}$/i.test(c || "")) return false;
  const [r, g, b] = [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16) / 255).map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05) >= 3;
}
const laneColor = (i, m = MODEL.maps[S.map]) => { const own = ((m.lanes || [])[i] || {}).color; return okColour(own) ? own : LANE_COLORS[i % LANE_COLORS.length]; };
const J = {laneW:262, laneGap:20, stepW:238, stepH:86, rowGap:18, headW:330, headGap:44, bandGap:76};
function stepInner(n) {
  return b => `${kindLabel(b)}<div class="row1"><span class="n">${n}</span><div class="t">${gl(b.text)}</div></div>${tech(b)}
    <div class="meta">${bpill(b)}${badges(b)}</div>`;
}
function journeyHead(m, j, ji, slots, mode) {
  const changed = mode === "changes" ? slots.filter(s => s.change && s.change !== "same") : [];
  return `<h3><span class="n">${ji + 1}</span><span class="tt">${gl(j.title)}</span></h3><p>${gl(j.summary || "")}</p>
    ${(j.creates || []).length ? `<div class="creates"><b>What gets created</b><ul>${j.creates.map(c => `<li>${esc(c)}</li>`).join("")}</ul></div>` : ""}
    ${changed.length ? `<div class="creates changes"><b>What changes</b><p>${countsHtml(changed)}</p></div>` : ""}
    ${tech(j)}<div class="meta">${badges(j)}<span class="chip">${plural(slots.length, "step")}</span></div>
    ${slots.length ? `<button class="mini startj" data-startj="${S.map}:${ji}">▶ Walk through this journey</button>` : ""}`;
}
function renderJourneys(m) {
  const lanes = m.lanes || [];
  const mode = modeOf(m);
  const LI = Object.fromEntries(lanes.map((l, i) => [l.id, i]));
  const laneX = i => J.headW + J.headGap + i * (J.laneW + J.laneGap);
  const lanesRight = laneX(lanes.length - 1) + J.laneW;
  const notesX = lanesRight + 56;
  const W = lanesRight + notesWidth();
  let y = header(m, W);
  lanes.forEach((l, i) => {
    const h = place("lanehead", laneX(i), y, J.laneW, `<i style="background:${laneColor(i)}"></i>${esc(l.label)}<small>${esc(l.sub || "")}</small>`,
      {type:"lane", mi:S.map, i}, `About ${l.label}`);
    h.style.setProperty("--lane", laneColor(i));
    if (l.summary) h.title = l.summary;
  });
  if (S.notesOnMap) place("label", notesX, y + 4, 0, "Notes from each role");
  y += 66;
  const laneTop = y - 78;
  (m.journeys || []).forEach((j, ji) => {
    const y0 = y;
    const slots = arrange(j.steps || [], mode);
    const hd = place("box jhead inj", 0, y0, J.headW, journeyHead(m, j, ji, slots, mode),
      {type:"box", id:j.id}, `Journey ${ji + 1}: ${j.title}`);
    hd.dataset.row = "j" + ji;
    nodes[j.id] = hd;
    let sy = y0, prev = null;
    slots.forEach((slot, k) => {
      const s = slot.box;
      const li = LI[s.lane] || 0;
      const x = laneX(li) + (J.laneW - J.stepW) / 2;
      const el = place(`box step inj${slot.change ? " chg-" + slot.change : ""}`, x, sy, J.stepW,
        slotHtml(slot, stepInner(k + 1)),
        {type:"box", id:s.id}, slotLabel(slot, `Step ${k + 1} of journey ${ji + 1}: ${s.text}`));
      el.style.minHeight = J.stepH + "px";
      el.style.setProperty("--lane", laneColor(li));
      el.dataset.row = "j" + ji;
      nodes[s.id] = el;
      const h = el.offsetHeight;
      if (prev) {
        const p = link(prev.x + J.stepW / 2, prev.y + prev.h, x + J.stepW / 2, sy - 3, "inj flow");
        p.dataset.row = "j" + ji; arrowHead(x + J.stepW / 2, sy - 3);
      }
      prev = {x, y:sy, h};
      sy += h + J.rowGap;
    });
    const nh = notePile([j.id, ...(j.steps || []).map(s => s.id)], notesX, y0, 4, "j" + ji);
    const h = Math.max(hd.offsetHeight, sy - y0, nh);
    rows.push({key:"j" + ji, y:y0, h, x:0, w:W});
    y = y0 + h + J.bandGap;
  });
  lanes.forEach((l, i) => {
    const bg = document.createElement("div"); bg.className = "lanebg";
    Object.assign(bg.style, {left:(laneX(i) - 9) + "px", top:laneTop + "px", width:(J.laneW + 18) + "px", height:(y - laneTop - J.bandGap + 24) + "px"});
    bg.style.setProperty("--lane", laneColor(i));
    world.prepend(bg);
  });
  return {x:0, y:0, w:W, h:y};
}

/* A customer's actions run left to right, in the supplied order. */
function renderCustomerJourney(m) {
  const cardW = 252, gap = 62;
  const mode = modeOf(m);
  const all = (m.journeys || []).map(j => arrange(j.steps || [], mode));
  const count = Math.max(1, ...all.map(s => s.length));
  const timelineW = count * (cardW + gap) - gap;
  const notesX = timelineW + 56;
  const W = timelineW + notesWidth();
  const LI = Object.fromEntries((m.lanes || []).map((l, i) => [l.id, i]));
  let y = header(m, W);
  (m.journeys || []).forEach((j, ji) => {
    const start = y;
    const slots = all[ji];
    const hd = place("box timeline-title inj", 0, y, Math.min(640, timelineW),
      journeyHead(m, j, ji, slots, mode), {type:"box", id:j.id}, j.title);
    nodes[j.id] = hd; hd.dataset.row = "j" + ji;
    y += hd.offsetHeight + 52;
    let maxH = 0, prev = null;
    slots.forEach((slot, i) => {
      const step = slot.box;
      const x = i * (cardW + gap);
      const li = LI[step.lane];
      const lane = (m.lanes || [])[li];
      const lb = place("steplabel", x, y - 28, cardW, `<i style="background:${laneColor(li || 0)}"></i>${i + 1}. ${esc(lane ? lane.label : "Next step")}`);
      lb.dataset.row = "j" + ji;
      const card = place(`box customer-step inj${slot.change ? " chg-" + slot.change : ""}`, x, y, cardW,
        slotHtml(slot, b => `${kindLabel(b)}<h4>${gl(b.text)}</h4>${tech(b)}<div class="meta">${bpill(b)}${badges(b)}</div>`),
        {type:"box", id:step.id}, slotLabel(slot, `Step ${i + 1}: ${step.text}`));
      card.style.setProperty("--lane", laneColor(li || 0));
      card.dataset.row = "j" + ji; nodes[step.id] = card;
      maxH = Math.max(maxH, card.offsetHeight);
      if (prev !== null) {
        const line = link(prev + cardW + 6, y + 32, x - 10, y + 32, "inj customer-flow");
        line.dataset.row = "j" + ji;
        const arrow = document.createElementNS("http://www.w3.org/2000/svg", "path");
        arrow.setAttribute("d", `M${x - 18},${y + 26} L${x - 10},${y + 32} L${x - 18},${y + 38}`);
        arrow.setAttribute("class", "customer-flow"); svg.appendChild(arrow);
      }
      prev = x;
    });
    const nh = notePile([j.id, ...(j.steps || []).map(step => step.id)], notesX, start, 4, "j" + ji);
    const h = Math.max(y - start + maxH, nh);
    rows.push({key:"j" + ji, y:start, h, x:0, w:W});
    y = start + h + 70;
  });
  return {x:0, y:0, w:W, h:y};
}

/* Side by side, journey maps: the chosen journey as one column of steps, each with its
   lane as a chip, so both panes stay readable. By default only the steps that differ show,
   with one step either side; runs of unchanged steps fold into a line that opens them. */
function renderJourneySbs(m) {
  const lanes = m.lanes || [];
  const LI = Object.fromEntries(lanes.map((l, i) => [l.id, i]));
  const js = m.journeys || [];
  if (S.sbsJourney == null || !js[S.sbsJourney]) S.sbsJourney = Math.max(0, js.findIndex(j => journeyChanges(j).length));
  const ji = S.sbsJourney, j = js[ji] || {steps:[]};
  const all = arrange(j.steps || [], "changes");
  const differs = all.map(s => s.change !== "same");
  const any = differs.some(Boolean);
  const keep = all.map((s, i) => S.sbsAll || !any || differs[i] || differs[i - 1] || differs[i + 1]);
  const W = 540;
  const t = place("maptitle sbs-title", 0, 0, W, `<span class="n">${ji + 1}</span><span class="tt">${esc(j.title || "")}</span>`);
  let y = t.offsetHeight + 8;
  if (j.summary) { const q = place("mapintro", 0, y, W, gl(j.summary)); y += q.offsetHeight + 12; }
  const changed = all.filter(s => s.change !== "same");
  const mb = place("modebar", 0, y, 0, any ? `${countsHtml(changed)}<span class="hint-sbs">${S.sbsAll ? "The whole journey" : "Only what changes, with one step either side"}</span>` : "No changes in this journey. All of its steps are shown.");
  y += mb.offsetHeight + 26;
  let prev = null, hidden = 0;
  const fold = () => {
    if (!hidden) return;
    const g = place("gaprow", 0, y, W, `${plural(hidden, "step")} the same here · Show the whole journey`, {type:"expand"}, `Show ${plural(hidden, "unchanged step")}`);
    g.dataset.row = "j" + ji;
    y += g.offsetHeight + 14; hidden = 0; prev = null;
  };
  all.forEach((slot, i) => {
    if (!keep[i]) { hidden++; return; }
    fold();
    const s = slot.box, li = LI[s.lane] || 0, lane = lanes[li];
    const el = place(`box step sbs-step inj${slot.change ? " chg-" + slot.change : ""}`, 0, y, W,
      slotHtml(slot, b => `${kindLabel(b)}<div class="row1"><span class="n">${i + 1}</span><div class="t">${gl(b.text)}</div></div>${tech(b)}
        <div class="meta"><span class="lanechip"><i style="background:${laneColor(LI[b.lane] || 0)}"></i>${esc((lanes[LI[b.lane] || 0] || {}).label || "")}</span>${bpill(b)}${badges(b)}</div>`),
      {type:"box", id:s.id}, slotLabel(slot, `Step ${i + 1}: ${s.text}`));
    el.style.setProperty("--lane", laneColor(li));
    el.dataset.row = "j" + ji;
    nodes[s.id] = el;
    if (prev) { const p = link(W / 2, prev.y + prev.h, W / 2, y - 3, "inj flow"); p.dataset.row = "j" + ji; arrowHead(W / 2, y - 3); }
    prev = {y, h:el.offsetHeight};
    y += el.offsetHeight + 16;
  });
  fold();
  rows.push({key:"j" + ji, y:0, h:y, x:0, w:W});
  return {x:0, y:0, w:W, h:y};
}

/* ---------- chain ---------- */
const C = {stageW:300, stageH:104, itemW:262, itemGap:16, perRow:3, gap:70};
const itemInner = b => `${kindLabel(b)}<h4>${gl(b.title)}</h4><p class="t">${gl(b.text || "")}</p>${tech(b)}<div class="meta">${bpill(b)}${badges(b)}</div>`;
function renderChain(m) {
  const mode = modeOf(m);
  // Two to a row side by side, or with notes on the map, so the boxes and their stickies fit on screen.
  const perRow = sbsOn() || S.notesOnMap ? 2 : C.perRow;
  const pileW = S.notesOnMap ? NOTE_W : 0;
  const hasBefore = (m.stages || []).some(st => st.before);
  const bands = m.bands || [];
  const beforeW = 250, stageX = hasBefore ? beforeW + 40 : 0;
  const itemsX = stageX + C.stageW + 64;
  const columnW = perRow * (C.itemW + C.itemGap) - C.itemGap;
  // Notes sit right after each row's own boxes, so a sticky is always next to what it is about;
  // bands move out past the notes.
  const notesX = itemsX + columnW + 40;
  const bandX = (S.notesOnMap ? notesX + pileW + 40 : itemsX + columnW + 56), bandW = 270;
  const W = Math.max(S.notesOnMap ? notesX + pileW : itemsX + columnW, bands.length ? bandX + bands.length * (bandW + 20) - 20 : 0);
  let y = header(m, W);
  if (hasBefore) place("label", 0, y, beforeW, esc(m.before_label || "Before"));
  place("label", stageX, y, 0, "The chain");
  if (bands.length) place("label", bandX, y, 0, "Across the chain");
  place("label", itemsX, y, columnW, {today:"What exists today", planned:"What the plan puts in place", changes:"The plan, with every change marked", all:"What is here"}[mode]);
  // (no column label: each row's notes sit beside its own boxes)
  y += 34;
  let prevStage = null;
  (m.stages || []).forEach((st, si) => {
    const y0 = y;
    const stEl = place(`box stage inj${si === 0 ? " first-stage" : ""}`, stageX, y0, C.stageW,
      `<span class="stagenum">${si + 1}</span><h3>${gl(st.label)}</h3><p>${gl(st.sub || "")}</p>${tech(st)}<div class="meta">${bpill(st)}${badges(st)}</div>`,
      {type:"box", id:st.id}, `Stage ${si + 1}: ${st.label}`);
    const bc = st.before ? place("beforecell inj", 0, y0, beforeW, `<p>${gl(st.before)}</p>`) : null;
    if (bc) { bc.dataset.row = "s" + si; bc.style.minHeight = C.stageH + "px"; }
    stEl.style.minHeight = C.stageH + "px";
    stEl.dataset.row = "s" + si; nodes[st.id] = stEl;
    const slots = arrange(st.items || [], mode);
    let rowMax = 0, iy = y0, col = 0;
    slots.forEach(slot => {
      const it = slot.box;
      const el = place(`box item inj${slot.change ? " chg-" + slot.change : ""}`,
        itemsX + col * (C.itemW + C.itemGap), iy, C.itemW, slotHtml(slot, itemInner),
        {type:"box", id:it.id}, slotLabel(slot, it.title));
      el.dataset.row = "s" + si;
      nodes[it.id] = el;
      rowMax = Math.max(rowMax, el.offsetHeight);
      if (++col === perRow) { col = 0; iy += rowMax + C.itemGap; rowMax = 0; }
    });
    let ih = iy - y0 + rowMax;
    if (!slots.length) {
      const e = place("emptyslot", itemsX, y0, C.itemW, mode === "today" ? "Nothing here today" : mode === "planned" ? "Nothing planned here" : "Nothing here yet");
      e.dataset.row = "s" + si; ih = e.offsetHeight;
    }
    const used = Math.max(1, Math.min(slots.length, perRow));
    const nh = notePile([st.id, ...(st.items || []).map(i => i.id)], itemsX + used * (C.itemW + C.itemGap) + 22, y0, 3, "s" + si, 1);
    const h = Math.max(stEl.offsetHeight, ih, nh, bc ? bc.offsetHeight : 0);
    rows.push({key:"s" + si, y:y0, h, x:0, w:W, stage:st.id, mid:y0 + stEl.offsetHeight / 2});
    if (prevStage) {
      const sx = stageX + C.stageW / 2;
      const p = link(sx, prevStage.y + prevStage.h + 4, sx, y0 - 6, "inj spine", prevStage.verb);
      p.dataset.row = "s" + si; arrowHead(sx, y0 - 6);
    }
    prevStage = {y:y0, h:stEl.offsetHeight, verb:st.verb || ""};
    y = y0 + h + C.gap;
  });
  /* Bands run beside the chain, as tall as the stages they touch, with a chip level with
     each of those stages and a dashed line back to its row. */
  bands.forEach((band, bi) => {
    const linked = rows.filter(r => r.stage && (!(band.stages || []).length || band.stages.includes(r.stage)));
    if (!linked.length) return;
    const top = linked[0].y, bottom = linked[linked.length - 1].y + linked[linked.length - 1].h;
    const x = bandX + bi * (bandW + 20);
    const el = place("box band inj", x, top, bandW,
      `${kindLabel(band)}<h4>${gl(band.title || band.id)}</h4>${band.text ? `<p class="t">${gl(band.text)}</p>` : ""}${tech(band)}
       <div class="meta">${bpill(band)}${badges(band)}</div>`,
      {type:"box", id:band.id}, `Across the chain: ${band.title || band.id}`);
    const wordsH = el.offsetHeight;
    el.style.height = Math.max(bottom - top, wordsH) + "px";
    const chips = linked.filter(r => r.mid - top - 12 > wordsH + 6).map(r => {
      const si = (m.stages || []).findIndex(st => st.id === r.stage);
      return `<span class="bandchip" style="top:${r.mid - top - 12}px">${si + 1} · ${esc((m.stages[si] || {}).label || "")}</span>`;
    }).join("");
    if (chips) el.insertAdjacentHTML("beforeend", `<div class="bandchips" aria-hidden="true">${chips}</div>`);
    nodes[band.id] = el;
    linked.forEach(r => {
      const l = link((S.notesOnMap ? notesX + pileW : itemsX + columnW) + 10, r.mid, x - 6, r.mid, "bandlink");
      l.dataset.row = r.key;
    });
  });
  const outs = MODEL.outcomes || [];
  if (outs.length && m === MODEL.maps.find(mm => KIND[mm.template] === "chain")) {
    place("label", stageX, y, 0, "Did it work?");
    y += 26;
    const ow = C.itemW + 60;
    let oy = y, outcomeH = 0;
    outs.forEach((o, i) => {
      const el = place("box inj", stageX + (i % 3) * (ow + C.itemGap), oy, ow,
        `<h4>${esc(o.measure)}</h4><p class="t">${o.baseline ? "Before: " + esc(o.baseline) + ". " : ""}${o.target ? "Target: " + esc(o.target) + ". " : ""}${o.result ? "<b>Result: " + esc(o.result) + "</b>" : "Not measured yet."}</p>
         <div class="meta">${o.becomes_evidence ? `<span class="chip">Feeds back as evidence</span>` : ""}</div>`,
        {type:"outcome", o}, `Outcome: ${o.measure}`);
      nodes[o.id] = el;
      outcomeH = Math.max(outcomeH, el.offsetHeight);
      if (i % 3 === 2 || i === outs.length - 1) { oy += outcomeH + C.itemGap; outcomeH = 0; }
    });
    rows.push({key:"outcomes", y:y - 26, h:oy - y + 26, x:0, w:W});
    y = oy + 20;
  }
  return {x:0, y:0, w:W, h:y};
}

/* ---------- tree ---------- */
const T = {colW:270, colGap:60, nodeH:104, vGap:18};
function renderTree(m) {
  const levels = !m.levels || JSON.stringify(m.levels) === JSON.stringify(["Outcome","Need or pain","Idea","Quick test"]) ? TREE_LEVELS : m.levels;
  const depthOf = n => n.children && n.children.length ? 1 + Math.max(...n.children.map(depthOf)) : 1;
  const depth = depthOf(m.root);
  const notesX = depth * (T.colW + T.colGap) + 10;
  const W = depth * (T.colW + T.colGap) - T.colGap + notesWidth();
  let y = header(m, W);
  for (let d = 0; d < depth; d++) place("label", d * (T.colW + T.colGap), y, 0, esc(levels[Math.min(d, levels.length - 1)]));
  y += 30;
  // Measure the actual cards before reserving rows. Long titles and badges wrap.
  const cards = {};
  let nodeH = T.nodeH;
  (function measure(n, d) {
    const el = place(`box tree-node l${d} inj`, d * (T.colW + T.colGap), y, T.colW,
      `${kindLabel(n)}<h4>${gl(n.title)}</h4>${n.text ? `<p class="t">${gl(n.text)}</p>` : ""}${tech(n)}<div class="meta">${bpill(n)}${badges(n)}</div>`,
      {type:"box", id:n.id}, `${levels[Math.min(d, levels.length - 1)]}: ${n.title}`);
    el.style.minHeight = T.nodeH + "px";
    cards[n.id] = el;
    nodeH = Math.max(nodeH, el.offsetHeight);
    (n.children || []).forEach(c => measure(c, d + 1));
  })(m.root, 0);
  let cursor = y;
  const pos = {};
  (function lay(n, d) {
    const kids = n.children || [];
    let cy;
    if (!kids.length) { cy = cursor; cursor += nodeH + T.vGap; }
    else { kids.forEach(k => lay(k, d + 1)); cy = (pos[kids[0].id].y + pos[kids[kids.length - 1].id].y) / 2; }
    pos[n.id] = {x:d * (T.colW + T.colGap), y:cy, d};
  })(m.root, 0);
  const branches = m.root.children || [];
  const ids = n => [n.id, ...(n.children || []).flatMap(ids)];
  const shifted = {};
  let shift = 0;
  branches.forEach((b, bi) => {
    const own = ids(b);
    const ys = own.map(i => pos[i].y);
    const y0 = Math.min(...ys) + shift, y1 = Math.max(...ys) + nodeH + shift;
    own.forEach(i => shifted[i] = pos[i].y + shift);
    const nh = notePile(own, notesX, y0, 4, "b" + bi);
    rows.push({key:"b" + bi, y:y0, h:Math.max(y1 - y0, nh), x:0, w:W});
    shift += Math.max(0, nh - (y1 - y0)) + (S.notesOnMap ? T.vGap : 0);
  });
  shifted[m.root.id] = branches.length ? (shifted[branches[0].id] + shifted[branches[branches.length - 1].id]) / 2 : pos[m.root.id].y;
  const draw = (n, parent, bi) => {
    const p = pos[n.id], ny = shifted[n.id];
    const el = cards[n.id];
    el.style.top = ny + "px";
    el.style.height = nodeH + "px";
    if (bi != null) el.dataset.row = "b" + bi;
    nodes[n.id] = el;
    if (parent) {
      const l = link(pos[parent.id].x + T.colW, shifted[parent.id] + nodeH / 2, p.x, ny + nodeH / 2, "inj");
      if (bi != null) l.dataset.row = "b" + bi;
    }
    (n.children || []).forEach(c => draw(c, n, bi == null ? branches.indexOf(c) : bi));
  };
  draw(m.root, null, null);
  let bottom = Math.max(...Object.values(shifted)) + nodeH;
  if (S.notesOnMap && notesOn(m.root.id).length) {
    const start = Math.max(bottom, ...rows.map(row => row.y + row.h)) + 38;
    place("label", notesX, start - 24, NOTES_W, "About the whole choice");
    const height = notePile([m.root.id], notesX, start, 6, "root-notes");
    rows.push({key:"root-notes", y:start, h:height, x:0, w:W});
    bottom = start + height;
  }
  return {x:0, y:0, w:W, h:bottom + 60};
}

/* ---------- options: scoring table and cost over time ----------
   The same arithmetic as choice.py, so totals, flips and costs match the text version.
   Scores are whole numbers 1 to 5; totals show one decimal so they never look more exact
   than the judgments behind them. */
const OPTIONS = (MODEL.options || []).filter(o => o && o.id);
const CRITERIA = (MODEL.criteria || []).filter(c => c && c.id);
const SCORED = CRITERIA.filter(c => (c.kind || "scored") === "scored");
const MUSTS = CRITERIA.filter(c => c.kind === "must");
const CELL = Object.fromEntries((MODEL.scores || []).map(s => [s.option + "|" + s.criterion, s]));
const WHATIFS = (MODEL.whatifs || []).filter(w => w && w.id);
const OPT_COLORS = ["#0072b2", "#d55e00", "#009e73", "#b5568c", "#8a6a00", "#56b4e9", "#4a4a4a"];
const optColor = o => okColour(o.color) ? o.color : OPT_COLORS[OPTIONS.indexOf(o) % OPT_COLORS.length];
const OPT = Object.fromEntries(OPTIONS.map(o => [o.id, o]));
const optName = id => (OPT[id] || {}).name || id;
const critName = id => ((CRITERIA.find(c => c.id === id)) || {}).name || id;
const CUR = (MODEL.costs || {}).currency || "";
function money(v) {
  const sym = {USD:"$", GBP:"£", EUR:"€"}[CUR] || "";
  const t = Math.round(Math.abs(v)).toLocaleString("en-US");
  return (v < 0 ? "-" : "") + (sym ? sym + t : t + (CUR ? " " + CUR : ""));
}
const modelWeight = c => +c.weight || 0;
const weightOf = c => c.id in S.weights ? S.weights[c.id] : modelWeight(c);
const ownWeights = () => SCORED.some(c => c.id in S.weights && S.weights[c.id] !== modelWeight(c));

function scoreTable(weights) {
  const w = Object.fromEntries(SCORED.map(c => [c.id, weights ? (c.id in weights ? weights[c.id] : modelWeight(c)) : weightOf(c)]));
  const rows = OPTIONS.map(o => {
    const fails = MUSTS.filter(c => (CELL[o.id + "|" + c.id] || {}).meets === false).map(c => c.id);
    let A = 0, W = 0;
    SCORED.forEach(c => { const s = CELL[o.id + "|" + c.id]; if (s && typeof s.value === "number") { A += w[c.id] * s.value; W += w[c.id]; } });
    return {option:o.id, points:A, total:W ? Math.round(A / W * 100) / 100 : 0, fails};
  });
  const eligible = rows.filter(r => !r.fails.length).sort((a, b) => b.total - a.total || OPTIONS.findIndex(o => o.id === a.option) - OPTIONS.findIndex(o => o.id === b.option));
  eligible.forEach((r, i) => r.rank = i + 1);
  const close = eligible.length > 1 && eligible[0].total - eligible[1].total < 0.25;
  return {w, rows, eligible, leader:eligible.length ? eligible[0].option : null, close, flips:flipsOf(w, eligible)};
}
function topOf(ids, w, cell) {
  const tot = o => { let A = 0, W = 0; SCORED.forEach(c => { const s = cell[o + "|" + c.id]; if (s && typeof s.value === "number") { A += w[c.id] * s.value; W += w[c.id]; } }); return W ? A / W : 0; };
  return ids.slice().sort((a, b) => tot(b) - tot(a) || OPTIONS.findIndex(o => o.id === a) - OPTIONS.findIndex(o => o.id === b))[0];
}
function flipsOf(w, eligible) {
  if (eligible.length < 2) return [];
  const lead = eligible[0].option, val = (o, c) => (CELL[o + "|" + c] || {}).value;
  const W = SCORED.reduce((a, c) => a + w[c.id], 0), out = [];
  eligible.slice(1).forEach(r => {
    const o = r.option;
    const A_l = SCORED.reduce((a, c) => a + w[c.id] * (val(lead, c.id) || 0), 0);
    const A_o = SCORED.reduce((a, c) => a + w[c.id] * (val(o, c.id) || 0), 0);
    const gap = A_l - A_o;
    SCORED.forEach(c => {
      const vl = val(lead, c.id), vo = val(o, c.id);
      if (vl == null || vo == null || vl === vo) return;
      const delta = gap / (vo - vl), nw = w[c.id] + delta;
      let target = delta > 0 ? Math.ceil(nw * 2) / 2 : Math.floor(nw * 2) / 2;
      if (target === nw) target += delta > 0 ? 0.5 : -0.5;
      if (target >= 0 && target <= 5 && target !== w[c.id]) out.push({kind:"weight", option:o, criterion:c.id, from:w[c.id], to:target, size:Math.abs(target - w[c.id])});
    });
    SCORED.forEach(c => {
      const vl = val(lead, c.id), vo = val(o, c.id);
      if (vl == null || vo == null || !W) return;
      if (vo < 5 && A_o + w[c.id] > A_l) out.push({kind:"score", option:o, criterion:c.id, of:o, from:vo, to:vo + 1, size:1});
      if (vl > 1 && A_l - w[c.id] < A_o) out.push({kind:"score", option:o, criterion:c.id, of:lead, from:vl, to:vl - 1, size:1});
    });
  });
  const oi = id => OPTIONS.findIndex(o => o.id === id), ci = id => SCORED.findIndex(c => c.id === id);
  out.sort((a, b) => a.size - b.size || (a.kind === "score" ? 0 : 1) - (b.kind === "score" ? 0 : 1) || (w[b.criterion] || 0) - (w[a.criterion] || 0) || oi(a.option) - oi(b.option) || ci(a.criterion) - ci(b.criterion));
  const ids = eligible.map(r => r.option);
  return out.map(f => {
    const ww = Object.assign({}, w), cell = Object.assign({}, CELL);
    if (f.kind === "weight") ww[f.criterion] = f.to;
    else { const k = f.of + "|" + f.criterion; cell[k] = Object.assign({}, cell[k], {value:f.to}); }
    return Object.assign(f, {new_leader:topOf(ids, ww, cell)});
  }).filter(f => f.new_leader !== lead).filter((f, i, all) => {
    /* Two challengers can suggest the same change with the same result: say it once. */
    const key = x => [x.kind, x.criterion, x.to, x.kind === "score" ? x.of : "", x.new_leader].join("|");
    return all.findIndex(g => key(g) === key(f)) === i;
  }).slice(0, 3);
}
const flipText = f => f.kind === "weight"
  ? `If <b>${esc(critName(f.criterion))}</b> mattered ${f.to > f.from ? "more" : "less"} (weight ${f.from} → ${f.to}), <b>${esc(optName(f.new_leader))}</b> would come out on top.`
  : `If <b>${esc(optName(f.of))}</b> scored ${f.to} instead of ${f.from} on <b>${esc(critName(f.criterion))}</b>, <b>${esc(optName(f.new_leader))}</b> would come out on top.`;

function choicePanelHtml(info, b) {
  if (info.kind === "option") {
    const r = scoreTable(), row = r.rows.find(x => x.option === b.id) || {fails:[]};
    const cr = MODEL.costs && MODEL.costs.options && MODEL.costs.options[b.id] ? costResult() : null;
    const scoreLines = CRITERIA.map(c => { const s = CELL[b.id + "|" + c.id] || {}; const v = c.kind === "must" ? (s.meets === true ? "Meets" : s.meets === false ? "Fails" : "Not checked") : (typeof s.value === "number" ? s.value + " of 5" : "–");
      return `<li><b>${esc(c.name)}:</b> ${v}${s.note ? ` – ${gl(s.note, true)}` : ""}${(s.evidence || []).length ? ` <button class="mini" data-evidence="${esc(s.evidence.join(","))}">Evidence</button>` : ""}</li>`; }).join("");
    return `${b.summary ? `<p>${gl(b.summary, true)}</p>` : ""}
      <p>${row.fails.length ? `<span class="pill missing">Fails a must-have</span> ${row.fails.map(id => esc(critName(id))).join(", ")}.` : row.rank ? `Place ${row.rank} in the table, ${row.total.toFixed(1)} of 5.` : ""}</p>
      ${cr ? `<p>Real cost after ${cr.h} years: <b>${money(cr.series[b.id].real[cr.h * 12])}</b>${cr.series[b.id].payment ? `; payment about ${money(cr.series[b.id].payment)} a month` : ""}.</p>` : ""}
      ${CRITERIA.length ? `<h3>How it scores</h3><ul class="scorelist">${scoreLines}</ul>` : ""}
      <p>${info.mi >= 0 ? `<button class="mini" data-goto-map="${info.mi}:sc-table">Show in the table</button>` : ""}${cr ? ` <button class="mini" data-goto-map="${MODEL.maps.findIndex(m => m.template === "cost-over-time")}:co-chart">Show on the cost chart</button>` : ""}</p>`;
  }
  if (info.kind === "criterion") {
    const lines = OPTIONS.map(o => { const s = CELL[o.id + "|" + b.id] || {}; const v = b.kind === "must" ? (s.meets === true ? "Meets" : s.meets === false ? "Fails" : "Not checked") : (typeof s.value === "number" ? s.value + " of 5" : "–"); return `<li><b>${esc(o.name)}:</b> ${v}${s.note ? ` – ${gl(s.note, true)}` : ""}</li>`; }).join("");
    return `${b.measure ? `<p><b>How it is judged:</b> ${gl(b.measure, true)}</p>` : ""}<ul class="scorelist">${lines}</ul>${b.kind !== "must" ? `<p><button class="mini" data-goto-map="${info.mi}:sc-flip">What would change the winner</button></p>` : ""}`;
  }
  if (info.kind === "whatif") {
    const f = Object.entries(b.multiply || {}).map(([k, v]) => `${esc(k)} × ${v}`).join(", ");
    return `<p class="small">Changes: ${f}.</p><p><button class="mini" data-goto-map="${info.mi}:co-chart">Show on the cost chart</button></p>`;
  }
  return "";
}
/* Cost over time: money spent + loan still owed − what it is worth + what the cash up front
   could have earned. Month 0 is the day you start. */
function yearly(it, y) {
  if (typeof it.yearly === "number") return it.yearly;
  const ys = (it.yearly || []).filter(v => typeof v === "number");
  return ys.length ? ys[Math.min(y, ys.length - 1)] : 0;
}
function factor(mult, keys) { return keys.reduce((f, k) => k in mult ? f * mult[k] : f, 1); }
function loanSchedule(amount, apr, months) {
  const r = apr / 12, pay = r === 0 ? amount / months : amount * r / (1 - Math.pow(1 + r, -months));
  const bal = [amount]; let b = amount;
  for (let i = 0; i < months; i++) { b = b * (1 + r) - pay; bal.push(Math.max(b, 0)); }
  return [pay, bal];
}
function mults(ids) {
  const m = {};
  ids.forEach(id => { const w = WHATIFS.find(x => x.id === id); if (w) Object.entries(w.multiply || {}).forEach(([k, f]) => m[k] = (m[k] || 1) * f); });
  return m;
}
function optionSeries(oid, mult) {
  const costs = MODEL.costs, h = costs.horizon_years || 5, c = costs.options[oid];
  const keys = x => [x.kind || "other", ...(x.tags || [])];
  const up = (c.upfront || []).reduce((a, u) => a + u.amount * factor(mult, keys(u)), 0);
  const items = c.items || [], loan = c.loan;
  const [pay, bal] = loan ? loanSchedule(loan.amount, loan.apr, loan.months) : [0, [0]];
  const value = (c.value || []).filter(v => typeof v === "number"); if (!value.length) value.push(0);
  const vf = factor(mult, ["value"]), rate = costs.cash_return || 0;
  const real = []; let total = up;
  for (let m = 0; m <= h * 12; m++) {
    if (m > 0) {
      const y = Math.floor((m - 1) / 12);
      total += items.reduce((a, it) => a + yearly(it, y) * factor(mult, keys(it)) / 12, 0);
      if (loan && m <= loan.months) total += pay;
    }
    const owed = loan ? bal[Math.min(m, bal.length - 1)] : 0;
    const yi = Math.floor(m / 12), frac = m % 12;
    const a = value[Math.min(yi, value.length - 1)], b = value[Math.min(yi + 1, value.length - 1)];
    const worth = (a + (b - a) * frac / 12) * vf;
    real.push(total + owed - worth + up * (Math.pow(1 + rate, m / 12) - 1));
  }
  const payment = loan ? pay : items.filter(it => it.kind === "lease").reduce((a, it) => a + yearly(it, 0), 0) / 12;
  return {real, payment};
}
function costResult() {
  const costs = MODEL.costs;
  if (!costs || !costs.options) return null;
  const order = OPTIONS.map(o => o.id).filter(id => costs.options[id]);
  if (!order.length) return null;   // options, but no costs yet (for example right after an interview)
  const mult = mults(S.whatifs);
  const h = costs.horizon_years || 5;
  const series = Object.fromEntries(order.map(o => [o, optionSeries(o, mult)]));
  const crossings = [];
  order.forEach((a, i) => order.slice(i + 1).forEach(b => {
    let prev = null;
    for (let m = 1; m <= h * 12; m++) {
      const d = series[a].real[m] - series[b].real[m], sign = d > 0 ? 1 : d < 0 ? -1 : 0;
      if (prev !== null && sign && prev && sign !== prev) crossings.push({month:m, cheaper:sign < 0 ? a : b, dearer:sign < 0 ? b : a});
      if (sign) prev = sign;
    }
  }));
  crossings.sort((x, y) => x.month - y.month || order.indexOf(x.cheaper) - order.indexOf(y.cheaper));
  const fails = new Set(scoreTable().rows.filter(r => r.fails.length).map(r => r.option));
  const ranking = order.slice().sort((a, b) => series[a].real[h * 12] - series[b].real[h * 12]);
  return {h, order, series, crossings, fails, ranking, cheapest:ranking.find(o => !fails.has(o))};
}
const whenText = m => { const y = Math.floor(m / 12), mo = m % 12; return y && mo ? `${y} year${y > 1 ? "s" : ""} and ${mo} month${mo > 1 ? "s" : ""} in` : y ? `${y} year${y > 1 ? "s" : ""} in` : `${mo} month${mo > 1 ? "s" : ""} in`; };

/* ---------- drawing the scoring table ---------- */
function heat(v) {   // calm sequential shading; the number is always written in the cell
  const t = Math.max(0, Math.min(1, (v - 1) / 4));
  const mix = (a, b) => Math.round(a + (b - a) * t);
  return `rgb(${mix(246, 196)},${mix(244, 222)},${mix(238, 250)})`;
}
function renderScoring(m) {
  const res = scoreTable();
  const colW = 176, headW = 270;
  const W = Math.max(headW + OPTIONS.length * colW, 760);
  const top = header(m, W);
  let y = top;
  const merged = (MERGED && MERGED.weights) || {};
  const split = new Set((MERGED && MERGED.weight_split) || []);
  const cellOf = (o, c) => CELL[o.id + "|" + c.id] || {};
  const head = OPTIONS.map(o => {
    const r = res.rows.find(x => x.option === o.id);
    const out = r.fails.length;
    return `<th scope="col" class="optcol${out ? " out" : ""}${res.leader === o.id ? " lead" : ""}" style="--opt:${optColor(o)}">
      <button class="optbtn" data-choice-open="${esc(o.id)}"><span class="swatch" aria-hidden="true"></span>${esc(o.name || o.id)}</button>
      <span class="optsum">${gl(o.summary || "")}</span>
      <span class="optmeta">${out ? `<span class="pill missing">Fails a must-have</span>` : `<span class="rank">${r.rank === 1 ? "Top of the table" : "Place " + r.rank}</span>`}${bpill(o)}${badges(o)}</span></th>`;
  }).join("");
  const mustRows = MUSTS.map(c => `<tr class="mustrow"><th scope="row"><button class="critbtn" data-choice-open="${esc(c.id)}">${esc(c.name)}</button><span class="crit-sub">Must-have${c.measure ? ": " + esc(c.measure) : ""}</span>${badges(c)}</th>
    ${OPTIONS.map(o => { const s = cellOf(o, c); const ok = s.meets; return `<td class="must ${ok === true ? "meets" : ok === false ? "fails" : "unknown"}"${s.note ? ` title="${esc(s.note)}"` : ""}>${ok === true ? "✓ Meets" : ok === false ? "✕ Fails" : "Not checked"}${ok === false && s.note ? `<span class="cellnote">${esc(s.note)}</span>` : ""}</td>`; }).join("")}</tr>`).join("");
  const scoreRows = SCORED.map(c => {
    const w = weightOf(c), mine = c.id in S.weights && S.weights[c.id] !== modelWeight(c);
    return `<tr><th scope="row"><button class="critbtn" data-choice-open="${esc(c.id)}">${esc(c.name)}</button>
      <span class="weight${mine ? " mine" : ""}" title="${mine ? `Your weight (the model says ${modelWeight(c)})` : "How much this matters, 0 to 5"}">Weight ${w}${mine ? " (yours)" : ""}</span>${split.has(c.id) ? `<span class="chip split" title="${esc((merged[c.id] || []).map(v => v.who + " " + v.weight).join(", "))}">Reviewers disagree</span>` : ""}
      ${c.measure ? `<span class="crit-sub">${esc(c.measure)}</span>` : ""}${badges(c)}</th>
      ${OPTIONS.map(o => { const s = cellOf(o, c); const v = s.value; const out = res.rows.find(x => x.option === o.id).fails.length;
        return `<td class="score${out ? " out" : ""}" style="background:${typeof v === "number" ? heat(v) : "transparent"}"${s.note ? ` title="${esc(s.note)}"` : ""}><span class="num">${typeof v === "number" ? v : "–"}</span>${s.note ? `<span class="cellnote">${esc(s.note)}</span>` : ""}</td>`; }).join("")}</tr>`;
  }).join("");
  const totals = OPTIONS.map(o => { const r = res.rows.find(x => x.option === o.id);
    return r.fails.length ? `<td class="total out">Out</td>` : `<td class="total"><span class="bar" style="width:${Math.round(r.total / 5 * 100)}%;background:${optColor(o)}"></span><b>${r.total.toFixed(1)}</b> <span class="small">of 5</span></td>`; }).join("");
  const table = place("scoreboard", 0, y, W, `<table class="scoretable"><caption class="sr">Scores for each option. Must-haves first, then weighted scores from 1 to 5.</caption>
    <thead><tr><th scope="col" class="corner">${MUSTS.length ? "Must-haves first, then what matters" : "What matters"}</th>${head}</tr></thead>
    <tbody>${mustRows}${scoreRows}<tr class="totalrow"><th scope="row">Weighted total${ownWeights() ? " (your weights)" : ""}</th>${totals}</tr></tbody></table>`);
  rows.push({key:"sc-table", y, h:table.offsetHeight, x:0, w:W});
  y += table.offsetHeight + 26;
  const lead = res.leader;
  const verdict = lead ? `<b>${esc(optName(lead))}</b> is top of the table${res.close ? `, but it is a <b>close call</b>: the top totals are within a quarter of a point, so treat them as level and let the notes and costs decide.` : "."}` : "No option meets every must-have.";
  const flips = res.flips.length ? `<ul>${res.flips.map(f => `<li>${flipText(f)}</li>`).join("")}</ul>` : `<p>No change of one weight within 0 to 5, or of one score by one point, changes the winner. The result is steady.</p>`;
  const card = place("flipcard", 0, y, Math.min(W, 900), `<h3>What would change the winner?</h3><p>${verdict}</p>${flips}
    <div class="cardbtns"><button data-choice="weights">Change the weights</button>${ownWeights() ? `<button data-choice="resetweights">Use the model's weights</button>` : ""}${MODEL.framing ? `<button data-choice="framing">Before you decide</button>` : ""}</div>`);
  rows.push({key:"sc-flip", y, h:card.offsetHeight, x:0, w:W});
  let bottom = y + card.offsetHeight;
  if (S.notesOnMap) {
    const ids = [...OPTIONS, ...CRITERIA].map(x => x.id);
    const nh = notePile(ids, W + 48, top, 8, "sc-notes");
    bottom = Math.max(bottom, top + nh);
  }
  table.querySelectorAll("[data-choice-open]").forEach(b => { b._data = {type:"box", id:b.dataset.choiceOpen}; nodes[b.dataset.choiceOpen] = b; });
  return {x:0, y:0, w:W + notesWidth(), h:bottom + 60};
}

/* ---------- drawing cost over time ---------- */
function renderCosts(m) {
  const res = costResult();
  const W = 980;
  const top = header(m, W);
  let y = top;
  if (!res) {
    place("mapintro", 0, y, 640, `<p><b>No costs yet.</b> For each option, add what it costs up front, each year, any loan, and what it is worth year by year. Then this map shows the real cost over time and where the cheaper option changes.</p><p class="small">The model format is in <code>decisioncraft guide</code>.</p>`);
    return {x:0, y:0, w:W, h:y + 140};
  }
  const span = Math.min(S.horizon || res.h, res.h);
  const controls = `<div class="seg" role="group" aria-label="How far ahead">${[1, 3, 5, 10].filter(n => n <= res.h).concat(res.h > 5 && res.h !== 10 ? [res.h] : []).filter((v, i, a) => a.indexOf(v) === i).map(n => `<button data-choice="horizon:${n}" aria-pressed="${span === n}">${n} year${n > 1 ? "s" : ""}</button>`).join("")}</div>
    <div class="seg" role="group" aria-label="Chart or table"><button data-choice="view:chart" aria-pressed="${S.costView !== "table"}">Chart</button><button data-choice="view:table" aria-pressed="${S.costView === "table"}">Table</button></div>
    ${WHATIFS.length ? `<div class="whatifs" role="group" aria-label="What if"><span class="small">What if:</span>${WHATIFS.map(w => `<button class="toggle" data-choice="whatif:${esc(w.id)}" aria-pressed="${S.whatifs.includes(w.id)}" data-whatif="${esc(w.id)}">${esc(w.label)}</button>`).join("")}</div>` : ""}`;
  const bar = place("costbar", 0, y, W, controls);
  y += bar.offsetHeight + 16;
  const months = span * 12;
  const vis = res.order;
  let body;
  if (S.costView === "table") {
    const years = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].filter(n => n <= span);
    body = `<table class="costtable"><caption class="sr">Real cost so far for each option, by year.</caption><thead><tr><th scope="col">Option</th>${years.map(n => `<th scope="col">After ${n} year${n > 1 ? "s" : ""}</th>`).join("")}<th scope="col">Loan or lease payment</th></tr></thead><tbody>
      ${vis.map(o => `<tr${res.fails.has(o) ? ` class="out"` : ""}><th scope="row"><span class="swatch" style="background:${optColor(OPT[o])}"></span>${esc(optName(o))}${res.fails.has(o) ? ` <span class="small">(fails a must-have)</span>` : ""}</th>${years.map(n => `<td>${money(res.series[o].real[n * 12])}</td>`).join("")}<td>${res.series[o].payment ? money(res.series[o].payment) + " a month" : "–"}</td></tr>`).join("")}</tbody></table>`;
  } else body = costChart(res, months, W);
  const chart = place("costchart", 0, y, W, body);
  rows.push({key:"co-chart", y:bar.offsetTop, h:chart.offsetTop + chart.offsetHeight - bar.offsetTop, x:0, w:W});
  y += chart.offsetHeight + 20;
  const relevant = res.crossings.filter(c => c.month <= months && !res.fails.has(c.cheaper) && !res.fails.has(c.dearer));
  const cheapNow = res.order.filter(o => !res.fails.has(o)).sort((a, b) => res.series[a].real[months] - res.series[b].real[months])[0];
  const say = place("costsay", 0, y, Math.min(W, 900), `<h3>What the lines say</h3>
    <p>Cheapest after ${span} year${span > 1 ? "s" : ""}${res.fails.size ? " among options that meet every must-have" : ""}: <b>${esc(optName(cheapNow))}</b>, ${money(res.series[cheapNow].real[months])} in real cost.${S.whatifs.length ? ` With: ${S.whatifs.map(id => esc((WHATIFS.find(w => w.id === id) || {}).label || id)).join(", ")}.` : ""}</p>
    ${relevant.length ? `<ul>${relevant.slice(0, 5).map(c => `<li><b>${esc(optName(c.cheaper))}</b> costs less than ${esc(optName(c.dearer))} from month ${c.month} on (${whenText(c.month)}).</li>`).join("")}</ul>` : `<p>No lines cross in this time: the order stays the same.</p>`}
    ${res.fails.size ? `<p class="small">Dashed lines fail a must-have; they are shown for comparison only.</p>` : ""}
    <p class="small">Real cost = money spent so far, plus any loan still owed, minus what you could sell it for${MODEL.costs.cash_return ? `, plus what the cash put down could have earned at ${Math.round(MODEL.costs.cash_return * 1000) / 10}% a year` : ""}.${MODEL.costs.assumptions ? " " + esc(MODEL.costs.assumptions) : ""}</p>`);
  rows.push({key:"co-say", y, h:say.offsetHeight, x:0, w:W});
  y += say.offsetHeight + 20;
  const split = place("costsplit", 0, y, W, `<h3>Where the money goes over ${res.h} years</h3><div class="splitgrid">${vis.map(o => {
      const parts = breakdownOf(o), total = parts.reduce((a, p) => a + Math.max(p.amount, 0), 0) || 1;
      return `<div class="split"><h4><span class="swatch" style="background:${optColor(OPT[o])}"></span>${esc(optName(o))}</h4>
        <div class="stack" role="img" aria-label="${esc(parts.map(p => p.label + " " + money(p.amount)).join(", "))}">${parts.filter(p => p.amount > 0).map((p, i) => `<i style="width:${p.amount / total * 100}%;opacity:${1 - i * 0.13}"></i>`).join("")}</div>
        <ul>${parts.slice(0, 5).map(p => `<li><span>${esc(p.label)}</span><b>${money(p.amount)}</b></li>`).join("")}</ul></div>`; }).join("")}</div>`);
  split.querySelectorAll(".split").forEach((el, i) => el.style.setProperty("--opt", optColor(OPT[vis[i]])));
  rows.push({key:"co-split", y, h:split.offsetHeight, x:0, w:W});
  y += split.offsetHeight;
  let bottom = y;
  if (S.notesOnMap) {
    const nh = notePile(WHATIFS.map(w => w.id), W + 48, top, 6, "co-notes");
    bottom = Math.max(bottom, top + nh);
  }
  bar.querySelectorAll("[data-whatif]").forEach(b => { const n = notesOn(b.dataset.whatif).length; if (n) b.insertAdjacentHTML("beforeend", ` <span class="small">· ${plural(n, "note")}</span>`); });
  return {x:0, y:0, w:W + notesWidth(), h:bottom + 60};
}
function breakdownOf(oid) {
  const costs = MODEL.costs, h = costs.horizon_years || 5, c = costs.options[oid], mult = mults(S.whatifs);
  const keys = x => [x.kind || "other", ...(x.tags || [])];
  const KINDS = {purchase:"Buying it", lease:"Lease payments", financing:"Loan payments", insurance:"Insurance", energy:"Fuel or charging",
    maintenance:"Servicing and repairs", tax:"Taxes and fees", membership:"Membership and hire", other:"Other costs",
    interest:"Loan interest", value_lost:"Value lost", cash_tied_up:"What the cash put down could have earned"};
  const parts = {}; let bought = 0;
  (c.upfront || []).forEach(u => { const a = u.amount * factor(mult, keys(u)); if (u.kind === "purchase") bought += a; else parts[u.kind || "other"] = (parts[u.kind || "other"] || 0) + a; });
  (c.items || []).forEach(it => { const f = factor(mult, keys(it)); let t = 0; for (let y = 0; y < h; y++) t += yearly(it, y) * f; parts[it.kind || "other"] = (parts[it.kind || "other"] || 0) + t; });
  if (c.loan) { const [pay, bal] = loanSchedule(c.loan.amount, c.loan.apr, c.loan.months); const n = Math.min(c.loan.months, h * 12); parts.interest = pay * n - (c.loan.amount - bal[n]); bought += c.loan.amount; }
  const value = (c.value || []).filter(v => typeof v === "number");
  if (value.length) parts.value_lost = bought - value[Math.min(h, value.length - 1)] * factor(mult, ["value"]);
  else if (bought) parts.purchase = (parts.purchase || 0) + bought;
  const up = (c.upfront || []).reduce((a, u) => a + u.amount * factor(mult, keys(u)), 0);
  if (costs.cash_return && up) parts.cash_tied_up = up * (Math.pow(1 + costs.cash_return, h) - 1);
  return Object.entries(parts).filter(([, v]) => Math.abs(v) >= 25).map(([k, v]) => ({kind:k, label:KINDS[k] || k, amount:v})).sort((a, b) => b.amount - a.amount);
}
function costChart(res, months, W) {
  const H = 380, L = 78, R = 190, T = 18, B = 46, pw = W - L - R, ph = H - T - B;
  const vals = res.order.flatMap(o => res.series[o].real.slice(0, months + 1));
  const lo = Math.min(0, ...vals), hi = Math.max(...vals);
  const step = niceStep((hi - lo) / 5);
  const y0 = Math.floor(lo / step) * step, y1 = Math.ceil(hi / step) * step;
  const X = m => L + m / months * pw, Y = v => T + ph - (v - y0) / (y1 - y0 || 1) * ph;
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-labelledby="chart-t chart-d"><title id="chart-t">Real cost so far, month by month</title><desc id="chart-d">${esc(res.order.map(o => `${optName(o)}: ${money(res.series[o].real[months])} after ${months / 12} years`).join("; "))}. The Table view has every number.</desc>`;
  for (let v = y0; v <= y1 + 1e-6; v += step) s += `<line class="grid" x1="${L}" x2="${L + pw}" y1="${Y(v)}" y2="${Y(v)}"/><text class="tick" x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${money(v)}</text>`;
  const yStep = months <= 12 ? 3 : 12;
  for (let m = 0; m <= months; m += yStep) s += `<line class="vgrid" x1="${X(m)}" x2="${X(m)}" y1="${T}" y2="${T + ph}"/><text class="tick" x="${X(m)}" y="${T + ph + 18}" text-anchor="middle">${m === 0 ? "Start" : months <= 12 ? "Month " + m : "Year " + m / 12}</text>`;
  if (y0 < 0) s += `<line class="zero" x1="${L}" x2="${L + pw}" y1="${Y(0)}" y2="${Y(0)}"/>`;
  const labels = [];
  res.order.forEach(o => {
    const pts = res.series[o].real.slice(0, months + 1).map((v, m) => `${X(m).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
    const col = optColor(OPT[o]);
    s += `<polyline class="line${res.fails.has(o) ? " out" : ""}" points="${pts}" style="stroke:${col}"/>`;
    labels.push({o, y:Y(res.series[o].real[months]), col});
  });
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 30) labels[i].y = labels[i - 1].y + 30;   // direct labels never overlap
  labels.forEach(l => {
    const end = Y(res.series[l.o].real[months]);
    s += `<line class="leader" x1="${L + pw + 2}" x2="${L + pw + 12}" y1="${end}" y2="${l.y}" style="stroke:${l.col}"/>
      <text class="lab" x="${L + pw + 16}" y="${l.y - 2}" style="fill:${l.col}">${esc(optName(l.o))}${res.fails.has(l.o) ? "*" : ""}</text>
      <text class="labv" x="${L + pw + 16}" y="${l.y + 14}">${money(res.series[l.o].real[months])}</text>`;
  });
  res.crossings.filter(c => c.month <= months && !res.fails.has(c.cheaper) && !res.fails.has(c.dearer)).slice(0, 5).forEach((c, i) => {
    const v = (res.series[c.cheaper].real[c.month] + res.series[c.dearer].real[c.month]) / 2;
    s += `<circle class="cross" cx="${X(c.month)}" cy="${Y(v)}" r="9"/><text class="crossn" x="${X(c.month)}" y="${Y(v) + 4}" text-anchor="middle">${i + 1}</text>`;
  });
  s += `</svg>`;
  const marks = res.crossings.filter(c => c.month <= months && !res.fails.has(c.cheaper) && !res.fails.has(c.dearer)).slice(0, 5);
  const foot = res.fails.size ? `<p class="chartfoot">* Dashed: fails a must-have, shown for comparison only.</p>` : "";
  return s + foot + (marks.length ? `<ol class="crosslist">${marks.map(c => `<li>${esc(optName(c.cheaper))} becomes cheaper than ${esc(optName(c.dearer))} at month ${c.month}.</li>`).join("")}</ol>` : "");
}
function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(raw || 1))), n = raw / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}
function choiceAction(a) {
  const [k, v] = a.split(":");
  if (k === "weights") return open("weights");
  if (k === "framing") return open("framing");
  if (k === "resetweights") { S.weights = {}; persist(); render(); return; }
  if (k === "horizon") S.horizon = +v;
  if (k === "view") S.costView = v;
  if (k === "whatif") S.whatifs = S.whatifs.includes(v) ? S.whatifs.filter(x => x !== v) : [...S.whatifs, v];
  persist(); layout(); applyFocusBack(a);
}
function applyFocusBack(a) { const b = world.querySelector(`[data-choice="${CSS.escape(a)}"]`); if (b) b.focus({preventScroll:true}); }

/* Named connections come from the model, never from the card positions. */
function visibleLinks() {
  const mode = modeOf(MODEL.maps[S.map]);
  return (MODEL.links || []).filter(l => mode === "changes" || mode === "all" || (l.when || "both") === "both" || l.when === mode);
}
function drawConnections() {
  const connections = visibleLinks().filter(l => nodes[l.from] && nodes[l.to]);
  const right = Math.max(0, ...Object.values(nodes).map(n => parseFloat(n.style.left) + n.offsetWidth));
  connections.forEach((connection, i) => {
    const a = nodes[connection.from], b = nodes[connection.to];
    const ax = parseFloat(a.style.left) + a.offsetWidth / 2, ay = parseFloat(a.style.top);
    const bx = parseFloat(b.style.left) + b.offsetWidth / 2, by = parseFloat(b.style.top);
    const gutter = right + 40 + i * 18;
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", `connection ${connection.kind || "flow"}`);
    group.dataset.from = connection.from; group.dataset.to = connection.to;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M${ax},${ay} V${ay - 16} H${gutter} V${by - 16} H${bx} V${by - 2}`);
    group.appendChild(path);
    const arrow = document.createElementNS("http://www.w3.org/2000/svg", "path");
    arrow.setAttribute("d", `M${bx - 5},${by - 9} L${bx},${by - 2} L${bx + 5},${by - 9}`);
    group.appendChild(arrow);
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = connection.label; group.appendChild(title);
    svg.appendChild(group);
  });
  if (connections.length) bounds.w = Math.max(bounds.w, right + 70 + connections.length * 18);
  applyConnections();
}
function applyConnections() {
  const selected = current && current.kind === "box" ? current.arg : null;
  const connected = new Set(selected ? [selected] : []);
  visibleLinks().forEach(l => { if (l.from === selected || l.to === selected) { connected.add(l.from); connected.add(l.to); } });
  svg.querySelectorAll(".connection").forEach(group => {
    const relevant = selected && (group.dataset.from === selected || group.dataset.to === selected);
    group.classList.toggle("active", !!relevant);
    group.style.display = S.lines || relevant ? "" : "none";
  });
  document.body.classList.toggle("connection-focus", connected.size > 1);
  Object.entries(nodes).forEach(([id, node]) => node.classList.toggle("connected", connected.has(id)));
}

/* ---------- render ---------- */
let bounds = {x:0, y:0, w:1000, h:800};
/* Free notes (about the whole map) sit in their own column to the right of everything. */
function drawFreeNotes(m) {
  const mid = m.id || String(S.map);
  const free = [...S.myNotes.filter(n => !n.anchor && (!n.map || n.map === mid)).map(n => [n, true]),
    ...MERGED_NOTES.filter(n => !n.anchor && (!n.map || n.map === mid)).map(n => [n, false])];
  if (!free.length) return;
  const x = bounds.w + 70;
  let y = 120;
  place("label", x, y - 30, 0, "Notes on the whole map");
  free.forEach(([n, mine], i) => {
    const el = place("roughcard", x, y, 260, `<div class="rn-head"><b>${mine ? "Your note" : esc(n.who || n.author || "A reviewer") + "’s note"}</b> ${noteState(n)}</div><p>${esc(n.text)}</p>`,
      {type:"mapnotes"}, `${mine ? "Your note" : "Reviewer note"} on the whole map: ${n.text}`);
    el.style.setProperty("--note-tilt", [-1, 0.8, -0.4][i % 3] + "deg");
    y += el.offsetHeight + 16;
  });
  bounds.w = x + 260 + 40; bounds.h = Math.max(bounds.h, y + 40);
}
/* Dashed lines join each note on the map to the box it is about. */
function drawNoteLinks() {
  world.querySelectorAll(".notecard").forEach(note => {
    const box = nodes[note.dataset.anchor];
    if (!box) return;
    const nx = parseFloat(note.style.left), ny = parseFloat(note.style.top) + 22;
    // A box placed on the map has its own position; one inside a table (an option or a
    // criterion) is measured against the map instead.
    const wr = world.getBoundingClientRect(), br = box.getBoundingClientRect(), k = (typeof Z === "number" && Z) || 1;
    const left = box.style.left ? parseFloat(box.style.left) : (br.left - wr.left) / k;
    const top = box.style.top ? parseFloat(box.style.top) : (br.top - wr.top) / k;
    const bx = left + box.offsetWidth, by = top + Math.min(box.offsetHeight / 2, 40);
    if (![nx, ny, bx, by].every(Number.isFinite)) return;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const mx = bx + (nx - bx) * 0.55;
    path.setAttribute("d", `M${bx + 4},${by} C${mx},${by} ${mx},${ny} ${nx - 4},${ny}`);
    path.setAttribute("class", "notelink inj"); path.dataset.row = note.dataset.row;
    path.style.stroke = note.style.getPropertyValue("--role");
    svg.appendChild(path);
  });
}
function layout() {
  world.classList.remove("pane-today");   // measure boxes as they are, not as the left pane shows them
  world.innerHTML = "";
  nodes = {}; rows = []; K = 0;
  svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "links"); svg.setAttribute("aria-hidden", "true");
  world.appendChild(svg);
  const m = MODEL.maps[S.map];
  const kind = KIND[m.template];
  document.body.dataset.mode = modeOf(m);
  document.body.classList.toggle("sbs-j", sbsJourneys());
  bounds = sbsJourneys() ? renderJourneySbs(m) : m.template === "customer-journey" ? renderCustomerJourney(m) : kind === "journeys" ? renderJourneys(m) : kind === "chain" ? renderChain(m) : kind === "scoring" ? renderScoring(m) : kind === "costs" ? renderCosts(m) : renderTree(m);
  drawNoteLinks();
  drawFreeNotes(m);
  drawConnections();
  applyFocus();
  if (current && current.kind === "box" && nodes[current.arg]) nodes[current.arg].classList.add("sel");
  syncPanes();
}
function render() {
  layout();
  topBar();
  story();
}
/* Side by side: the same drawing twice, today on the left and the plan on the right, with
   one pan and zoom. The right copy is for looking; clicks open the matching box. */
const world2 = $("#world2"), viewport2 = $("#viewport2");
function sbsBar() {
  const bar = $("#sbsbar");
  if (!sbsJourneys()) { bar.innerHTML = ""; return; }
  const js = MODEL.maps[S.map].journeys || [];
  bar.innerHTML = `<label for="sbs-journey">Journey</label>
    <select id="sbs-journey">${js.map((j, i) => { const c = journeyChanges(j); return `<option value="${i}"${i === S.sbsJourney ? " selected" : ""}>${i + 1}. ${esc(j.title)}${c.length ? " · " + countsText(c) : " · no changes"}</option>`; }).join("")}</select>
    <button data-sbs-step="-1"${S.sbsJourney <= 0 ? " disabled" : ""}>‹ Previous journey</button>
    <button data-sbs-step="1"${S.sbsJourney >= js.length - 1 ? " disabled" : ""}>Next journey ›</button>
    <label class="switch"><input type="checkbox" id="sbs-only"${S.sbsAll ? "" : " checked"}> Only what changes</label>`;
  const pick = i => { S.sbsJourney = Math.max(0, Math.min(js.length - 1, i)); persist(); render(); fit(); };
  $("#sbs-journey").addEventListener("change", e => pick(+e.target.value));
  bar.querySelectorAll("[data-sbs-step]").forEach(b => b.addEventListener("click", () => pick(S.sbsJourney + +b.dataset.sbsStep)));
  $("#sbs-only").addEventListener("change", e => { S.sbsAll = !e.target.checked; persist(); render(); fit(); });
}
function syncPanes() {
  sbsBar();
  const on = sbsOn();
  document.body.classList.toggle("sbs", on);
  world.classList.toggle("pane-today", on);
  world2.innerHTML = "";
  if (!on) return;
  const copy = world.cloneNode(true);
  world2.append(...copy.childNodes);
  world2.querySelectorAll("[tabindex]").forEach(e => e.setAttribute("tabindex", "-1"));
  world2.querySelectorAll("[id]").forEach(e => e.removeAttribute("id"));
}
function twin(el) {
  if (!el || !el.dataset.k) return null;
  const other = el.closest("#world2") ? world : world2;
  return other.querySelector(`[data-k="${el.dataset.k}"]`);
}
const pairline = $("#pairline");
function showPair(el) {
  const t = twin(el);
  document.querySelectorAll(".pair").forEach(x => x.classList.remove("pair"));
  if (!sbsOn() || !t) { pairline.style.display = "none"; return; }
  const [a, b] = el.closest("#world2") ? [t, el] : [el, t];
  a.classList.add("pair"); b.classList.add("pair");
  const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
  const x1 = ra.right, y1 = ra.top + Math.min(ra.height / 2, 30), x2 = rb.left, y2 = rb.top + Math.min(rb.height / 2, 30);
  const len = Math.hypot(x2 - x1, y2 - y1);
  Object.assign(pairline.style, {display:"block", left:x1 + "px", top:y1 + "px", width:len + "px", transform:`rotate(${Math.atan2(y2 - y1, x2 - x1)}rad)`});
}
[world, world2].forEach(w => {
  w.addEventListener("mouseover", e => { const el = e.target.closest("[data-k]"); if (el) showPair(el); });
  w.addEventListener("mouseleave", () => showPair(null));
});

/* ---------- pan and zoom ---------- */
let Z = 1, X = 40, Y = 80;
const leftEdge = () => S.story && getComputedStyle($("#story")).display !== "none" ? $("#story").getBoundingClientRect().right : 0;
const rightEdge = () => document.body.classList.contains("panel-open") && innerWidth > 720 ? innerWidth - $("#panel").getBoundingClientRect().left : 0;
/* The drawing area: the whole screen with the side lists as insets, or in Side by side the
   left half of the space between them. X and Y are measured from the pane's corner. */
function pane() {
  if (!sbsOn()) return {x:0, w:innerWidth, l:leftEdge(), r:rightEdge()};
  const l = leftEdge(), w = Math.floor((innerWidth - l - rightEdge()) / 2);
  return {x:l, w, l:0, r:0};
}
function apply() {
  const P = pane(), on = sbsOn();
  Object.assign(viewport.style, on ? {left:P.x + "px", width:P.w + "px", right:"auto"} : {left:"", width:"", right:""});
  Object.assign(viewport2.style, on ? {left:(P.x + P.w) + "px", width:P.w + "px"} : {left:"", width:""});
  Object.assign($("#sbsbar").style, sbsJourneys() ? {display:"flex", left:P.x + "px", width:(2 * P.w) + "px"} : {display:"none"});
  const tf = `translate(${X}px,${Y}px) scale(${Z})`;
  world.style.transform = tf; world2.style.transform = tf;
  document.documentElement.style.setProperty("--z", Z);
  const inv = Math.min(2.4, Math.max(1, 0.62 / Z));
  const changed = document.body.classList.contains("z-far") !== (Z < 0.55) ||
    document.documentElement.style.getPropertyValue("--inv") !== String(inv);
  document.documentElement.style.setProperty("--inv", inv);
  document.body.classList.toggle("z-far", Z < 0.55);
  if (changed) layout();
  pairline.style.display = "none";
}
function zoomAt(f, cx, cy) {
  const P = pane();
  const ox = sbsOn() && cx >= P.x + P.w ? P.x + P.w : P.x;
  const lx = cx - ox;
  const nz = Math.min(MAX_Z, Math.max(MIN_Z, Z * f));
  X = lx - (lx - X) * (nz / Z); Y = cy - (cy - Y) * (nz / Z); Z = nz; apply();
}
const bottomEdge = () => document.body.classList.contains("panel-open") && innerWidth <= 720 ? innerHeight - $("#panel").getBoundingClientRect().top : 0;
const topEdge = () => (S.notesOnMap && NOTES.length ? TOP_H + 50 : TOP_H) + (sbsJourneys() ? 92 : sbsOn() ? 34 : 0);
const viewCenter = () => { const P = pane(); return [P.x + P.l + (P.w - P.l - P.r) / 2, topEdge() + (innerHeight - topEdge() - bottomEdge()) / 2]; };
function fitTo(b) {
  const P = pane();
  const vw = P.w - P.l - P.r - 40, vh = innerHeight - topEdge() - bottomEdge() - 40;
  const zw = vw / b.w * 0.96, zh = vh / b.h * 0.95;
  let z = Math.min(zw, zh);
  // A tall map would shrink until its words are unreadable: fit the width instead and start
  // at the top, so people scroll down through readable boxes.
  const tall = zh < 0.62 && zw > zh * 1.2;
  if (tall) z = Math.min(1, Math.max(sbsOn() ? MIN_Z : 0.5, zw));
  // A wide map (one long journey) has the same problem sideways: fit the height instead, at a
  // readable size, and start at the left so people scroll across.
  const wide = !tall && zw < 0.62 && zh > zw * 1.2;
  if (wide) z = Math.min(1, Math.max(0.62, Math.min(zh, 0.9)));
  // Never fit a whole map below a readable size: start at the top left instead, and let the
  // list on the left be the overview (pick a journey there to frame just that one).
  const tiny = !tall && !wide && z < 0.5 && !sbsOn();
  if (tiny) z = 0.55;
  Z = Math.min(1.3, Math.max(sbsJourneys() ? 0.55 : MIN_Z, z));   // one journey side by side: text stays readable
  X = P.l + 20 + (wide || tiny ? 0 : Math.max(0, (vw - b.w * Z) / 2)) - b.x * Z;
  Y = topEdge() + 20 + (tall || tiny ? 0 : Math.max(0, (vh - b.h * Z) / 2)) - b.y * Z;
  apply();
}
function fitRow(key) {
  const r = rows.find(r => r.key === key);
  if (r) fitTo({x:r.x - 10, y:r.y - 30, w:r.w + 20, h:r.h + 60});
}
function fit() { if (S.journey >= 0 && !sbsJourneys()) fitRow("j" + S.journey); else fitTo(bounds); }
/* With notes on the map the whole drawing is wide; on first open, start at a size where the
   stickies can be read and begin at the top left, rather than shrinking everything. */
function fitReadable() {
  if (!S.notesOnMap || Z >= 0.8 || sbsOn()) return;
  const P = pane();
  Z = 0.8; X = P.l + 20 - bounds.x * Z; Y = topEdge() + 20 - bounds.y * Z;
  apply();
}
function centerOn(el) {
  if (Z < 0.75) {
    // zooming in can rebuild the drawing (text sizes change), so find the box again after
    Z = 0.9; apply();
    el = (el.dataset.k && world.querySelector(`[data-k="${el.dataset.k}"]`)) || el;
  }
  const x = parseFloat(el.style.left) + el.offsetWidth / 2, y = parseFloat(el.style.top) + el.offsetHeight / 2;
  const [cx, cy] = viewCenter();
  X = cx - pane().x - x * Z; Y = cy - y * Z; apply();
}
let drag = null;
[viewport, viewport2].forEach(vp => {
  vp.addEventListener("pointerdown", e => {
    if (e.target.closest(".box,.notecard,.morenotes,button,[role=button],.term")) return;
    drag = {x:e.clientX, y:e.clientY, X, Y, vp}; vp.classList.add("dragging"); vp.setPointerCapture(e.pointerId);
  });
  vp.addEventListener("pointermove", e => { if (!drag) return; X = drag.X + e.clientX - drag.x; Y = drag.Y + e.clientY - drag.y; apply(); });
  vp.addEventListener("pointerup", () => { if (drag) drag.vp.classList.remove("dragging"); drag = null; });
  vp.addEventListener("wheel", e => {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) zoomAt(Math.exp(-e.deltaY * 0.01), e.clientX, e.clientY);
    else { X -= e.deltaX; Y -= e.deltaY; apply(); }
  }, {passive:false});
});
$("#zin").addEventListener("click", () => zoomAt(1.25, ...viewCenter()));
$("#zout").addEventListener("click", () => zoomAt(1 / 1.25, ...viewCenter()));
$("#zfit").addEventListener("click", () => fit());

/* ---------- focus ---------- */
function applyFocus() {
  const on = S.journey >= 0 && KIND[MODEL.maps[S.map].template] === "journeys" && !sbsJourneys();
  document.body.classList.toggle("dim", on);
  world.querySelectorAll(".inj").forEach(el => el.classList.toggle("hot", on && el.dataset.row === "j" + S.journey));
  svg.querySelectorAll("path").forEach(p => p.classList.toggle("hot", on && p.dataset.row === "j" + S.journey));
  if (sbsOn()) syncPanes();
}
function showMap(i) { if (i !== S.map) { S.map = i; S.journey = -1; persist(); render(); } }
function focusJourney(mi, ji) {
  showMap(mi);
  if (sbsJourneys()) { S.sbsJourney = ji; persist(); render(); fit(); return; }
  S.journey = ji; persist(); applyFocus(); story(); fit();
}
function focusRow(mi, key) { showMap(mi); S.journey = -1; persist(); applyFocus(); story(); fitRow(key); }
function setMode(m) { S.mode = m; if (m !== "changes") S.sbs = false; persist(); render(); }
function setSideBySide(on) {
  if (on && innerWidth < 1000) return toast("Side by side needs a wider window. What changes shows the same on one map.");
  S.sbs = on; if (on) S.mode = "changes"; persist(); render(); fit();
}

/* ---------- top bar ---------- */
/* Words, not icons: the view switch, one View menu for display options, the questions, the
   save button and Tools. */
function modeSwitch(where) {
  const m = MODEL.maps[S.map];
  if (!hasChanges(m)) return "";
  const mode = modeOf(m);
  return `<div class="seg mode-seg ${where}" role="group" aria-label="Today, planned, or what changes">
    ${Object.entries(MODES).map(([k, l]) => `<button data-mode="${k}" aria-pressed="${mode === k && !(k === "changes" && sbsOn())}">${l}</button>`).join("")}
    <button data-sbs class="sbs" aria-pressed="${sbsOn()}">Side by side</button></div>`;
}
function wireModeSwitch(root) {
  root.querySelectorAll("[data-mode]").forEach(b => b.addEventListener("click", () => { setMode(b.dataset.mode); b.dataset.mode === "changes" ? fitFirstChange() : fit(); }));
  root.querySelectorAll("[data-sbs]").forEach(b => b.addEventListener("click", () => { setSideBySide(!sbsOn()); if (sbsOn()) fitFirstChange(); }));
}
/* On a journey map the changes can sit far down: start at the first journey that changes. */
function fitFirstChange() {
  const m = MODEL.maps[S.map];
  const ji = (m.journeys || []).findIndex(j => (j.steps || []).some(s => s.when === "today" || s.when === "planned"));
  if (KIND[m.template] === "journeys" && ji > 0 && !sbsJourneys()) fitRow("j" + ji); else fit();
}
function viewItems() {
  const details = Object.values(BOX).some(info => info.mi === S.map && info.box.detail);
  return [
    NOTES.length ? ["notes", "Notes on the map", S.notesOnMap] : null,
    (MODEL.links || []).length ? ["lines", "All connections", S.lines] : null,
    details ? ["tech", "Technical names on the map", S.tech] : null,
    ["dots", "Background dots", S.dots],
    ["story", "List on the left", leftEdge() > 0],
    TERMS.length ? ["glossary", "Word meanings", ""] : null,
    ["key", "What the colours mean", ""],
  ].filter(Boolean);
}
function topBar() {
  const qn = questionList().length;
  $("#top").innerHTML = `
    <span class="title" title="${esc(MODEL.title)}">${esc(MODEL.title)}</span>
    ${modeSwitch("in-top")}
    <button id="tview" aria-haspopup="true" aria-expanded="false">View ▾</button>
    <button id="tquestions" class="primary"><span class="wide-label">Questions to decide</span><span class="short-label">Questions</span><span class="count">${qn}</span></button>
    <button id="tsave" class="save-primary" aria-label="${SESSION ? S.sessionFinished ? "Read my answers" : "Finish review" : "Save my answers"}">${SESSION ? S.sessionFinished ? '<span class="wide-label">Read my answers</span><span class="short-label">Answers</span>' : '<span class="wide-label">Finish review</span><span class="short-label">Finish</span>' : '<span class="wide-label">Save my answers</span><span class="short-label">Save</span>'}</button>
    <button id="tshare" aria-haspopup="true" aria-expanded="false">Tools ▾</button>`;
  roleStrip();
  wireModeSwitch($("#top"));
  $("#tview").addEventListener("click", e => menu(e.currentTarget, viewItems()));
  $("#tquestions").addEventListener("click", () => open("questions"));
  $("#tsave").addEventListener("click", () => SESSION && S.sessionFinished ? open("reviewsummary") : saveReview());
  $("#tshare").addEventListener("click", e => menu(e.currentTarget, [
    ["walk", "Walk me through it", ""],
    ["mapnotes", "Add a free note to the map", ""],
    ...(hasChanges(MODEL.maps[S.map]) ? [["walkchanges", "Walk through the changes", ""]] : []),
    [SESSION ? "backup" : "save", SESSION ? "Download a backup copy" : "Save my answers as a file", ""],
    ["copy", "Copy the questions as a list", ""], ["paper", "Print the questions", ""],
    ["print", "Print this view", ""], ["roles", "Whose notes to show", ""],
    ["key", "What the colours mean", ""], ["keys", "Keyboard shortcuts", ""],
    ["reset", "Clear my answers on this computer", ""]]));
}

function roleStrip() {
  let strip = $("#role-strip");
  if (!strip) { strip = document.createElement("nav"); strip.id = "role-strip"; strip.setAttribute("aria-label", "Perspectives on the map"); document.body.appendChild(strip); }
  const used = ROLES.filter(r => NOTES.some(n => n.role === r.id));
  strip.hidden = !S.notesOnMap || !used.length;
  strip.style.left = (leftEdge() + 12) + "px";
  strip.style.right = (rightEdge() + 12) + "px";
  strip.style.maxWidth = Math.max(60, innerWidth - leftEdge() - rightEdge() - 24) + "px";
  strip.innerHTML = `<span class="role-caption">Perspectives</span>` + used.map(r => `<button data-map-role="${esc(r.id)}" aria-pressed="${S.roles[r.id] !== false}" title="${esc(r.label)} notes · ${S.roles[r.id] !== false ? "shown" : "hidden"}"><span class="paper-swatch" style="background:${esc(tint(r.color))};border-color:${esc(r.color)}"></span>${esc(r.label)}</button>`).join("");
  strip.querySelectorAll("button").forEach(button => button.addEventListener("click", () => { const role = button.dataset.mapRole; S.roles[role] = S.roles[role] === false; persist(); render(); fit(); const next = $("#role-strip [data-map-role=" + CSS.escape(role) + "]"); if (next) next.focus(); }));
}

function menu(btn, items) {
  const mm = $("#menu");
  const reopen = mm.classList.contains("open") && mm._from === btn;
  mm.classList.remove("open");
  document.querySelectorAll("#top [aria-expanded]").forEach(b => b.setAttribute("aria-expanded", "false"));
  if (reopen) return;
  mm._from = btn;
  mm.innerHTML = items.map(([a, label, state]) => typeof state === "boolean"
    ? `<button role="menuitemcheckbox" aria-checked="${state}" aria-label="${label}" data-a="${a}"><span>${label}</span><span class="state" aria-hidden="true">${state ? "On" : "Off"}</span></button>`
    : `<button role="menuitem" data-a="${a}"><span>${label}</span><span class="state">${state}</span></button>`).join("");
  const r = btn.getBoundingClientRect();
  mm.style.left = Math.max(8, Math.min(r.left, innerWidth - 290)) + "px"; mm.style.top = (r.bottom + 6) + "px";
  mm.classList.add("open"); btn.setAttribute("aria-expanded", "true");
  mm.querySelectorAll("button").forEach(b => b.addEventListener("click", () => { mm.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); act(b.dataset.a); }));
  mm.querySelector("button").focus();
}
document.addEventListener("click", e => { if (!e.target.closest("#menu,#tshare,#tview")) $("#menu").classList.remove("open"); });
function act(a) {
  if (a === "walk") walk(0);
  if (a === "walkchanges") walkChanges(0);
  if (a === "mapnotes") open("mapnotes");
  if (a === "tech" && !Object.values(BOX).some(info => info.mi === S.map && info.box.detail)) return toast("This map has no extra box details.");
  if (a === "lines") { S.lines = !S.lines; persist(); topBar(); applyConnections(); }
  if (a === "glossary") open("glossary");
  if (a === "tech") { S.tech = !S.tech; persist(); render(); if (current) open(current.kind, current.arg); fit(); toast(S.tech ? "Extra box details shown on the map" : "Extra box details hidden on the map"); }
  if (a === "notes") { S.notesOnMap = !S.notesOnMap; persist(); render(); fit(); toast(S.notesOnMap ? "Notes shown beside the boxes" : "Notes shown as a count on each box"); }
  if (a === "roles") open("roles");
  if (a === "story") setStory(leftEdge() === 0);
  if (a === "dots") { S.dots = !S.dots; persist(); document.body.classList.toggle("dots", S.dots); topBar(); }
  if (a === "key") open("key");
  if (a === "keys") open("keys");
  if (a === "save") saveReview();
  if (a === "backup") downloadReview();
  if (a === "copy") copyQuestions();
  if (a === "print") window.print();
  if (a === "paper") printQuestions();
  if (a === "reset" && confirm("Clear your answers, dots and decision notes on this computer?")) {
    S.answers = {}; S.votes = {}; S.decisions = {}; persist(); if (current) open(current.kind, current.arg); topBar();
  }
}

/* ---------- left story list ---------- */
function setStory(on) { document.body.classList.toggle("show-navigation", on); S.story = on; persist(); document.body.classList.toggle("nostory", !on); story(); topBar(); fit(); }
$("#storytab").addEventListener("click", () => setStory(true));
function story() {
  const el = $("#story");
  if (!S.story) { el.innerHTML = ""; return; }
  const views = MODEL.maps.map((m, mi) => {
    const kind = KIND[m.template];
    const cur = mi === S.map;
    let sub = "";
    if (kind === "journeys") sub = (m.journeys || []).map((j, ji) => `<li class="jrow"><button class="mini startj" data-startj="${mi}:${ji}" aria-label="Walk through journey ${mi + 1}.${ji + 1}, ${esc(j.title)}">▶ Start</button><button class="view" data-j="${mi}:${ji}" aria-current="${cur && (sbsJourneys() ? S.sbsJourney === ji : S.journey === ji)}"><b><span class="num">${mi + 1}.${ji + 1}</span>${esc(j.title)}</b><span>${esc(j.summary || plural((j.steps || []).length, "step"))}</span></button></li>`).join("");
    if (kind === "chain") sub = (m.stages || []).map((st, si) => `<li><button class="view" data-row="${mi}:s${si}"><b><span class="num">${mi + 1}.${si + 1}</span>${esc(st.label)}</b><span>${esc(st.sub || "")}</span></button></li>`).join("");
    if (kind === "scoring") sub = [["sc-table", "The table", `${plural(OPTIONS.length, "option")}, ${plural(CRITERIA.length, "thing")} that matter`], ["sc-flip", "What would change the winner", scoreTable().close ? "A close call" : "How steady the result is"]].map(([k, t, d], i) => `<li><button class="view" data-row="${mi}:${k}"><b><span class="num">${mi + 1}.${i + 1}</span>${t}</b><span>${d}</span></button></li>`).join("");
    if (kind === "costs") sub = [["co-chart", "The chart", `Real cost over ${(MODEL.costs || {}).horizon_years || 5} years`], ["co-say", "What the lines say", "Where the cheaper option changes"], ["co-split", "Where the money goes", "Each option, part by part"]].map(([k, t, d], i) => `<li><button class="view" data-row="${mi}:${k}"><b><span class="num">${mi + 1}.${i + 1}</span>${t}</b><span>${d}</span></button></li>`).join("");
    if (kind === "tree") sub = (m.root.children || []).map((b, bi) => `<li><button class="view" data-row="${mi}:b${bi}"><b><span class="num">${mi + 1}.${bi + 1}</span>${esc(b.title)}</b><span>${plural((b.children || []).length, "idea")}</span></button></li>`).join("");
    const tag = hasChanges(m) ? `<span class="viewtag">${countsText(changeList(m))}</span>` : "";
    return `<li class="${cur ? "cur" : ""}"><button class="view top-view" data-map="${mi}" aria-current="${cur && S.journey < 0}"><b><span class="num">${mi + 1}.</span>${esc(m.title)}</b><span>${esc(m.intro || "")}</span>${tag}</button>${cur ? modeSwitch("in-story") : ""}${cur ? `<ol class="sub">${sub}</ol>` : ""}</li>`;
  }).join("");
  const m = MODEL.maps[S.map];
  const changes = hasChanges(m) ? changeList(m) : [];
  const qs = questionList(), done = qs.filter(q => answerDone(q.n)).length;
  const active = current && current.kind;
  el.innerHTML = `<button class="hide" data-hide>Hide list</button>
    <div class="small">The decision</div><p class="q">${gl(MODEL.question, true)}</p>
    <button class="walkbtn" data-walk>▶ Walk me through it</button>
    <h2>The maps</h2><ol class="maps">${views}</ol>
    ${changes.length ? `<h2>What changes on this map</h2><p class="chg-legend">${countsHtml(changes)}</p>
      <button class="walkbtn alt" data-walk-changes>▶ Walk through the changes</button>
      <ol class="changes">${changes.map((c, i) => `<li><button class="view chg" data-change="${i}"><span class="ribbon ${c.change}">${CHANGE_WORD[c.change]}</span><b>${esc(titleOf(c.box))}</b>${c.before ? `<span>Today: ${esc(titleOf(c.before))}</span>` : ""}</button></li>`).join("")}</ol>` : ""}
    <h2>Your review</h2><p class="small">${done} of ${qs.length} questions answered</p>
    <div class="more workflow">
      <button data-open="reviewstart" aria-current="${active === 'reviewstart'}">1. Understand the decision</button>
      <button data-give aria-current="${active === 'review' || active === 'questions'}">2. Give your view</button>
      <button data-open="reviewsummary" aria-current="${active === 'reviewsummary'}">3. Check your answers</button>
    </div>
    <h2>Supporting material</h2><div class="more">
      ${MODEL.comparison ? `<button data-open="comparison">Compare the options</button>` : ""}
      ${MODEL.framing ? `<button data-open="framing">Before you decide</button>` : ""}
      ${SCORED.length ? `<button data-open="weights">Change the weights</button>` : ""}
      <button data-open="evidence">Supporting sources</button>
      ${DECISIONS.length ? `<button data-open="decisions">Decision record</button>` : ""}
      ${GAPS.length ? `<button data-open="gaps">Changes to consider</button>` : ""}
      ${MODEL.reading ? `<button data-open="reading">How to read the map</button>` : ""}
    </div>`;
  el.querySelector("[data-hide]").addEventListener("click", () => setStory(false));
  el.querySelector("[data-walk]").addEventListener("click", () => walk(0));
  const wc = el.querySelector("[data-walk-changes]"); if (wc) wc.addEventListener("click", () => walkChanges(0));
  el.querySelector("[data-give]").addEventListener("click", () => goReview(Math.max(0, qs.findIndex(q => !answerDone(q.n)))));
  el.querySelectorAll("[data-map]").forEach(b => b.addEventListener("click", () => { showMap(+b.dataset.map); S.journey = -1; persist(); applyFocus(); story(); fit(); }));
  el.querySelectorAll("[data-j]").forEach(b => b.addEventListener("click", () => { const [mi, ji] = b.dataset.j.split(":").map(Number); focusJourney(mi, ji); }));
  el.querySelectorAll("[data-startj]").forEach(b => b.addEventListener("click", () => { const [mi, ji] = b.dataset.startj.split(":").map(Number); walkJourney(mi, ji, 0); }));
  el.querySelectorAll("[data-row]").forEach(b => b.addEventListener("click", () => { const [mi, key] = b.dataset.row.split(":"); focusRow(+mi, key); }));
  el.querySelectorAll("[data-change]").forEach(b => b.addEventListener("click", () => {
    const c = changes[+b.dataset.change];
    if (modeOf(m) === "today" || modeOf(m) === "planned") setMode("changes");
    open("box", c.box.id); jumpTo(c.box.id);
  }));
  wireModeSwitch(el);
  el.querySelectorAll("[data-open]").forEach(b => b.addEventListener("click", () => open(b.dataset.open)));
  wireTerms(el);
}

/* ---------- walk-through ---------- */
function steps() {
  const out = [{title:"The decision", text:MODEL.question + (MODEL.summary ? " " + MODEL.summary : ""), go:() => { showMap(0); S.journey = -1; applyFocus(); story(); fit(); }}];
  if (MODEL.reading) out.push({title:"How to read this", text:MODEL.reading, go:() => { showMap(0); S.journey = -1; applyFocus(); story(); fit(); }});
  MODEL.maps.forEach((m, mi) => {
    const kind = KIND[m.template];
    out.push({title:m.title, text:m.intro || "", go:() => { showMap(mi); S.journey = -1; applyFocus(); story(); fit(); }});
    if (kind === "journeys") (m.journeys || []).forEach((j, ji) => {
      const moments = (j.steps || []).filter(s => s.moment).map(s => s.text);
      out.push({title:`${ji + 1}. ${j.title}`, text:(j.summary || "") + ` ${plural((j.steps || []).length, "step")}.` + (moments.length ? ` Moments that matter: ${moments.join("; ")}.` : ""), go:() => focusJourney(mi, ji)});
    });
    if (kind === "chain") (m.stages || []).forEach((st, si) => {
      const items = arrange(st.items || [], modeOf(m)).map(slot => slotLabel(slot, slot.box.title));
      out.push({title:`${si + 1}. ${st.label}`, text:`${st.sub || ""}. ${items.length ? items.join("; ") + "." : "Nothing here yet."}`, go:() => focusRow(mi, "s" + si)});
    });
    if (kind === "scoring") {
      const r = scoreTable();
      const fails = r.rows.filter(x => x.fails.length).map(x => optName(x.option));
      out.push({title:"Must-haves and scores", text:(fails.length ? `${fails.join(", ")} ${fails.length > 1 ? "fail" : "fails"} a must-have, so ${fails.length > 1 ? "they are" : "it is"} out. ` : "") + (r.leader ? `Top of the table: ${optName(r.leader)}${r.close ? ", but it is a close call" : ""}.` : ""), go:() => focusRow(mi, "sc-table")});
      out.push({title:"What would change the winner", text:r.flips.length ? r.flips.map(f => flipText(f).replace(/<[^>]+>/g, "")).join(" ") : "No small change alters the winner.", go:() => focusRow(mi, "sc-flip")});
    }
    if (kind === "costs") {
      const r = costResult();
      if (r) out.push({title:"Cost over time", text:`Cheapest over ${r.h} years${r.fails.size ? " among options that meet every must-have" : ""}: ${optName(r.cheapest)}. ` + r.crossings.filter(c => !r.fails.has(c.cheaper) && !r.fails.has(c.dearer)).slice(0, 2).map(c => `${optName(c.cheaper)} costs less than ${optName(c.dearer)} from month ${c.month}.`).join(" ") + (WHATIFS.length ? " Try the what-ifs above the chart." : ""), go:() => focusRow(mi, "co-chart")});
    }
    if (kind === "tree") (m.root.children || []).forEach((b, bi) => {
      out.push({title:b.title, text:`Ideas: ${(b.children || []).map(c => c.title).join("; ") || "none yet"}.`, go:() => focusRow(mi, "b" + bi)});
    });
  });
  if (GAPS.length) {
    const best = GAPS.slice().sort((a, b) => ((b.impact || 0) * 2 - (b.effort || 0)) - ((a.impact || 0) * 2 - (a.effort || 0)))[0];
    out.push({title:"Gaps between today and planned", text:`${plural(GAPS.length, "gap")}. Best value first: ${best.title}.`, panel:true, go:() => open("gaps")});
  }
  const qs = questionList();
  const must = qs.filter(q => q.urgency === "must").length;
  out.push({title:"What we need to decide", text:`${plural(qs.length, "question")}, ${must} that must be decided. Answer them on the right, then press Save my answers. Send the downloaded file to the review owner.`, panel:true, go:() => open("questions")});
  return out;
}
let walkAt = -1, walkKind = "tour";
function walk(i) {
  const list = steps();
  if (i < 0 || i >= list.length) return endWalk();
  walkAt = i; walkKind = "tour";
  hideHint();
  const s = list[i];
  if (!s.panel) close();
  s.go();
  const w = $("#walk");
  w.innerHTML = `<div class="step">Step ${i + 1} of ${list.length}</div><h3>${esc(s.title)}</h3><p>${gl(s.text)}</p>
    <div class="row"><button data-w="back"${i === 0 ? " disabled" : ""}>Back</button><span class="grow"></span>
    <button data-w="end">End the walk-through</button><button class="next" data-w="next">${i === list.length - 1 ? "Finish" : "Next"}</button></div>`;
  w.classList.add("open");
  w.querySelector('[data-w="back"]').addEventListener("click", () => walk(walkAt - 1));
  w.querySelector('[data-w="next"]').addEventListener("click", () => walk(walkAt + 1));
  w.querySelector('[data-w="end"]').addEventListener("click", endWalk);
  w.querySelector('[data-w="next"]').focus();
  wireTerms(w);
}
function endWalk() { walkAt = -1; $("#walk").classList.remove("open"); }
let walkCtx = null;
const stepWalk = d => walkKind === "changes" ? walkChanges(walkAt + d) : walkKind === "journey" ? walkJourney(walkCtx.mi, walkCtx.ji, walkAt + d) : walk(walkAt + d);
/* One journey, step by step: the step is outlined on the map and opens on the right. */
function walkJourney(mi, ji, i) {
  showMap(mi);
  const m = MODEL.maps[mi], j = (m.journeys || [])[ji];
  if (!j) return endWalk();
  const slots = arrange(j.steps || [], modeOf(m));
  if (i < 0 || i >= slots.length) return endWalk();
  walkAt = i; walkKind = "journey"; walkCtx = {mi, ji};
  hideHint();
  if (sbsJourneys()) { if (S.sbsJourney !== ji) { S.sbsJourney = ji; persist(); render(); } }
  else if (S.journey !== ji) { S.journey = ji; persist(); applyFocus(); story(); }
  const slot = slots[i], b = slot.box;
  if (sbsJourneys() && !nodes[b.id]) { S.sbsAll = true; persist(); render(); }
  open("box", b.id);
  jumpTo(b.id);
  const lane = (m.lanes || []).find(l => l.id === b.lane);
  const said = [lane ? esc(lane.label) + "." : "", b.status ? esc(STATUS[b.status] || "") + "." : "",
    slot.change === "changed" ? `Today: ${esc(slot.before.text)}.` : slot.change === "new" ? "Not there today." : slot.change === "gone" ? "The plan drops it." : ""].filter(Boolean).join(" ");
  const w = $("#walk");
  w.innerHTML = `<div class="step">${esc(j.title)} · Step ${i + 1} of ${slots.length}</div>
    <h3>${slot.change && slot.change !== "same" ? `<span class="ribbon ${slot.change}">${CHANGE_WORD[slot.change]}</span> ` : ""}${gl(b.text)}</h3><p>${said}</p>
    <div class="row"><button data-w="back"${i === 0 ? " disabled" : ""}>Back</button><span class="grow"></span>
    <button data-w="end">End the walk-through</button><button class="next" data-w="next">${i === slots.length - 1 ? "Finish" : "Next"}</button></div>`;
  w.classList.add("open");
  w.querySelector('[data-w="back"]').addEventListener("click", () => walkJourney(mi, ji, walkAt - 1));
  w.querySelector('[data-w="next"]').addEventListener("click", () => walkJourney(mi, ji, walkAt + 1));
  w.querySelector('[data-w="end"]').addEventListener("click", endWalk);
  w.querySelector('[data-w="next"]').focus();
  wireTerms(w);
}
/* One change at a time: the box is outlined on the map and its before and after open on the right. */
function walkChanges(i) {
  const m = MODEL.maps[S.map];
  const list = changeList(m);
  if (!list.length || i < 0 || i >= list.length) return endWalk();
  walkAt = i; walkKind = "changes";
  hideHint();
  if (modeOf(m) !== "changes") { S.mode = "changes"; persist(); render(); }
  const c = list[i];
  open("box", c.box.id);
  jumpTo(c.box.id);
  const what = c.change === "changed" ? `Today: ${esc(titleOf(c.before))}. In the plan: ${esc(titleOf(c.box))}.`
    : c.change === "new" ? "Not there today. The plan adds it." : "There today. The plan drops it.";
  const w = $("#walk");
  w.innerHTML = `<div class="step">Change ${i + 1} of ${list.length} · ${countsText(list)}</div>
    <h3><span class="ribbon ${c.change}">${CHANGE_WORD[c.change]}</span> ${esc(titleOf(c.box))}</h3><p>${what}</p>
    <div class="row"><button data-w="back"${i === 0 ? " disabled" : ""}>Back</button><span class="grow"></span>
    <button data-w="end">End the walk-through</button><button class="next" data-w="next">${i === list.length - 1 ? "Finish" : "Next"}</button></div>`;
  w.classList.add("open");
  w.querySelector('[data-w="back"]').addEventListener("click", () => walkChanges(walkAt - 1));
  w.querySelector('[data-w="next"]').addEventListener("click", () => walkChanges(walkAt + 1));
  w.querySelector('[data-w="end"]').addEventListener("click", endWalk);
  w.querySelector('[data-w="next"]').focus();
}

/* ---------- first-visit hint ---------- */
function hint() {
  if (S.hintSeen) return;
  const h = $("#hint");
  h.innerHTML = `<b>New here?</b> ${S.story ? "Pick a view on the left" : "Press <b>Show list</b> to pick a view"}, or press <b>Walk me through it</b>. Click any box to read about it. ${hasChanges(MODEL.maps[S.map]) ? "Use <b>Today</b>, <b>Planned</b> and <b>What changes</b> to see the plan. " : ""}${SESSION ? "Answer questions on the right. Your answers save for your agent automatically; press Finish review when ready." : HOST ? "Answer questions on the right, then press Save my answers: they go straight to your agent." : "Answer questions on the right, then press Save my answers. Send the downloaded file to the review owner."}<br><button id="hintok">Got it</button>`;
  h.classList.add("open");
  $("#hintok").addEventListener("click", hideHint);
}
function hideHint() { $("#hint").classList.remove("open"); if (!S.hintSeen) { S.hintSeen = true; persist(); } }

/* ---------- right panel ---------- */
let current = null;
function open(kind, arg, keep) {
  current = {kind, arg};
  applyConnections();
  story();
  const p = $("#panel");
  const [title, html] = PANELS[kind](arg);
  p.innerHTML = `<header><h2 id="ptitle">${title}</h2><button id="pclose">Close</button></header>
    <div class="body">${html}</div>`;
  p.classList.add("open"); document.body.classList.add("panel-open"); topBar();
  p.setAttribute("aria-labelledby", "ptitle");
  $("#pclose").addEventListener("click", close);
  wirePanel(p);
  if (!keep) fit();
  $("#ptitle").setAttribute("tabindex", "-1"); if (!keep) $("#ptitle").focus();
}
function close() {
  $("#panel").classList.remove("open"); document.body.classList.remove("panel-open");
  current = null; topBar(); applyConnections(); world.querySelectorAll(".sel").forEach(x => x.classList.remove("sel")); story(); fit();
}

/* What the plan does to this box: new, gone, or before and after with the words that change. */
function changeSection(id) {
  const c = CHANGE_INFO[id];
  if (!c) return "";
  if (c.change === "new") return `<section class="change new"><span class="ribbon new">New</span><p>Not there today. The plan adds this.</p></section>`;
  if (c.change === "gone") return `<section class="change gone"><span class="ribbon gone">Goes away</span><p>There today. The plan drops it.</p></section>`;
  const before = c.change === "replaced" ? c.box : c.before, after = c.change === "replaced" ? c.by : c.box;
  const field = (label, a, b) => {
    if (!a && !b) return "";
    const [da, db] = a === b ? [esc(a), esc(b)] : wordDiff(a, b);
    return `<div class="ba-row"><div class="ba-label">${label}</div><div class="ba-cell before">${da || "<i>None</i>"}</div><div class="ba-cell after">${db || "<i>None</i>"}</div></div>`;
  };
  const st = x => x.status ? STATUS[x.status] : "";
  return `<section class="change changed"><span class="ribbon changed">Changed</span>
    ${c.change === "replaced" ? `<p>This is how it works today. In the plan it becomes <button class="mini" data-jump-to="${esc(after.id)}">${esc(titleOf(after))}</button>.</p>` : "<p>The plan changes this. Words that go are struck through; words that arrive are marked.</p>"}
    <div class="ba"><div class="ba-row head"><div class="ba-label"></div><div class="ba-cell before">Today</div><div class="ba-cell after">In the plan</div></div>
    ${field(before.title ? "Name" : "What happens", titleOf(before), titleOf(after))}
    ${before.title || after.title ? field("In short", before.text || "", after.text || "") : ""}
    ${field("Status", st(before), st(after))}
    ${S.tech ? field("Technical", before.detail || "", after.detail || "") : ""}</div></section>`;
}
function evidenceHtml(refs) {
  return (refs || []).map(r => {
    const e = EVID[r]; if (!e) return "";
    const s = SRC[e.source] || {};
    const local = SESSION && SESSION.sources && SESSION.sources[s.id];
    const remote = /^https?:\/\//i.test(s.ref || "") ? s.ref : null;
    const sourceLink = local || remote;
    const q = e.kind === "data" ? "" : "“", qq = e.kind === "data" ? "" : "”";
    return `<div class="quote${e.voice ? " voice" : ""}">${q}${esc(e.text)}${qq}
      <span class="src">${e.voice ? "In their words · " : ""}${esc(s.title || e.source)}${s.date ? " · " + esc(s.date) : ""}</span>${sourceLink ? `<a href="${esc(sourceLink)}" target="_blank" rel="noopener noreferrer">Open source</a>` : ""}${e.where || s.ref ? `<p class="small">${esc(s.ref || "")}${e.where ? " · " + esc(e.where) : ""}</p>` : ""}</div>`;
  }).join("");
}
function noteHtml(n, withJump) {
  const r = ROLE[n.role] || {label:n.role, color:"#888"};
  const dec = DECISIONS.filter(d => (d.notes || []).includes(n.id));
  return `<div class="card ${n.urgency || "info"}">
    <div class="small"><span class="swatch" style="background:${r.color}"></span><b>${esc(r.label)}</b> · ${esc(n.author || (SESSION && SESSION.prepared_by) || "Author not recorded")} · ${URG[n.urgency || "info"]}</div>
    <h3 style="margin:4px 0">${gl(n.title, true)}</h3>
    ${n.fromNote ? `<p class="small from-note">From a reviewer note (${esc(n.fromNote.who)}): “${esc(n.fromNote.text)}”</p>` : ""}
    ${n.body ? `<p>${gl(n.body, true)}</p>` : ""}
    ${n.fromNote ? "" : (n.evidence || []).length ? `<button class="mini" data-evidence="${esc(n.evidence.join(","))}">See supporting sources</button>` : `<p class="small">We have not attached a source for this yet.</p>`}
    ${n.question ? `<p><b>Question:</b> ${gl(n.question, true)}</p>${answerHtml(n)}` : ""}
    ${dec.length ? `<p class="small">Part of ${dec.map(d => `<button class="mini" data-open-decision="${esc(d.id)}">decision ${esc(d.id)}</button>`).join(" ")}</p>` : ""}
    ${withJump && BOX[n.anchor] ? `<button class="mini" data-jump-to="${esc(n.anchor)}">Show where this note sits</button>` : ""}
  </div>`;
}
function answerHtml(n) {
  const a = S.answers[n.id] || {};
  const v = S.votes[n.id] || 0;
  const mv = MERGED && MERGED.questions && MERGED.questions[n.id];
  const stance = n.answer_type === "stance";
  const choices = stance ? [["agree", "Agree"], ["change", "Change it"], ["unsure", "Not sure yet"]] : [["unsure", "Not sure yet"]];
  return `${n.recommend ? `<section class="recommendation"><b>Suggested next step</b><p>${gl(n.recommend, true)}</p></section>` : ""}
    ${!stance ? `<label class="answer-label" for="a-${esc(n.id)}">Your answer<span class="sr">: ${esc(n.question)}</span></label>
      <textarea id="a-${esc(n.id)}" data-answer="${esc(n.id)}" placeholder="Answer in your own words. It is fine to be unsure.">${esc(a.answer || "")}</textarea>` : ""}
    ${!stance && a.choice && a.choice !== "unsure" ? `<p class="small">Earlier view: ${esc(a.choice)}. Add a written answer to complete this question.</p>` : ""}
    <div class="answer" role="group" aria-label="${stance ? "Your view" : "Your uncertainty"}">
      ${choices.map(([k, l]) => `<button data-ans="${esc(n.id)}" data-choice="${k}" aria-pressed="${a.choice === k}">${l}</button>`).join("")}
      <button class="mini" data-priority="${esc(n.id)}" aria-pressed="${v > 0}">${v ? `Important · ${plural(v, "vote")}` : "Mark as important"}</button>
    </div><p class="small"><span data-votes-left>${dotsLeft()}</span> votes left to mark what deserves discussion.</p>
    ${mv ? `<button class="mini" data-responses="${esc(n.id)}">Compare earlier responses</button>` : ""}
    ${a.comment ? `<label class="small" for="c-${esc(n.id)}">Earlier comment</label><textarea id="c-${esc(n.id)}" data-comment="${esc(n.id)}">${esc(a.comment)}</textarea>` : ""}`;
}
function questionList() {
  return [...NOTES.filter(n => (n.question || "").trim()), ...replyQuestions()].map(n => {
    const mv = MERGED && MERGED.questions && MERGED.questions[n.id] || {};
    const g = GAPS.find(g => g.id === n.anchor);
    return {id:n.id, n, urgency:n.urgency || "info", dots:(mv.dots || 0) + (S.votes[n.id] || 0), impact:g ? g.impact || 0 : 0};
  }).sort((a, b) => URG_ORDER[a.urgency] - URG_ORDER[b.urgency] || b.dots - a.dots || b.impact - a.impact);
}
const dotsLeft = () => DOT_BUDGET - Object.values(S.votes).reduce((a, b) => a + b, 0);

const PANELS = {
  comparison() {
    const comparison = MODEL.comparison || {}, criteria = comparison.criteria || [], options = comparison.options || [];
    const judgments = {fits:"Fits", mixed:"Tradeoff", does_not_fit:"Does not meet this", unknown:"Not yet known"};
    const importance = {must:"Must-have", important:"Important", nice:"Nice to have"};
    const recommendation = comparison.recommendation;
    return ["Compare the options", `<p>${gl(comparison.why || "Agree what matters before choosing. Compare realistic options, including keeping things as they are when that is a real choice.", true)}</p>
      <h3>What matters</h3>${criteria.length ? `<ul>${criteria.map(c => `<li><b>${esc(c.label)}</b> · ${importance[c.importance || "important"]}</li>`).join("")}</ul>` : "<p>Not agreed yet. Ask the decision owner what matters most.</p>"}
      <h3>How we will compare</h3><p>${gl(comparison.method || "Not agreed yet. Choose a discussion, research or a small trial to match the stakes.", true)}</p>
      ${options.length ? options.map(option => `<section class="card"><h3>${esc(option.title)}</h3><p>${gl(option.summary || "", true)}</p>${criteria.map(criterion => {
        const evaluation = (option.evaluations || []).find(e => e.criterion === criterion.id) || {};
        return `<p><b>${esc(criterion.label)}:</b> ${judgments[evaluation.judgment || "unknown"]}</p><p class="small">${gl(evaluation.reason || "This still needs checking.", true)}</p>${(evaluation.evidence || []).length ? `<button class="mini" data-evidence="${esc(evaluation.evidence.join(","))}">See supporting sources</button>` : ""}`;
      }).join("")}</section>`).join("") : "<p>The alternatives have not been named yet.</p>"}
      ${recommendation ? `<h3>Suggested choice</h3><p><b>${esc((options.find(o => o.id === recommendation.option) || {}).title || recommendation.option)}</b></p><p>${gl(recommendation.reason, true)}</p><p>Remaining risks: ${gl(recommendation.risks || "Not recorded yet.", true)}</p><p class="small">The owner still makes and records the final choice.</p>` : "<p>No choice has been recommended yet.</p>"}
      <h3>When to check again</h3><p>${gl(comparison.review_when || "Not agreed yet. Record what would make you revisit the choice.", true)}</p>`];
  },
  glossary() {
    return ["Word meanings", `<p>These meanings were supplied with this review. Select an underlined word to see its meaning beside it.</p>
      <dl class="word-meanings">${TERMS.slice().sort().map(term => `<dt>${esc(term)}</dt><dd>${esc(GLOSS[term])}</dd>`).join("")}</dl>`];
  },
  box(id) {
    const info = BOX[id]; const b = info.box;
    world.querySelectorAll(".sel").forEach(x => x.classList.remove("sel"));
    if (nodes[id]) nodes[id].classList.add("sel");
    const m = MODEL.maps[info.mi] || {};
    const lane = (m.lanes || []).find(l => l.id === b.lane);
    const gaps = GAPS.filter(g => (g.anchors || []).includes(id));
    const ch = sinceChanged[id];
    const notes = notesOn(id);
    const where = info.kind === "step" ? `Step ${info.k + 1} · ${esc(lane ? lane.label : b.lane)}` : info.kind === "journey" ? `Journey ${info.ji + 1}` : info.kind === "stage" ? `Stage ${info.si + 1}` : info.kind === "option" ? "Option" : info.kind === "criterion" ? (b.kind === "must" ? "Must-have" : `Weighted ${weightOf(b)} of 5`) : info.kind === "whatif" ? "What if" : "";
    const choiceInfo = choicePanelHtml(info, b);
    return [esc(titleOf(b)), `
      ${changeSection(id)}
      <p class="small">${where} ${b.kind ? `<span class="kind inline">${esc(b.kind)}</span>` : ""} ${bpill(b)}</p>
      ${b.status_reason ? `<p><b>${esc(STATUS[b.status] || "Status")}:</b> ${gl(b.status_reason, true)}</p>` : ""}
      ${b.title && b.text ? `<p>${gl(b.text, true)}</p>` : ""}${b.summary ? `<p>${gl(b.summary, true)}</p>` : ""}${b.sub ? `<p>${gl(b.sub, true)}</p>` : ""}
      ${choiceInfo}
      ${b.pain ? `<p><b>Pain point:</b> ${gl(b.pain, true)}</p>` : ""}
      ${b.moment ? `<p><b>A moment that matters.</b> Get this right and people trust the rest.</p>` : ""}
      ${b.feeling ? `<p><i class="feel ${b.feeling}"></i>${FEEL[b.feeling]}</p>` : ""}
      ${sinceAdded.has(id) ? `<p><span class="chip since">New since last review</span></p>` : ""}
      ${ch ? `<p><span class="chip since">Changed since last review</span> ${ch.map(esc).join(", ")}.</p>` : ""}
      ${b.checked ? `<p class="small">Checked ${esc(b.checked)}.</p>` : ""}
      ${visibleLinks().filter(l => l.from === id || l.to === id).length ? `<h3>Connected to this</h3>${visibleLinks().filter(l => l.from === id || l.to === id).map(l => {
        const other = l.from === id ? l.to : l.from;
        return `<p class="connection-description ${l.kind || "flow"}">${esc(l.label)} ${l.from === id ? "→" : "←"} <button class="mini" data-connection-to="${esc(other)}">${esc(titleOf(BOX[other].box))}</button>${modeOf(MODEL.maps[S.map]) === "changes" && l.when && l.when !== "both" ? ` <span class="small">(${l.when === "today" ? "today only" : "in the plan"})</span>` : ""}</p>`;
      }).join("")}` : ""}
      ${b.detail ? `<h3>More about this</h3><p>${gl(b.detail, true)}</p>` : ""}
      ${(b.evidence || []).length ? `<h3>Evidence</h3>${evidenceHtml(b.evidence)}` : ""}
      ${gaps.length ? `<h3>Gaps here</h3>${gaps.map(g => `<button class="mini" data-open-gap="${esc(g.id)}">${esc(g.id)}: ${esc(g.title)}</button>`).join(" ")}` : ""}
      <h3>${notes.length ? `Notes from ${plural(notes.length, "role")}` : "Notes"}</h3>
      ${notes.length ? notes.map(n => noteHtml(n)).join("") : `<p class="small">No notes here from the roles you are showing.</p>`}
      ${roughHtml(id)}`];
  },
  note(n) { return [`${esc((ROLE[n.role] || {}).label || n.role)} note`, noteHtml(n, true)]; },
  mapnotes() {
    return ["Notes on the whole map", `<p class="small">A free note is about the map or the decision as a whole, not one box.</p>${roughHtml(null, false)}
      ${S.myNotes.filter(n => n.anchor).length ? `<h3>Your notes on boxes</h3>${S.myNotes.filter(n => n.anchor).map(n => `<button class="mini" data-jump-note="${esc(n.id)}">${esc(whereTitle(n.anchor))}: ${esc(n.text.slice(0, 60))}</button>`).join(" ")}` : ""}`];
  },
  getreplies(id) {
    const waiting = S.myNotes.filter(n => n.ask && !(n.replies || []).length);
    return ["Get the experts’ replies", `<p>${EXPERTS ? "The experts could not reply here." : "This page is a file, so it cannot ask a model itself."} Two ways to get the replies:</p>
      <h3>1. Run the command</h3><ol><li>Press <b>Save my answers</b>. Your notes and what you asked travel in that file.</li>
      <li>Run, from the folder with the model this map was drawn from:<pre class="cmd">decisioncraft perspectives model.json --notes ${esc(`review-${(S.reviewer || "reviewer").toLowerCase().replace(/[^a-z0-9]+/g, "-")}.json`)} --out replies.json</pre></li>
      <li>Then see the threads:<pre class="cmd">decisioncraft render model.json --reviews replies.json --open</pre></li></ol>
      <button class="save-primary" data-save-review>Save my answers</button>
      <h3>2. Ask your AI agent</h3><p>Copy everything it needs: the decision, the roles, your ${plural(waiting.length || 1, "note")} and the reply format.</p>
      <button class="save-primary" data-copyprompt>Copy prompt for your AI agent</button>`];
  },
  lane(d) {
    const m = MODEL.maps[d.mi] || {}, l = (m.lanes || [])[d.i] || {};
    const steps = (m.journeys || []).flatMap(j => (j.steps || []).filter(st => st.lane === l.id));
    return [esc(l.label || "Lane"), `${l.sub ? `<p class="small">${esc(l.sub)}</p>` : ""}
      ${l.summary ? `<p>${gl(l.summary, true)}</p>` : "<p class=\"small\">No description for this part yet.</p>"}
      ${l.detail ? (S.tech ? `<h3>Technical</h3><p class="techname">${esc(l.detail)}</p>` : `<p class="small">Technical detail is available. Turn on Technical names on the map in the View menu.</p>`) : ""}
      <h3>${plural(steps.length, "step")} here</h3>${steps.map(st => `<button class="mini" data-jump-to="${esc(st.id)}">${esc(st.text)}</button>`).join(" ")}`];
  },
  notes(arg) { return [arg.title, NOTES.filter(n => arg.anchors.includes(n.anchor) && S.roles[n.role] !== false).map(n => noteHtml(n, true)).join("")]; },
  outcome(o) {
    return [esc(o.measure), `${o.baseline ? `<p><b>Before:</b> ${esc(o.baseline)}</p>` : ""}${o.target ? `<p><b>Target:</b> ${esc(o.target)}</p>` : ""}
      <p><b>Result:</b> ${o.result ? esc(o.result) : "Not measured yet."}</p>${o.checked ? `<p class="small">Measured ${esc(o.checked)}.</p>` : ""}
      ${o.becomes_evidence ? `<h3>Feeds back as evidence</h3>${evidenceHtml([o.becomes_evidence])}` : ""}`];
  },
  weights() {
    const merged = (MERGED && MERGED.weights) || {};
    const r = scoreTable();
    return ["Change the weights", `<p>How much does each thing matter to you, from 0 (not at all) to 5 (a lot)? The table and the winner update as you move a slider. Your weights are saved with your answers.</p>
      ${SCORED.map(c => { const w = weightOf(c), others = merged[c.id] || [];
        return `<div class="wrow"><label for="w-${esc(c.id)}"><b>${esc(c.name)}</b> <span class="wval" id="wv-${esc(c.id)}">${w}</span></label>
          <input type="range" id="w-${esc(c.id)}" min="0" max="5" step="0.5" value="${w}" data-weight="${esc(c.id)}" aria-describedby="wd-${esc(c.id)}">
          <span class="small" id="wd-${esc(c.id)}">The model says ${modelWeight(c)}.${others.length ? " Reviewers: " + others.map(v => esc(v.who) + " " + v.weight).join(", ") + "." : ""}</span></div>`; }).join("")}
      <p id="wnow" aria-live="polite">${r.leader ? `Top now: <b>${esc(optName(r.leader))}</b>${r.close ? " (a close call)" : ""}.` : ""}</p>
      <button class="mini" data-resetw>Use the model's weights</button>`];
  },
  framing() {
    const f = MODEL.framing || {};
    return ["Before you decide", `${(f.premortem || []).length ? `<h3>A year later this went badly. Why?</h3><p class="small">A pre-mortem: imagine the choice has already gone wrong, then list the likely reasons. Guard against each one now.</p><ul>${f.premortem.map(x => `<li>${gl(x, true)}</li>`).join("")}</ul>` : ""}
      ${f.regret && Object.keys(f.regret).length ? `<h3>How will it feel later?</h3><p class="small">The 10-10-10 check: how will you feel about the choice soon, in a while, and much later?</p>${Object.entries(f.regret).map(([k, v]) => `<p><b>In ${esc(k)}:</b> ${gl(v, true)}</p>`).join("")}` : ""}`];
  },
  reading() { return ["How to read this", `<p>${gl(MODEL.reading || "Start with the decision, then answer the review questions.", true)}</p>`]; },
  sources(refs) {
    return ["Supporting sources", evidenceHtml(refs) + `<button class="mini" data-support-back>Back to the question</button>`];
  },
  responses(id) {
    const q = MERGED && MERGED.questions && MERGED.questions[id] || {};
    return ["Earlier responses", `${(q.answers || []).map(a => `<p class="review-answer"><b>${esc(a.who)}:</b> ${esc(a.text)}</p>`).join("")}
      <p class="small">Recorded views: ${q.agree || 0} agree · ${q.change || 0} want a change · ${q.unsure || 0} not sure. These are not written answers.</p>
      ${(q.comments || []).map(c => `<p><b>${esc(c.who)} commented:</b> ${esc(c.text)}</p>`).join("")}
      <button class="mini" data-support-back>Back to the question</button>`];
  },
  handoff() {
    const result = completedHandoff;
    if (!result) return ["Next steps", "<p>The agent will prepare the proposed stories, acceptance criteria and map from your answers.</p>"];
    return ["Next steps for the agent", `<p>Your answers are recorded. These next steps remain proposals for the decision owner.</p>
      ${(result.user_stories || []).map(story => `<section class="card"><h3>${esc(story.story)}</h3><b>Acceptance criteria</b>${story.acceptance_criteria.length ? `<ul>${story.acceptance_criteria.map(c => `<li>${esc(c)}</li>`).join("")}</ul>` : "<p>Not defined yet.</p>"}</section>`).join("")}
      ${(result.missing || []).length ? `<h3>What still needs defining</h3><ul>${result.missing.map(item => `<li>${esc(item)}</li>`).join("")}</ul>` : ""}
      ${result.proposed_model ? '<button class="save-primary" data-proposed-map>See the proposed map</button>' : "<p>The agent still needs to draft a proposed-state map.</p>"}
      <p>Return to chat to discuss the choice and its reasons with your agent.</p>`];
  },
  sessiondone() {
    return ["Your answers are ready for your agent", `<p>Your answers have been saved on this computer, where the agent can read them. You do not need to download or attach a file.</p><p>Return to your agent chat. The agent receives your answers and a request to show the proposed user stories, acceptance criteria and proposed-state map, including what still needs defining. You still make the final decision.</p><button data-open-handoff>See next steps</button><button data-review-summary>${SESSION.close_on_finish ? "Read my answers" : "Check my answers"}</button>${SESSION.close_on_finish ? "<p>To change these answers, ask your agent to reopen the review.</p>" : ""}`];
  },
  saved(filename) {
    return ["Send your saved answers", `<p>Your browser started downloading <b>${esc(filename)}</b>. If it asks where to save it, choose a folder you can find again.</p><ol><li>Send this file to the review owner, or attach it to your agent chat.</li><li>The owner combines the reviews, checks unanswered questions, and records the decision.</li><li>Keep the file so you can return to the discussion.</li></ol><p>Saving does not send anything automatically. A partial review is fine.</p><button data-return-questions>Back to my answers</button>`];
  },
  reviewstart() {
    const qs = questionList();
    const done = qs.filter(q => answerDone(q.n)).length;
    const next = Math.max(0, qs.findIndex(q => !answerDone(q.n)));
    return ["Let's review this decision", `<p class="decision-question">${gl(MODEL.question, true)}</p>
      ${MODEL.summary ? `<p>${gl(MODEL.summary, true)}</p>` : ""}
      <p>We will ask ${plural(qs.length, "question")}, one at a time. Give your view in your own words. If you need more information, choose <b>Not sure yet</b>.</p>
      <p>${SESSION ? "Your answers save automatically for your agent. Check them, then press Finish review and return to chat." : "Then check your answers and save a file to share."} The decision owner makes the final call.</p>
      ${done === qs.length ? `<button class="save-primary" data-review-summary>Check my answers</button>` : `<button class="save-primary" data-review-at="${next}">${done ? "Continue review" : "Answer questions"}</button>`}
      ${done < qs.length ? `<button class="mini" data-review-summary>Check my answers</button>` : ""}
      <button class="mini" data-all-questions>See all questions</button>`];
  },
  review(index) {
    const qs = questionList();
    index = Math.max(0, Math.min(qs.length - 1, Number(index) || 0));
    if (!qs.length) return PANELS.reviewsummary();
    const n = qs[index].n;
    const r = ROLE[n.role] || {label:n.role};
    return [esc(n.question), `<p class="small">Question ${index + 1} of ${qs.length} · ${esc(r.label)}<br>From: ${esc(n.author || (SESSION && SESSION.prepared_by) || "Author not recorded")}</p>
      ${n.body ? `<p>${gl(n.body, true)}</p>` : ""}
      ${answerHtml(n)}
      ${(n.evidence || []).length ? `<button class="mini" data-evidence="${esc(n.evidence.join(","))}">See supporting sources</button>` : ""}
      <div class="review-nav">${index ? `<button data-review-at="${index - 1}">Back</button>` : ""}
      ${index < qs.length - 1 ? `<button class="save-primary" data-review-at="${index + 1}">${SESSION ? "Save and continue" : "Next question"}</button>` : `<button class="save-primary" data-review-summary>Check my answers</button>`}</div>
      <button class="mini" data-review-summary>Pause and check my answers</button>
      <p id="review-progress" class="small" role="status"></p><p id="save-status" class="small"></p>`];
  },
  reviewsummary() {
    const qs = questionList();
    const readOnly = SESSION && SESSION.close_on_finish && S.sessionFinished;
    return ["Check your answers", `<p id="review-progress" role="status"></p>
      <p>You can change any answer or save what you have. Missing answers and uncertainty remain open for discussion.</p>
      ${qs.map((q, i) => { const a = S.answers[q.id] || {}; return `<div class="card"><h3>${gl(q.n.question, true)}</h3>
        <p class="review-answer">${a.answer ? esc(a.answer) : q.n.answer_type === "stance" && a.choice ? esc({agree:"Agree",change:"Change it",unsure:"Not sure yet"}[a.choice]) : a.choice === "unsure" ? "Not sure yet" : "No written answer yet"}</p>
        ${a.choice && q.n.answer_type !== "stance" ? `<p class="small">Recorded view: ${esc(a.choice)}. This does not decide the question.</p>` : ""}
        ${readOnly ? "" : `<button class="mini" data-review-at="${i}">Change answer<span class="sr"> to ${esc(q.n.question)}</span></button>`}</div>`; }).join("")}
      <label for="reviewer">Your name or role (optional)</label><input type="text" id="reviewer" value="${esc(S.reviewer)}" placeholder="For example: Product owner">
      <p id="save-status" class="small"></p><button class="save-primary" data-save-review>${SESSION ? "Finish review" : "Save my answers"}</button>
      <p class="small">${SESSION ? "Your agent receives saved answers on this computer. Press Finish review when you are ready." : "Send the downloaded file to the decision owner, or attach it to your agent chat."}</p>`];
  },
  questions() {
    const qs = questionList();
    let html = `<section class="review-next"><p id="review-progress" role="status"></p><p id="save-status" class="small"></p><button data-save-review class="save-primary">${SESSION ? "Finish review" : "Save my answers"}</button><p class="small">${SESSION ? "Your answers save automatically for the agent that opened this review. Press Finish review when ready. You can leave questions open." : "Send the downloaded file to the review owner or attach it to your agent chat. The owner combines reviews and records the decision. You can save a partial review and return later."}</p></section><p class="small">Every note ends in a question. Answer the ones you can. You have <b id="dleft">${dotsLeft()}</b> of ${DOT_BUDGET} votes to mark what matters most. <span data-local-copy>Answers stay in this browser. Save a file to share.</span></p>
      <label class="small" for="reviewer">Your role, for the saved file</label><input type="text" id="reviewer" value="${esc(S.reviewer)}" placeholder="For example: Product owner">
      ${MERGED ? `<p class="small">Showing answers from ${plural(MERGED.reviewers.length, "reviewer")}: ${MERGED.reviewers.map(esc).join(", ")}.</p>` : ""}`;
    let cur = null;
    qs.forEach(q => {
      if (q.urgency !== cur) { cur = q.urgency; html += `<h3>${URG[cur]}</h3>`; }
      const r = ROLE[q.n.role] || {label:q.n.role, color:"#888"};
      const where = whereTitle(q.n.anchor);
      html += `<div class="card ${cur}"><div class="small"><span class="swatch" style="background:${r.color}"></span>${esc(r.label)} · about <button class="mini" data-jump-to="${esc(q.n.anchor)}">${esc(where)}</button></div>
        ${q.n.fromNote ? `<p class="small from-note">From a reviewer note (${esc(q.n.fromNote.who)}): “${esc(q.n.fromNote.text)}”</p>` : ""}
        <p><b>${gl(q.n.question, true)}</b></p><p class="small">${gl(q.n.body || "", true)}</p>
        ${(q.n.evidence || []).length ? `<button class="mini" data-evidence="${esc(q.n.evidence.join(","))}">See supporting sources</button>` : ""}
        ${answerHtml(q.n)}</div>`;
    });
    if (!qs.length) html += `<p>No questions from the roles you are showing.</p>`;
    return [`Questions to decide (${qs.length})`, html];
  },
  decisions() {
    return [`Decisions (${DECISIONS.length})`, `<p class="small">Each decision has an owner, a status and a date. What you type here is saved with your answers.</p>` +
      DECISIONS.map(d => {
        const mine = S.decisions[d.id] || {};
        const val = k => esc(mine[k] != null ? mine[k] : (d[k] || ""));
        const mv = MERGED && MERGED.decisions && MERGED.decisions[d.id];
        return `<div class="card"><p class="small">${esc(d.id)} · ${DSTATUS[d.status || "open"]}${d.decided_by ? " by " + esc(d.decided_by) : ""}</p>
          <p><b>${gl(d.question, true)}</b></p>
          ${(d.options || []).length ? `<p class="small">Options: ${d.options.map(esc).join(" · ")}</p>` : ""}
          ${d.decision ? `<p><b>Decided:</b> ${esc(d.decision)}</p>` : ""}
          ${(d.notes || []).length ? `<p class="small">Comes from: ${d.notes.map(id => { const n = NOTES.find(x => x.id === id); return `<button class="mini" data-open-note="${esc(id)}">${esc(n ? n.title : id)}</button>`; }).join(" ")}</p>` : ""}
          ${mv && mv.conflict && mv.conflict.length ? `<p class="small"><span class="badge split">Reviewers differ</span> on ${mv.conflict.map(esc).join(", ")}</p>` : ""}
          <div class="row"><label>Owner<input type="text" data-dec="${esc(d.id)}" data-k="owner" value="${val("owner")}"></label>
          <label>Due<input type="date" data-dec="${esc(d.id)}" data-k="due" value="${val("due")}"></label></div>
          <div class="row"><label>Status<select class="field" data-dec="${esc(d.id)}" data-k="status">${Object.entries(DSTATUS).map(([k, l]) => `<option value="${k}"${(mine.status || d.status || "open") === k ? " selected" : ""}>${l}</option>`).join("")}</select></label>
          <label>Decided by<input type="text" data-dec="${esc(d.id)}" data-k="decided_by" value="${val("decided_by")}"></label></div>
          <label>What we decided<textarea data-dec="${esc(d.id)}" data-k="decision">${val("decision")}</textarea></label></div>`;
      }).join("")];
  },
  gaps(sort) {
    sort = sort || "value";
    const score = g => sort === "impact" ? (g.impact || 0) : sort === "effort" ? -(g.effort || 0) : (g.impact || 0) * 2 - (g.effort || 0);
    const list = GAPS.slice().sort((a, b) => score(b) - score(a));
    const meter = (v, label) => `<span class="meter" role="img" aria-label="${label} ${v || 0} of 5">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= (v || 0) ? "on" : ""}"></i>`).join("")}</span>`;
    const plot = `<svg viewBox="0 0 220 160" width="100%" role="img" aria-label="Impact against effort for each gap">
      <rect x="30" y="10" width="180" height="120" fill="#faf9f5" stroke="#d9d6ce"/><line x1="120" y1="10" x2="120" y2="130" stroke="#e5e2da"/><line x1="30" y1="70" x2="210" y2="70" stroke="#e5e2da"/>
      <text x="34" y="22" font-size="9" fill="#1f7a4a">Quick wins</text><text x="160" y="22" font-size="9" fill="#6a6862">Big bets</text>
      <text x="120" y="152" font-size="10" text-anchor="middle" fill="#6a6862">More effort →</text><text x="12" y="70" font-size="10" fill="#6a6862" transform="rotate(-90 12 70)" text-anchor="middle">More impact →</text>
      ${GAPS.map(g => { const x = 30 + ((g.effort || 3) - 0.5) / 5 * 180, y = 130 - ((g.impact || 3) - 0.5) / 5 * 120; return `<circle cx="${x}" cy="${y}" r="9" fill="#2f5bd3" opacity=".85"/><text x="${x}" y="${y + 3}" font-size="8" fill="#fff" text-anchor="middle">${esc(g.id)}</text>`; }).join("")}
    </svg>`;
    return [`Gaps (${GAPS.length})`, `${plot}
      <label class="small">Order<select class="field" id="gsort"><option value="value"${sort === "value" ? " selected" : ""}>Best value first (high impact, low effort)</option><option value="impact"${sort === "impact" ? " selected" : ""}>Biggest impact first</option><option value="effort"${sort === "effort" ? " selected" : ""}>Least effort first</option></select></label>
      ${list.map(g => `<div class="card" id="gap-${esc(g.id)}"><p class="small">${esc(g.id)} · Impact ${meter(g.impact, "Impact")} · Effort ${meter(g.effort, "Effort")}</p>
        <h3 style="margin:2px 0">${gl(g.title, true)}</h3>${g.why ? `<p>${gl(g.why, true)}</p>` : ""}
        ${(g.design || []).length ? `<p class="small"><b>Design principles</b></p><ul class="design">${g.design.map(d => `<li>${gl(d, true)}</li>`).join("")}</ul>` : ""}
        ${g.detail ? (S.tech ? `<p class="small"><b>Technical design</b></p><p class="techname">${esc(g.detail)}</p>` : `<p class="small">Technical design is available. Turn on Technical names on the map in the View menu.</p>`) : ""}
        ${(g.stories || []).map(s => { const sd = typeof s.detail === "string" ? [s.detail] : (s.detail || []);
          return `<p><b>${gl(s.as, true)}</b></p><ul>${(s.done_when || []).map(d => `<li>Done when ${gl(d, true)}</li>`).join("")}
          ${S.tech ? sd.map(d => `<li class="techcheck">Technical check: ${esc(d)}</li>`).join("") : ""}</ul>`; }).join("")}
        ${(g.anchors || []).filter(a => BOX[a]).map(a => `<button class="mini" data-jump-to="${esc(a)}">Show: ${esc(titleOf(BOX[a].box))}</button>`).join(" ")}
        ${(g.stories || []).map((st, k) => `<details class="storynotes"><summary>Notes on story ${k + 1}</summary>${roughHtml(g.id + "#story-" + k, false)}</details>`).join("")}
        ${roughHtml(g.id, "Reviewer notes on this gap")}
        ${notesOn(g.id).map(n => noteHtml(n)).join("")}</div>`).join("")}`];
  },
  evidence(voiceOnly) {
    const outs = MODEL.outcomes || [];
    return ["Evidence and sources", `<label class="switch"><input type="checkbox" id="voiceonly"${voiceOnly ? " checked" : ""}> Only what people said in their own words</label>
      ${(MODEL.sources || []).map(s => {
        const ev = (MODEL.evidence || []).filter(e => e.source === s.id && (!voiceOnly || e.voice));
        if (voiceOnly && !ev.length) return "";
        return `<div class="card"><p><b>${esc(s.title)}</b></p><p class="small">${esc(s.kind || "")}${s.date ? " · " + esc(s.date) : ""}${s.ref ? " · " + esc(s.ref) : ""}</p>${evidenceHtml(ev.map(e => e.id))}</div>`;
      }).join("")}
      ${outs.length ? `<h3>Did it work?</h3>${outs.map(o => `<div class="card"><p><b>${esc(o.measure)}</b></p><p class="small">${o.result ? "Result: " + esc(o.result) : "Not measured yet"}${o.target ? " · Target: " + esc(o.target) : ""}</p></div>`).join("")}` : ""}`];
  },
  roles() {
    const count = id => NOTES.filter(n => n.role === id).length;
    return ["Whose notes to show", `<p class="small">These switches change the notes on the map. The review still includes every question.</p><div class="row"><button class="mini" data-roles="all">Show all</button><button class="mini" data-roles="none">Hide all</button></div>
      ${ROLES.map(r => `<div class="rolerow"><input type="checkbox" id="r-${esc(r.id)}" data-role="${esc(r.id)}"${S.roles[r.id] !== false ? " checked" : ""}>
        <label for="r-${esc(r.id)}"><span class="swatch" style="background:${r.color}"></span><b>${esc(r.label)}</b> <span class="small">${plural(count(r.id), "note")}</span>
        ${r.asks ? `<br><span class="small">Always asks: ${esc(r.asks)}</span>` : ""}
        ${(r.jobs || []).length ? `<br><span class="small">Jobs to be done: ${r.jobs.map(esc).join("; ")}</span>` : ""}</label></div>`).join("")}`];
  },
  key() {
    return ["What the colours mean", `<h3>Status of each box</h3><p class="legend">${Object.keys(STATUS).map(pill).join(" ")}</p>
      <h3>Connections</h3><p>Arrows between steps show their order. Named connections come from this review: purple for flow, blue for supporting evidence, and red dashed lines for feedback. Selecting a box highlights its connections; their names appear in the detail panel. Use All connections to show them together.</p>
      <h3>Notes</h3><p>Each note is one role's comment and ends in a question. A box shows how many notes it has; red means at least one must be decided. The coloured edge on a note shows how urgent it is:</p>
      <p class="legend"><span><span class="swatch" style="background:var(--must)"></span>Must decide</span><span><span class="swatch" style="background:var(--should)"></span>Should decide</span><span><span class="swatch" style="background:var(--info)"></span>For information</span></p>
      <h3>Roles</h3><p class="legend">${ROLES.map(r => `<span><span class="swatch" style="background:${r.color}"></span>${esc(r.label)}</span>`).join(" ")}</p>
      <h3>What changes</h3><p class="legend"><span class="ribbon new">New</span> <span class="ribbon changed">Changed</span> <span class="ribbon gone">Goes away</span></p>
      <p>New boxes have a teal dashed edge, changed ones an amber edge, and boxes that go away are faded and struck through. Open a changed box to see today and the plan side by side. Side by side shows today on the left and the plan on the right.</p>
      <p class="legend"><span class="pill addon">Add-on</span> <span class="pill unsure">Not sure</span> Hover a tag, or open the box, to read why.</p>
      <h3>Marks on boxes</h3><p class="legend"><span class="chip moment">Moment that matters</span> <span class="chip pain">Pain point</span> <span class="chip since">New since last review</span> <span class="chip stale">May be out of date</span></p>`];
  },
  keys() {
    return ["Keyboard shortcuts", `<p class="small">Everything also works with the buttons on screen. These are only shortcuts.</p>
      <ul><li><b>Tab</b> and <b>Enter</b>: move between boxes and open one</li><li><b>W</b>: walk me through it; <b>→</b> and <b>←</b>: next and back during the walk-through</li>
      <li><b>F</b>: fit to screen; <b>+</b> and <b>−</b>: zoom</li><li><b>Q</b>: questions to decide</li><li><b>T</b>: Today, Planned, What changes (where a map has a plan)</li><li><b>S</b>: side by side</li>
      <li><b>N</b>: show all notes on the map</li><li><b>X</b>: show extra box details on the map, when available</li><li><b>1</b> to <b>9</b>: switch view</li><li><b>Esc</b>: close the panel or menu</li></ul>
      <p class="small">Boxes are placed automatically. Drag empty space to move the view. Zoom with Ctrl and scroll, or pinch.</p>`];
  },
};

let supportReturn = null;
function openSupport(kind, arg) {
  supportReturn = {kind:current.kind, arg:current.arg, scroll:$("#panel .body").scrollTop};
  open(kind, arg);
}
async function goReview(index) {
  if (SESSION && !(await syncReview())) { toast("The answers could not be saved. Keep this page open and try again."); return; }
  open("review", index);
}
function wirePanel(p) {
  p.querySelectorAll("[data-weight]").forEach(inp => inp.addEventListener("input", () => {
    const id = inp.dataset.weight, v = +inp.value, c = SCORED.find(x => x.id === id);
    if (c && v === modelWeight(c)) delete S.weights[id]; else S.weights[id] = v;
    persist();
    const out = p.querySelector("#wv-" + CSS.escape(id)); if (out) out.textContent = v;
    const r = scoreTable(), now = p.querySelector("#wnow");
    if (now) now.innerHTML = r.leader ? `Top now: <b>${esc(optName(r.leader))}</b>${r.close ? " (a close call)" : ""}.` : "";
    if (KIND[MODEL.maps[S.map].template] === "scoring") layout();
  }));
  p.querySelectorAll("[data-resetw]").forEach(b => b.addEventListener("click", () => { S.weights = {}; persist(); if (KIND[MODEL.maps[S.map].template] === "scoring") layout(); open("weights"); }));
  p.querySelectorAll("[data-goto-map]").forEach(b => b.addEventListener("click", () => { const [mi, key] = b.dataset.gotoMap.split(":"); focusRow(+mi, key); }));
  p.querySelectorAll("[data-evidence]").forEach(b => b.addEventListener("click", () => openSupport("sources", b.dataset.evidence.split(","))));
  p.querySelectorAll("[data-responses]").forEach(b => b.addEventListener("click", () => openSupport("responses", b.dataset.responses)));
  p.querySelectorAll("[data-support-back]").forEach(b => b.addEventListener("click", () => { if (supportReturn) { const previous = supportReturn; open(previous.kind, previous.arg); $("#panel .body").scrollTop = previous.scroll; } }));
  p.querySelectorAll("[data-priority]").forEach(b => b.addEventListener("click", () => {
    const id = b.dataset.priority;
    if (!S.votes[id] && dotsLeft() <= 0) return toast("No votes left. Unmark another question first.");
    if (S.votes[id]) delete S.votes[id]; else S.votes[id] = 1;
    persist();
    b.setAttribute("aria-pressed", !!S.votes[id]);
    b.textContent = S.votes[id] ? "Important · 1 vote" : "Mark as important";
    p.querySelectorAll("[data-votes-left]").forEach(el => el.textContent = dotsLeft());
    const remaining = $("#dleft"); if (remaining) remaining.textContent = dotsLeft();
  }));
  p.querySelectorAll("[data-review-at]").forEach(b => b.addEventListener("click", () => goReview(+b.dataset.reviewAt)));
  p.querySelectorAll("[data-open-handoff]").forEach(b => b.addEventListener("click", () => open("handoff")));
  p.querySelectorAll("[data-proposed-map]").forEach(b => b.addEventListener("click", () => {
    const index = MODEL.maps.findIndex(m => m.when === "planned" || m.template === "decision-chain" && (m.stages || []).some(stage => (stage.items || []).some(item => item.when === "planned")));
    if (index >= 0) { showMap(index); setMode("planned"); close(); fit(); }
  }));
  p.querySelectorAll("[data-review-summary]").forEach(b => b.addEventListener("click", () => open("reviewsummary")));
  p.querySelectorAll("[data-all-questions]").forEach(b => b.addEventListener("click", () => open("questions")));
  p.querySelectorAll("[data-save-review]").forEach(b => b.addEventListener("click", saveReview));
  p.querySelectorAll("[data-answer]").forEach(t => t.addEventListener("input", () => {
    (S.answers[t.dataset.answer] = S.answers[t.dataset.answer] || {}).answer = t.value;
    persist();
  }));
  updateReviewStatus();
  if (SESSION && SESSION.close_on_finish && S.sessionFinished) {
    p.querySelectorAll("input,textarea,select,[data-review-at],[data-save-review],[data-ans],[data-dot],[data-priority]").forEach(el => el.disabled = true);
    $("#tsave").disabled = false; $("#tsave").textContent = "Read my answers";
  }
  p.querySelectorAll("[data-return-questions]").forEach(b => b.addEventListener("click", () => open("reviewsummary")));
  p.querySelectorAll("[data-connection-to]").forEach(b => b.addEventListener("click", () => { jumpTo(b.dataset.connectionTo); open("box", b.dataset.connectionTo); }));
  p.querySelectorAll("[data-jump-to]").forEach(b => b.addEventListener("click", () => jumpTo(b.dataset.jumpTo)));
  p.querySelectorAll("[data-open-gap]").forEach(b => b.addEventListener("click", () => { open("gaps"); const c = $("#gap-" + CSS.escape(b.dataset.openGap)); if (c) c.scrollIntoView(); }));
  p.querySelectorAll("[data-open-note]").forEach(b => b.addEventListener("click", () => open("note", NOTES.find(n => n.id === b.dataset.openNote))));
  p.querySelectorAll("[data-open-decision]").forEach(b => b.addEventListener("click", () => open("decisions")));
  p.querySelectorAll("[data-ans]").forEach(b => b.addEventListener("click", () => {
    const a = S.answers[b.dataset.ans] = S.answers[b.dataset.ans] || {};
    a.choice = a.choice === b.dataset.choice ? "" : b.dataset.choice; persist();
    b.parentElement.querySelectorAll("[data-ans]").forEach(x => x.setAttribute("aria-pressed", x.dataset.choice === a.choice));
  }));
  p.querySelectorAll("[data-comment]").forEach(t => t.addEventListener("input", () => {
    (S.answers[t.dataset.comment] = S.answers[t.dataset.comment] || {}).comment = t.value; persist();
  }));
  p.querySelectorAll("[data-dot]").forEach(b => b.addEventListener("click", () => {
    const id = b.dataset.dot, d = +b.dataset.d, v = S.votes[id] || 0;
    if (d > 0 && dotsLeft() <= 0) return toast("No votes left. Take one back from another question first.");
    S.votes[id] = Math.max(0, v + d); if (!S.votes[id]) delete S.votes[id]; persist();
    b.parentElement.querySelector(".n").textContent = S.votes[id] || 0;
    const dl = $("#dleft"); if (dl) dl.textContent = dotsLeft();
    p.querySelectorAll("[data-votes-left]").forEach(el => el.textContent = dotsLeft());
  }));
  p.querySelectorAll("[data-dec]").forEach(f => f.addEventListener(f.tagName === "SELECT" ? "change" : "input", () => {
    (S.decisions[f.dataset.dec] = S.decisions[f.dataset.dec] || {})[f.dataset.k] = f.value; persist();
  }));
  const rv = $("#reviewer", p); if (rv) rv.addEventListener("input", () => { S.reviewer = rv.value; persist(); });
  p.querySelectorAll("[data-role]").forEach(c => c.addEventListener("change", () => { S.roles[c.dataset.role] = c.checked; persist(); render(); }));
  p.querySelectorAll("[data-roles]").forEach(b => b.addEventListener("click", () => {
    ROLES.forEach(r => S.roles[r.id] = b.dataset.roles === "all"); persist(); render(); open("roles");
  }));
  const gs = $("#gsort", p); if (gs) gs.addEventListener("change", () => open("gaps", gs.value));
  wireRough(p);
  const vo = $("#voiceonly", p); if (vo) vo.addEventListener("change", () => open("evidence", vo.checked));
  wireTerms(p);
}
function refreshPanel() {
  const body = $("#panel .body"), top = body ? body.scrollTop : 0;
  render();
  if (current) open(current.kind, current.arg, true);
  const nb = $("#panel .body"); if (nb) nb.scrollTop = top;
}
function wireRough(p) {
  p.querySelectorAll("[data-addnote]").forEach(b => b.addEventListener("click", () => {
    const ed = b.parentElement.querySelector(".noteeditor"); ed.hidden = false; b.hidden = true; ed.querySelector("textarea").focus();
  }));
  p.querySelectorAll("[data-cancelnote]").forEach(b => b.addEventListener("click", () => {
    const ed = b.closest(".noteeditor"); ed.hidden = true; delete ed.dataset.editing; const add = ed.parentElement.querySelector("[data-addnote]"); if (add) add.hidden = false;
  }));
  p.querySelectorAll("[data-savenote]").forEach(b => b.addEventListener("click", () => {
    const ed = b.closest(".noteeditor"), text = ed.querySelector("[data-notetext]").value.trim();
    if (!text) return toast("Write something first. A rough note is fine.");
    const name = ed.querySelector("[data-notename]"); if (name && name.value.trim()) S.reviewer = name.value.trim();
    if (ed.dataset.editing) { const n = S.myNotes.find(x => x.id === ed.dataset.editing); if (n) { n.text = text; n.edited_at = new Date().toISOString(); } }
    else S.myNotes.push({id:newNoteId(), anchor:b.dataset.savenote || null, text, author:S.reviewer || "", at:new Date().toISOString(),
      ...(b.dataset.savenote ? {} : {map:MODEL.maps[S.map].id || String(S.map)})});
    persist(); refreshPanel(); toast("Note saved with your answers");
  }));
  p.querySelectorAll("[data-editnote]").forEach(b => b.addEventListener("click", () => {
    const n = S.myNotes.find(x => x.id === b.dataset.editnote); const sec = b.closest(".rough"); const ed = sec.querySelector(".noteeditor");
    ed.hidden = false; ed.dataset.editing = n.id; ed.querySelector("textarea").value = n.text; ed.querySelector("textarea").focus();
  }));
  p.querySelectorAll("[data-delnote]").forEach(b => b.addEventListener("click", () => {
    if (!confirm("Delete this note and any replies to it?")) return;
    S.myNotes = S.myNotes.filter(x => x.id !== b.dataset.delnote); persist(); refreshPanel();
  }));
  p.querySelectorAll("[data-asknote]").forEach(b => b.addEventListener("click", () => {
    const box = p.querySelector(`[data-askbox="${CSS.escape(b.dataset.asknote)}"]`); box.hidden = !box.hidden; if (!box.hidden) box.querySelector("input").focus();
  }));
  p.querySelectorAll("[data-askcancel]").forEach(b => b.addEventListener("click", () => { p.querySelector(`[data-askbox="${CSS.escape(b.dataset.askcancel)}"]`).hidden = true; }));
  p.querySelectorAll("[data-askgo]").forEach(b => b.addEventListener("click", () => {
    const n = S.myNotes.find(x => x.id === b.dataset.askgo); if (!n) return;
    const roles = [...p.querySelectorAll(`[data-askbox="${CSS.escape(n.id)}"] [data-askrole]:checked`)].map(c => c.dataset.askrole);
    if (!roles.length) return toast("Pick at least one role to ask.");
    n.ask = {roles, requested_at:new Date().toISOString()};
    persist();
    if (EXPERTS) askLive(n, roles); else { refreshPanel(); open("getreplies", n.id); }
  }));
  p.querySelectorAll("[data-getreplies]").forEach(b => b.addEventListener("click", () => open("getreplies", b.dataset.getreplies)));
  p.querySelectorAll("[data-copyprompt]").forEach(b => b.addEventListener("click", () => {
    const waiting = S.myNotes.filter(n => n.ask && !(n.replies || []).length);
    const text = expertPrompt(waiting.length ? waiting : S.myNotes);
    const done = () => toast("Copied. Paste it into your AI agent with your answers file.");
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done)); else fallbackCopy(text, done);
  }));
  p.querySelectorAll("[data-jump-note]").forEach(b => b.addEventListener("click", () => { const n = S.myNotes.find(x => x.id === b.dataset.jumpNote); if (n) { jumpTo(n.anchor); open("box", n.anchor); } }));
}
/* In a live session the page asks the experts through the local tool and shows the replies. */
async function askLive(n, roles) {
  n._waiting = true; refreshPanel();
  try {
    let value;
    if (SESSION && SESSION.experts) {
      const response = await fetch(SESSION.base + "/experts", {method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({note:cleanNote(n), roles})});
      value = await response.json();
      if (!response.ok) throw new Error(value.error || "The experts could not reply.");
    } else {
      value = await HOST.askExperts(cleanNote(n), roles, MODEL, reviewData());
    }
    n.replies = value.replies || [];
    n._waiting = false; persist(); refreshPanel(); toast(`${plural(n.replies.length, "reply")} arrived`.replace("replys", "replies"));
  } catch (error) {
    n._waiting = false; refreshPanel(); toast(error.message); open("getreplies", n.id);
  }
}
function jumpTo(id) {
  const info = BOX[id];
  if (info && info.kind === "gap") return open("gaps");
  const mi = mapOfAnchor(id);
  if (mi >= 0) showMap(mi);
  if (info && !nodes[id] && hasChanges(MODEL.maps[S.map])) {
    const c = CHANGE_INFO[id];
    if (c && c.change === "replaced" && modeOf(MODEL.maps[S.map]) === "changes") id = c.by.id;
    else if (info.box.when === "today") setMode("today");
    else if (info.box.when === "planned") setMode("planned");
  }
  if (S.journey >= 0 && info && info.ji !== S.journey) { S.journey = -1; applyFocus(); story(); }
  const el = nodes[id];
  if (el) { world.querySelectorAll(".sel").forEach(x => x.classList.remove("sel")); el.classList.add("sel"); centerOn(el); }
}

/* ---------- clicks on the map ---------- */
function activate(el) {
  const d = el._data; if (!d) return;
  hideHint();
  if (d.type === "box") open("box", d.id);
  else if (d.type === "note") open("note", d.n);
  else if (d.type === "notes") open("notes", d);
  else if (d.type === "outcome") open("outcome", d.o);
  else if (d.type === "expand") { S.sbsAll = true; persist(); render(); fit(); }
  else if (d.type === "lane") open("lane", d);
  else if (d.type === "mapnotes") open("mapnotes");
}
const startFrom = e => { const sj = e.target.closest("[data-startj]"); if (!sj) return false; e.stopPropagation(); const [mi, ji] = sj.dataset.startj.split(":").map(Number); walkJourney(mi, ji, 0); return true; };
world.addEventListener("click", e => { if (startFrom(e)) return;
  const ch = e.target.closest("[data-choice]"); if (ch) { e.stopPropagation(); choiceAction(ch.dataset.choice); return; }
  const co = e.target.closest("[data-choice-open]"); if (co) { e.stopPropagation(); hideHint(); open("box", co.dataset.choiceOpen); return; } const term = e.target.closest(".term"); if (term) { showTerm(term); return; } const el = e.target.closest("[role=button]"); if (el && el._data) activate(el); });
world2.addEventListener("click", e => { if (startFrom(e)) return; const el = e.target.closest("[data-k]"); const t = twin(el); if (t && t._data) activate(t); });
world.addEventListener("keydown", e => {
  const term = e.target.closest(".term"); if (term && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); showTerm(term); return; }
  if (e.target.tagName === "BUTTON") return;   // a real button inside a box handles its own keys
  const el = e.target.closest("[role=button]");
  if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); activate(el); }
});
world.addEventListener("focusin", e => {
  const el = e.target.closest("[role=button]");
  if (!el) return;
  const r = el.getBoundingClientRect();
  if (r.right < leftEdge() || r.left > innerWidth - rightEdge() || r.bottom < TOP_H || r.top > innerHeight) centerOn(el);
});

/* ---------- glossary ---------- */
const gbox = $("#gloss");
function showTerm(el) {
  const k = el.dataset.term; if (!GLOSS[k]) return;
  gbox.innerHTML = `<b>${esc(k)}</b>${esc(GLOSS[k])}`;
  gbox.style.display = "block";
  const r = el.getBoundingClientRect();
  gbox.style.left = Math.min(innerWidth - 320, Math.max(8, r.left)) + "px";
  gbox.style.top = (r.bottom + 8 + 120 > innerHeight ? r.top - gbox.offsetHeight - 8 : r.bottom + 8) + "px";
}
const hideTerm = () => { gbox.style.display = "none"; };
function wireTerms(root) {
  root.querySelectorAll(".term").forEach(t => {
    t.addEventListener("mouseenter", () => showTerm(t)); t.addEventListener("mouseleave", hideTerm);
    t.addEventListener("focus", () => showTerm(t)); t.addEventListener("blur", hideTerm);
    t.addEventListener("click", e => { e.stopPropagation(); showTerm(t); });
  });
}
world.addEventListener("mouseover", e => { const t = e.target.closest(".term"); if (t) showTerm(t); });
world.addEventListener("mouseout", e => { if (e.target.closest(".term")) hideTerm(); });
world.addEventListener("focusin", e => { const term = e.target.closest(".term"); if (term) showTerm(term); });
world.addEventListener("focusout", e => { if (e.target.closest(".term")) hideTerm(); });

/* ---------- share ---------- */
function reviewData() {
  return {format:"decisioncraft-review/1", model:MODEL.title, model_fingerprint:META.fingerprint || "",
    reviewer:S.reviewer || "", saved_at:new Date().toISOString(), answers:S.answers, dots:S.votes, decisions:S.decisions,
    ...(ownWeights() ? {weights:Object.fromEntries(SCORED.map(c => [c.id, weightOf(c)]))} : {}),
    ...(S.whatifs.length ? {whatifs:S.whatifs} : {}),
    ...(S.myNotes.length ? {notes:S.myNotes.map(cleanNote)} : {})};
}
function saveReview() { if (SESSION) finishReview(); else if (HOST && HOST.saveReview) hostSaveReview(); else downloadReview(); }
/* In an MCP App host a download may be blocked by the sandbox: hand the review to the host's
   decisioncraft_save_review tool instead, and fall back to a download if the host refuses. */
async function hostSaveReview() {
  try {
    const value = await HOST.saveReview(reviewData());
    S.lastExport = JSON.stringify([S.answers, S.votes, S.decisions, S.reviewer]);
    persist();
    toast(value && value.path ? `Saved for your agent: ${value.path}` : "Saved for your agent.");
  } catch (error) {
    toast("The host did not accept the answers, so they are downloading instead.");
    downloadReview();
  }
}
function downloadReview() {
  const blob = new Blob([JSON.stringify(reviewData(), null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  const who = (S.reviewer || "reviewer").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  a.href = URL.createObjectURL(blob); a.download = `review-${who || "reviewer"}.json`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  S.lastExport = JSON.stringify([S.answers, S.votes, S.decisions, S.reviewer]);
  persist();
  if (!SESSION) open("saved", a.download);
  toast(SESSION ? "Backup download started. Your agent already receives saved answers." : "Download started. Send the file to the review owner.");
}
function copyQuestions() {
  let out = `# Questions to decide: ${MODEL.title}\n`, cur = null;
  questionList().forEach(q => {
    if (q.urgency !== cur) { cur = q.urgency; out += `\n## ${URG[cur]}\n\n`; }
    const a = S.answers[q.id] || {};
    out += `- ${q.n.question} (${(ROLE[q.n.role] || {label:q.n.role}).label})${a.answer ? ` — my answer: ${a.answer}` : ""}${a.choice ? ` — my view: ${a.choice}` : ""}${a.comment ? ` — ${a.comment}` : ""}\n`;
  });
  const done = () => toast("Copied as a list");
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(out).then(done, () => fallbackCopy(out, done));
  else fallbackCopy(out, done);
}
function printQuestions() {
  const sheet = document.createElement("section"); sheet.id = "paper-review";
  sheet.innerHTML = `<h1>${esc(MODEL.title)}</h1><p><b>The decision:</b> ${esc(MODEL.question)}</p>
    ${MODEL.summary ? `<p>${esc(MODEL.summary)}</p>` : ""}
    <p>Write your own view first. It is fine to say you are not sure. Compare answers together, then have the decision owner record the choice and reason.</p>
    ${questionList().map(q => `<article><h2>${esc(q.n.question)}</h2>${q.n.body ? `<p>${esc(q.n.body)}</p>` : ""}<p>Your answer:</p><div class="paper-space"></div></article>`).join("")}
    <h2>What did we decide?</h2><p>Decision owner: ____________________</p><p>Choice and reason:</p><div class="paper-space"></div><p>What remains open, and who will follow up?</p><div class="paper-space"></div>`;
  document.body.appendChild(sheet); document.body.classList.add("print-review");
  try { window.print(); }
  finally { document.body.classList.remove("print-review"); sheet.remove(); }
}
function fallbackCopy(text, done) {
  const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select();
  try { document.execCommand("copy"); done(); } catch (e) { toast("Could not copy on this browser."); }
  t.remove();
}
let tt;
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.style.display = "block"; clearTimeout(tt); tt = setTimeout(() => t.style.display = "none", 2600); }

/* ---------- optional keyboard shortcuts ---------- */
document.addEventListener("keydown", e => {
  if (e.target.closest("input,textarea,select")) { if (e.key === "Escape") e.target.blur(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === "escape") { $("#menu").classList.remove("open"); hideTerm(); if (walkAt >= 0) endWalk(); else close(); return; }
  if (walkAt >= 0 && (k === "arrowright" || k === "arrowleft")) { stepWalk(k === "arrowright" ? 1 : -1); e.preventDefault(); return; }
  const m = MODEL.maps[S.map];
  if (/^[1-9]$/.test(k) && +k <= MODEL.maps.length) { showMap(+k - 1); fit(); }
  else if (k === "w") walk(0);
  else if (k === "f") fit();
  else if (k === "+" || k === "=") zoomAt(1.25, ...viewCenter());
  else if (k === "-") zoomAt(1 / 1.25, ...viewCenter());
  else if (k === "q") open("questions");
  else if (k === "n") act("notes");
  else if (k === "x") act("tech");
  else if (k === "?") open("keys");
  else if (k === "t" && hasChanges(m)) { const order = ["today", "planned", "changes"]; setMode(order[(order.indexOf(modeOf(m)) + 1) % 3]); fit(); }
  else if (k === "s" && hasChanges(m)) setSideBySide(!sbsOn());
  else return;
  e.preventDefault();
});

/* ---------- print: fit the view to the page width ---------- */
let before = null;
addEventListener("beforeprint", () => { before = {Z, X, Y}; Z = Math.min(1, 1000 / bounds.w); X = 0; Y = 0; apply(); });
addEventListener("afterprint", () => { if (before) { ({Z, X, Y} = before); apply(); } });

/* ---------- start ---------- */
document.title = MODEL.title;
document.body.classList.toggle("dots", S.dots);
document.body.classList.toggle("nostory", !S.story);
render();
fit();
fitReadable();
hint();
if (SESSION) { hideHint(); open("reviewstart"); }
queueSync();
addEventListener("resize", () => { fit(); topBar(); });
};
if (!window.DC_DEFER) window.__dcBoot();
