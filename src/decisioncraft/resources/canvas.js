/* Decisioncraft canvas engine. Reads a decision model from #dc-model and draws it.
   No outside requests. Plain DOM, no libraries.
   The page: one quiet top bar; a numbered story list on the left; the map in the middle;
   a detail panel on the right; zoom buttons bottom right; a walk-through card. */
(function () {
"use strict";

const $ = (s, r) => (r || document).querySelector(s);
const read = id => { const n = document.getElementById(id); return n && n.textContent.trim() ? JSON.parse(n.textContent) : null; };
const MODEL = read("dc-model");
const MERGED = read("dc-merged");
const SINCE = read("dc-since");
const META = read("dc-meta") || {};

const STATUS = {works:"Works today", partial:"Partly there", missing:"Missing", planned:"Planned"};
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
  "decision-chain":"chain","opportunity-tree":"tree"};
const TREE_LEVELS = ["Outcome","Need or pain","Idea","Quick test"];
const MIN_Z = 0.3, MAX_Z = 2.2;
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
const KEY = "decisioncraft:" + (META.fingerprint || MODEL.title);

const sinceAdded = new Set((SINCE && SINCE.added || []).map(x => x.id));
const sinceChanged = Object.fromEntries((SINCE && SINCE.changed || []).map(x => [x.id, x.fields]));

/* ---------- saved state ---------- */
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { saved = {}; }
const S = Object.assign({map:0, mode:"planned", journey:-1, tech:false, notesOnMap:false, dots:true, story:true,
  hintSeen:false, roles:Object.fromEntries(ROLES.map(r => [r.id, true])),
  answers:{}, votes:{}, decisions:{}, reviewer:""}, saved);
ROLES.forEach(r => { if (!(r.id in S.roles)) S.roles[r.id] = true; });
if (S.map >= MODEL.maps.length) S.map = 0;
const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} };

/* ---------- text helpers ---------- */
const esc = t => String(t == null ? "" : t).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const TERMS = Object.keys(GLOSS).sort((a, b) => b.length - a.length);
const TERM_RE = TERMS.length ? new RegExp("\\b(" + TERMS.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")\\b", "i") : null;
function gl(text, focusable) {
  const s = esc(text);
  if (!TERM_RE) return s;
  return s.replace(TERM_RE, m => {
    const key = TERMS.find(t => t.toLowerCase() === m.toLowerCase());
    return `<span class="term" data-term="${esc(key)}"${focusable ? ' tabindex="0"' : ""}>${m}</span>`;
  });
}
const pill = s => s && STATUS[s] ? `<span class="pill ${s}">${STATUS[s]}</span>` : "";
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
  if (m.root) {
    const walk = (n, d, bi) => { BOX[n.id] = {box:n, mi, kind:"node", depth:d, bi}; (n.children || []).forEach((c, i) => walk(c, d + 1, d === 0 ? i : bi)); };
    walk(m.root, 0, -1);
  }
});
GAPS.forEach(g => BOX[g.id] = {box:g, mi:-1, kind:"gap"});
const notesOn = id => NOTES.filter(n => n.anchor === id && S.roles[n.role] !== false);
const mapOfAnchor = a => BOX[a] ? (BOX[a].mi >= 0 ? BOX[a].mi : mapOfAnchor((BOX[a].box.anchors || [])[0])) : -1;
const titleOf = b => b.title || b.label || b.text || b.id;

function badges(b) {
  const out = [];
  if (sinceAdded.has(b.id)) out.push(`<span class="chip new">New</span>`);
  else if (sinceChanged[b.id]) out.push(`<span class="chip changed">Changed</span>`);
  const ref = (MODEL.checked || {}).date;
  if (b.checked && ref && days(ref, b.checked) > FRESH_DAYS) out.push(`<span class="chip stale" title="Checked ${esc(b.checked)}">May be out of date</span>`);
  if (b.moment) out.push(`<span class="chip moment">Moment that matters</span>`);
  if (b.pain) out.push(`<span class="chip pain">Pain point</span>`);
  if (b.feeling) out.push(`<span class="chip"><i class="feel ${b.feeling}"></i>${FEEL[b.feeling]}</span>`);
  const ev = (b.evidence || []).length;
  if (ev) out.push(`<span class="chip">${ev} evidence</span>`);
  const notes = notesOn(b.id);
  if (notes.length) out.push(`<span class="notebadge${notes.some(n => n.urgency === "must") ? " must" : ""}">${plural(notes.length, "note")}</span>`);
  return out.join("");
}
const tech = b => S.tech && b.detail ? `<span class="techname">${esc(b.detail)}</span>` : "";

/* ---------- DOM helpers ---------- */
const world = $("#world"), viewport = $("#viewport");
let nodes = {}, rows = [], svg;
function place(cls, x, y, w, html, data, label) {
  const d = document.createElement("div");
  d.className = cls; d.style.left = x + "px"; d.style.top = y + "px";
  if (w) d.style.width = w + "px";
  d.innerHTML = html;
  if (data) { d.tabIndex = 0; d.setAttribute("role", "button"); d.setAttribute("aria-label", label || ""); d._data = data; }
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
    t.setAttribute("x", (x1 + x2) / 2 + 10); t.setAttribute("y", my + 5); t.textContent = label;
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
function notePile(anchors, x, y, max, rowKey) {
  if (!S.notesOnMap) return 0;
  const list = NOTES.filter(n => anchors.includes(n.anchor) && S.roles[n.role] !== false)
    .sort((a, b) => URG_ORDER[a.urgency || "info"] - URG_ORDER[b.urgency || "info"]);
  const shown = list.slice(0, max);
  const colH = [0, 0];
  shown.forEach(n => {
    const c = colH[0] <= colH[1] ? 0 : 1;
    const r = ROLE[n.role] || {label:n.role, color:"#888"};
    const el = place(`notecard ${n.urgency || "info"} inj`, x + c * (NOTE_W + NOTE_GAP), y + colH[c], NOTE_W,
      `<div><span class="who">${esc(r.label)}</span><span class="urg">${URG[n.urgency || "info"]}</span></div>
       <h5>${esc(n.title)}</h5><div class="q">${esc(n.question || n.body || "")}</div>`,
      {type:"note", n}, `${r.label} note: ${n.title}`);
    el.style.background = tint(r.color);
    el.dataset.row = rowKey;
    colH[c] += el.offsetHeight + NOTE_GAP;
  });
  let h = Math.max(colH[0], colH[1]);
  if (list.length > shown.length) {
    const more = place("morenotes inj", x, y + h, NOTES_W, `+ ${plural(list.length - shown.length, "more note")} here`,
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
  return 40 + t.offsetHeight + 8 + q.offsetHeight + 40;
}

/* ---------- journeys ---------- */
const J = {laneW:260, laneGap:22, stepW:236, stepH:84, rowGap:16, headW:330, headGap:40, bandGap:70};
function renderJourneys(m) {
  const lanes = m.lanes || [];
  const LI = Object.fromEntries(lanes.map((l, i) => [l.id, i]));
  const laneX = i => J.headW + J.headGap + i * (J.laneW + J.laneGap);
  const lanesRight = laneX(lanes.length - 1) + J.laneW;
  const notesX = lanesRight + 48;
  const W = lanesRight + notesWidth();
  let y = header(m, W);
  lanes.forEach((l, i) => place("lanehead", laneX(i), y, J.laneW, `${esc(l.label)}<small>${esc(l.sub || "")}</small>`));
  if (S.notesOnMap) place("label", notesX, y + 4, 0, "Notes from each role");
  y += 60;
  const laneTop = y - 70;
  (m.journeys || []).forEach((j, ji) => {
    const y0 = y;
    const hd = place("box jhead inj", 0, y0, J.headW,
      `<h3><span class="n">${ji + 1}</span>${gl(j.title)}</h3><p>${gl(j.summary || "")}</p>
       ${(j.creates || []).length ? `<p class="sub small"><b>What it leaves behind:</b> ${j.creates.map(esc).join(", ")}</p>` : ""}
       <div class="meta">${badges(j)}<span class="chip">${plural((j.steps || []).length, "step")}</span></div>`,
      {type:"box", id:j.id}, `Journey ${ji + 1}: ${j.title}`);
    hd.dataset.row = "j" + ji;
    nodes[j.id] = hd;
    let sy = y0, prev = null;
    (j.steps || []).forEach((s, k) => {
      const x = laneX(LI[s.lane] || 0) + (J.laneW - J.stepW) / 2;
      const el = place("box step inj", x, sy, J.stepW,
        `<div class="row1"><span class="n">${k + 1}</span><div class="t">${gl(s.text)}</div></div>${tech(s)}
         <div class="meta">${pill(s.status)}${badges(s)}</div>`,
        {type:"box", id:s.id}, `Step ${k + 1} of journey ${ji + 1}: ${s.text}`);
      el.style.minHeight = J.stepH + "px";
      el.dataset.row = "j" + ji;
      nodes[s.id] = el;
      const h = el.offsetHeight;
      if (prev) {
        const p = link(prev.x + J.stepW / 2, prev.y + prev.h, x + J.stepW / 2, sy - 2, "inj");
        p.dataset.row = "j" + ji; arrowHead(x + J.stepW / 2, sy - 2);
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
    Object.assign(bg.style, {left:(laneX(i) - 8) + "px", top:laneTop + "px", width:(J.laneW + 16) + "px", height:(y - laneTop) + "px"});
    world.prepend(bg);
  });
  return {x:0, y:0, w:W, h:y};
}

/* ---------- chain ---------- */
const C = {stageW:300, stageH:96, itemW:250, itemGap:14, perRow:3, gap:64};
function renderChain(m) {
  const itemsX = C.stageW + 50;
  const notesX = itemsX + C.perRow * (C.itemW + C.itemGap) + 34;
  const W = itemsX + C.perRow * (C.itemW + C.itemGap) + notesWidth();
  let y = header(m, W);
  place("label", 0, y, 0, "Stage");
  place("label", itemsX, y, 0, S.mode === "planned" ? "Planned (dashed border = new)" : "What exists today");
  if (S.notesOnMap) place("label", notesX, y, 0, "Notes from each role");
  y += 30;
  let prevStage = null;
  (m.stages || []).forEach((st, si) => {
    const y0 = y;
    const items = (st.items || []).filter(it => (it.when || "both") === "both" || it.when === S.mode);
    const stEl = place("box stage inj", 0, y0, C.stageW,
      `<h3>${gl(st.label)}</h3><p>${gl(st.sub || "")}</p>${tech(st)}<div class="meta">${badges(st)}</div>`,
      {type:"box", id:st.id}, `Stage ${si + 1}: ${st.label}`);
    stEl.style.minHeight = C.stageH + "px";
    stEl.dataset.row = "s" + si;
    nodes[st.id] = stEl;
    let rowMax = 0, iy = y0, col = 0;
    items.forEach(it => {
      const el = place(`box item inj${it.when === "planned" ? " planned-new" : ""}`,
        itemsX + col * (C.itemW + C.itemGap), iy, C.itemW,
        `<h4>${gl(it.title)}</h4><p class="t">${gl(it.text || "")}</p>${tech(it)}<div class="meta">${pill(it.status)}${badges(it)}</div>`,
        {type:"box", id:it.id}, it.title);
      el.dataset.row = "s" + si;
      nodes[it.id] = el;
      rowMax = Math.max(rowMax, el.offsetHeight);
      if (++col === C.perRow) { col = 0; iy += rowMax + C.itemGap; rowMax = 0; }
    });
    let ih = iy - y0 + rowMax;
    if (!items.length) { place("label", itemsX, y0 + 10, 0, S.mode === "planned" ? "Nothing planned here" : "Nothing here today"); ih = 40; }
    const nh = notePile([st.id, ...(st.items || []).map(i => i.id)], notesX, y0, 4, "s" + si);
    const h = Math.max(stEl.offsetHeight, ih, nh);
    rows.push({key:"s" + si, y:y0, h, x:0, w:W});
    if (prevStage) {
      const p = link(C.stageW / 2, prevStage.y + prevStage.h, C.stageW / 2, y0 - 2, "inj", prevStage.verb);
      p.dataset.row = "s" + si; arrowHead(C.stageW / 2, y0 - 2);
    }
    prevStage = {y:y0, h:stEl.offsetHeight, verb:st.verb || ""};
    y = y0 + h + C.gap;
  });
  const outs = MODEL.outcomes || [];
  if (outs.length && m === MODEL.maps.find(mm => KIND[mm.template] === "chain")) {
    place("label", 0, y, 0, "Did it work?");
    y += 26;
    const ow = C.itemW + 60;
    outs.forEach((o, i) => {
      const el = place("box inj", (i % 3) * (ow + C.itemGap), y + Math.floor(i / 3) * 150, ow,
        `<h4>${esc(o.measure)}</h4><p class="t">${o.baseline ? "Before: " + esc(o.baseline) + ". " : ""}${o.target ? "Target: " + esc(o.target) + ". " : ""}${o.result ? "<b>Result: " + esc(o.result) + "</b>" : "Not measured yet."}</p>
         <div class="meta">${o.becomes_evidence ? `<span class="chip">Feeds back as evidence</span>` : ""}</div>`,
        {type:"outcome", o}, `Outcome: ${o.measure}`);
      nodes[o.id] = el;
    });
    rows.push({key:"outcomes", y:y - 26, h:Math.ceil(outs.length / 3) * 150 + 26, x:0, w:W});
    y += Math.ceil(outs.length / 3) * 150 + 20;
  }
  return {x:0, y:0, w:W, h:y};
}

/* ---------- tree ---------- */
const T = {colW:270, colGap:60, nodeH:104, vGap:18};
function renderTree(m) {
  const levels = m.levels || TREE_LEVELS;
  const depthOf = n => n.children && n.children.length ? 1 + Math.max(...n.children.map(depthOf)) : 1;
  const depth = depthOf(m.root);
  const notesX = depth * (T.colW + T.colGap) + 10;
  const W = depth * (T.colW + T.colGap) - T.colGap + notesWidth();
  let y = header(m, W);
  for (let d = 0; d < depth; d++) place("label", d * (T.colW + T.colGap), y, 0, esc(levels[Math.min(d, levels.length - 1)]));
  y += 30;
  let cursor = y;
  const pos = {};
  (function lay(n, d) {
    const kids = n.children || [];
    let cy;
    if (!kids.length) { cy = cursor; cursor += T.nodeH + T.vGap; }
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
    const y0 = Math.min(...ys) + shift, y1 = Math.max(...ys) + T.nodeH + shift;
    own.forEach(i => shifted[i] = pos[i].y + shift);
    const nh = notePile(own, notesX, y0, 4, "b" + bi);
    rows.push({key:"b" + bi, y:y0, h:Math.max(y1 - y0, nh), x:0, w:W});
    shift += Math.max(0, nh - (y1 - y0)) + (S.notesOnMap ? T.vGap : 0);
  });
  shifted[m.root.id] = branches.length ? (shifted[branches[0].id] + shifted[branches[branches.length - 1].id]) / 2 : pos[m.root.id].y;
  const draw = (n, parent, bi) => {
    const p = pos[n.id], ny = shifted[n.id];
    const el = place(`box tree-node l${p.d} inj`, p.x, ny, T.colW,
      `<h4>${gl(n.title)}</h4>${n.text ? `<p class="t">${gl(n.text)}</p>` : ""}${tech(n)}<div class="meta">${pill(n.status)}${badges(n)}</div>`,
      {type:"box", id:n.id}, `${levels[Math.min(p.d, levels.length - 1)]}: ${n.title}`);
    el.style.minHeight = T.nodeH + "px";
    if (bi != null) el.dataset.row = "b" + bi;
    nodes[n.id] = el;
    if (parent) {
      const l = link(pos[parent.id].x + T.colW, shifted[parent.id] + T.nodeH / 2, p.x, ny + T.nodeH / 2, "inj");
      if (bi != null) l.dataset.row = "b" + bi;
    }
    (n.children || []).forEach(c => draw(c, n, bi == null ? branches.indexOf(c) : bi));
  };
  draw(m.root, null, null);
  return {x:0, y:0, w:W, h:Math.max(...Object.values(shifted)) + T.nodeH + 60};
}

/* ---------- render ---------- */
let bounds = {x:0, y:0, w:1000, h:800};
function render() {
  world.innerHTML = "";
  nodes = {}; rows = [];
  svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "links"); svg.setAttribute("aria-hidden", "true");
  world.appendChild(svg);
  const far = document.body.classList.contains("z-far");
  document.body.classList.remove("z-far");          // lay out at full detail, then restore
  const m = MODEL.maps[S.map];
  const kind = KIND[m.template];
  bounds = kind === "journeys" ? renderJourneys(m) : kind === "chain" ? renderChain(m) : renderTree(m);
  if (far) document.body.classList.add("z-far");
  applyFocus();
  topBar();
  story();
}

/* ---------- pan and zoom ---------- */
let Z = 1, X = 40, Y = 80;
const leftEdge = () => S.story ? STORY_W : 0;
const rightEdge = () => document.body.classList.contains("panel-open") ? PANEL_W + 10 : 0;
function apply() {
  world.style.transform = `translate(${X}px,${Y}px) scale(${Z})`;
  document.documentElement.style.setProperty("--z", Z);
  document.documentElement.style.setProperty("--inv", Math.min(2.4, Math.max(1, 0.62 / Z)));
  document.body.classList.toggle("z-far", Z < 0.55);
}
function zoomAt(f, cx, cy) {
  const nz = Math.min(MAX_Z, Math.max(MIN_Z, Z * f));
  X = cx - (cx - X) * (nz / Z); Y = cy - (cy - Y) * (nz / Z); Z = nz; apply();
}
const viewCenter = () => [leftEdge() + (innerWidth - leftEdge() - rightEdge()) / 2, TOP_H + (innerHeight - TOP_H) / 2];
function fitTo(b) {
  const vw = innerWidth - leftEdge() - rightEdge() - 40, vh = innerHeight - TOP_H - 40;
  let z = Math.min(vw / b.w, vh / b.h) * 0.95;
  const tall = z < MIN_Z + 0.08;
  if (tall) z = Math.min(1, Math.max(MIN_Z + 0.1, vw / b.w * 0.96));   // too tall: fit the width, start at the top
  Z = Math.min(1.3, Math.max(MIN_Z, z));
  X = leftEdge() + 20 + Math.max(0, (vw - b.w * Z) / 2) - b.x * Z;
  Y = TOP_H + 20 + (tall ? 0 : Math.max(0, (vh - b.h * Z) / 2)) - b.y * Z;
  apply();
}
function fitRow(key) {
  const r = rows.find(r => r.key === key);
  if (r) fitTo({x:r.x - 10, y:r.y - 30, w:r.w + 20, h:r.h + 60});
}
function fit() { if (S.journey >= 0) fitRow("j" + S.journey); else fitTo(bounds); }
function centerOn(el) {
  const x = parseFloat(el.style.left) + el.offsetWidth / 2, y = parseFloat(el.style.top) + el.offsetHeight / 2;
  if (Z < 0.75) Z = 0.9;
  const [cx, cy] = viewCenter();
  X = cx - x * Z; Y = cy - y * Z; apply();
}
let drag = null;
viewport.addEventListener("pointerdown", e => {
  if (e.target.closest(".box,.notecard,.morenotes,button")) return;
  drag = {x:e.clientX, y:e.clientY, X, Y}; viewport.classList.add("dragging"); viewport.setPointerCapture(e.pointerId);
});
viewport.addEventListener("pointermove", e => { if (!drag) return; X = drag.X + e.clientX - drag.x; Y = drag.Y + e.clientY - drag.y; apply(); });
viewport.addEventListener("pointerup", () => { drag = null; viewport.classList.remove("dragging"); });
viewport.addEventListener("wheel", e => {
  e.preventDefault();
  if (e.ctrlKey || e.metaKey) zoomAt(Math.exp(-e.deltaY * 0.01), e.clientX, e.clientY);
  else { X -= e.deltaX; Y -= e.deltaY; apply(); }
}, {passive:false});
$("#zin").addEventListener("click", () => zoomAt(1.25, ...viewCenter()));
$("#zout").addEventListener("click", () => zoomAt(1 / 1.25, ...viewCenter()));
$("#zfit").addEventListener("click", () => fit());

/* ---------- focus ---------- */
function applyFocus() {
  const on = S.journey >= 0 && KIND[MODEL.maps[S.map].template] === "journeys";
  document.body.classList.toggle("dim", on);
  world.querySelectorAll(".inj").forEach(el => el.classList.toggle("hot", on && el.dataset.row === "j" + S.journey));
  svg.querySelectorAll("path").forEach(p => p.classList.toggle("hot", on && p.dataset.row === "j" + S.journey));
}
function showMap(i) { if (i !== S.map) { S.map = i; S.journey = -1; persist(); render(); } }
function focusJourney(mi, ji) { showMap(mi); S.journey = ji; persist(); applyFocus(); story(); fit(); }
function focusRow(mi, key) { showMap(mi); S.journey = -1; persist(); applyFocus(); story(); fitRow(key); }
function setMode(m) { S.mode = m; persist(); render(); }

/* ---------- top bar ---------- */
function topBar() {
  const qn = questionList().length;
  $("#top").innerHTML = `
    <span class="title" title="${esc(MODEL.title)}">${esc(MODEL.title)}</span>
    <button id="tq" class="primary">Questions to decide<span class="count">${qn}</span></button>
    <button id="tshare" aria-haspopup="true" aria-expanded="false">Share my answers ▾</button>
    <button id="tview" aria-haspopup="true" aria-expanded="false">View ▾</button>
    <button id="tkeys" title="Keyboard shortcuts">? Keys</button>`;
  $("#tq").addEventListener("click", () => open("questions"));
  $("#tshare").addEventListener("click", e => menu(e.currentTarget, [
    ["save", "Save my answers as a file", ""], ["copy", "Copy the questions as a list", ""],
    ["print", "Print this view", ""], ["reset", "Clear my answers on this computer", ""]]));
  $("#tview").addEventListener("click", e => menu(e.currentTarget, [
    ["tech", "Show technical names", S.tech ? "On" : "Off"],
    ["notes", "Show all notes on the map", S.notesOnMap ? "On" : "Off"],
    ["roles", "Whose notes to show", `${ROLES.filter(r => S.roles[r.id] !== false).length} of ${ROLES.length}`],
    ["story", S.story ? "Hide the list on the left" : "Show the list on the left", ""],
    ["dots", "Background dots", S.dots ? "On" : "Off"],
    ["key", "What the colours mean", ""]]));
  $("#tkeys").addEventListener("click", () => open("keys"));
}
function menu(btn, items) {
  const mm = $("#menu");
  const reopen = mm.classList.contains("open") && mm._from === btn;
  mm.classList.remove("open");
  document.querySelectorAll("#top [aria-expanded]").forEach(b => b.setAttribute("aria-expanded", "false"));
  if (reopen) return;
  mm._from = btn;
  mm.innerHTML = items.map(([a, label, state]) => `<button role="menuitem" data-a="${a}"><span>${label}</span><span class="state">${state}</span></button>`).join("");
  const r = btn.getBoundingClientRect();
  mm.style.left = Math.max(8, Math.min(r.left, innerWidth - 290)) + "px"; mm.style.top = (r.bottom + 6) + "px";
  mm.classList.add("open"); btn.setAttribute("aria-expanded", "true");
  mm.querySelectorAll("button").forEach(b => b.addEventListener("click", () => { mm.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); act(b.dataset.a); }));
  mm.querySelector("button").focus();
}
document.addEventListener("click", e => { if (!e.target.closest("#menu,#tshare,#tview")) $("#menu").classList.remove("open"); });
function act(a) {
  if (a === "tech") { S.tech = !S.tech; persist(); render(); if (current) open(current.kind, current.arg); toast(S.tech ? "Technical names shown" : "Technical names hidden"); }
  if (a === "notes") { S.notesOnMap = !S.notesOnMap; persist(); render(); toast(S.notesOnMap ? "Notes shown beside the boxes" : "Notes shown as a count on each box"); }
  if (a === "roles") open("roles");
  if (a === "story") setStory(!S.story);
  if (a === "dots") { S.dots = !S.dots; persist(); document.body.classList.toggle("dots", S.dots); }
  if (a === "key") open("key");
  if (a === "save") saveReview();
  if (a === "copy") copyQuestions();
  if (a === "print") window.print();
  if (a === "reset" && confirm("Clear your answers, dots and decision notes on this computer?")) {
    S.answers = {}; S.votes = {}; S.decisions = {}; persist(); if (current) open(current.kind, current.arg); topBar();
  }
}

/* ---------- left story list ---------- */
function setStory(on) { S.story = on; persist(); document.body.classList.toggle("nostory", !on); story(); }
$("#storytab").addEventListener("click", () => setStory(true));
function story() {
  const el = $("#story");
  if (!S.story) { el.innerHTML = ""; return; }
  const views = MODEL.maps.map((m, mi) => {
    const kind = KIND[m.template];
    const cur = mi === S.map;
    let sub = "";
    if (kind === "journeys") sub = (m.journeys || []).map((j, ji) => `<li><button class="view" data-j="${mi}:${ji}" aria-current="${cur && S.journey === ji}"><b><span class="num">${mi + 1}.${ji + 1}</span>${esc(j.title)}</b><span>${esc(j.summary || plural((j.steps || []).length, "step"))}</span></button></li>`).join("");
    if (kind === "chain") sub = (m.stages || []).map((st, si) => `<li><button class="view" data-row="${mi}:s${si}"><b><span class="num">${mi + 1}.${si + 1}</span>${esc(st.label)}</b><span>${esc(st.sub || "")}</span></button></li>`).join("");
    if (kind === "tree") sub = (m.root.children || []).map((b, bi) => `<li><button class="view" data-row="${mi}:b${bi}"><b><span class="num">${mi + 1}.${bi + 1}</span>${esc(b.title)}</b><span>${plural((b.children || []).length, "idea")}</span></button></li>`).join("");
    const seg = kind === "chain" && cur ? `<div class="seg" role="group" aria-label="Today or planned"><button data-mode="today" aria-pressed="${S.mode === "today"}">Today</button><button data-mode="planned" aria-pressed="${S.mode === "planned"}">Planned</button></div>` : "";
    return `<li><button class="view" data-map="${mi}" aria-current="${cur && S.journey < 0}"><b><span class="num">${mi + 1}.</span>${esc(m.title)}</b><span>${esc(m.intro || "")}</span></button>${seg}<ol class="sub">${sub}</ol></li>`;
  }).join("");
  el.innerHTML = `<button class="hide" data-hide>Hide list</button>
    <div class="small">The decision</div><p class="q">${gl(MODEL.question, true)}</p>
    ${MODEL.reading ? `<details class="reading"><summary>How to read this</summary><p>${gl(MODEL.reading, true)}</p></details>` : ""}
    <button class="walkbtn" data-walk>Walk me through it</button>
    <h2>Views</h2><ol>${views}</ol>
    <h2>Deciding</h2><div class="more">
      <button data-open="questions">Questions to decide (${questionList().length})</button>
      ${DECISIONS.length ? `<button data-open="decisions">Decisions (${DECISIONS.length})</button>` : ""}
      ${GAPS.length ? `<button data-open="gaps">Gaps, ranked (${GAPS.length})</button>` : ""}
      <button data-open="evidence">Evidence and sources (${(MODEL.evidence || []).length})</button>
      <button data-open="roles">Whose notes to show</button>
    </div>
    ${MODEL.summary ? `<h2>About this decision</h2><p class="small">${gl(MODEL.summary, true)}</p>` : ""}`;
  el.querySelector("[data-hide]").addEventListener("click", () => setStory(false));
  el.querySelector("[data-walk]").addEventListener("click", () => walk(0));
  el.querySelectorAll("[data-map]").forEach(b => b.addEventListener("click", () => { showMap(+b.dataset.map); S.journey = -1; persist(); applyFocus(); story(); fit(); }));
  el.querySelectorAll("[data-j]").forEach(b => b.addEventListener("click", () => { const [mi, ji] = b.dataset.j.split(":").map(Number); focusJourney(mi, ji); }));
  el.querySelectorAll("[data-row]").forEach(b => b.addEventListener("click", () => { const [mi, key] = b.dataset.row.split(":"); focusRow(+mi, key); }));
  el.querySelectorAll("[data-mode]").forEach(b => b.addEventListener("click", () => setMode(b.dataset.mode)));
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
      const items = (st.items || []).filter(it => (it.when || "both") === "both" || it.when === S.mode).map(it => it.title);
      out.push({title:`${si + 1}. ${st.label}`, text:`${st.sub || ""}. ${items.length ? items.join("; ") + "." : "Nothing here yet."}`, go:() => focusRow(mi, "s" + si)});
    });
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
  out.push({title:"What we need to decide", text:`${plural(qs.length, "question")}, ${must} that must be decided. Answer them on the right, then use Share my answers.`, panel:true, go:() => open("questions")});
  return out;
}
let walkAt = -1;
function walk(i) {
  const list = steps();
  if (i < 0 || i >= list.length) return endWalk();
  walkAt = i;
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

/* ---------- first-visit hint ---------- */
function hint() {
  if (S.hintSeen) return;
  const h = $("#hint");
  h.innerHTML = `<b>New here?</b> Press <b>Walk me through it</b> on the left for a short tour, or click any box to read about it. Answer questions on the right, then use <b>Share my answers</b>.<br><button id="hintok">Got it</button>`;
  h.classList.add("open");
  $("#hintok").addEventListener("click", hideHint);
}
function hideHint() { $("#hint").classList.remove("open"); if (!S.hintSeen) { S.hintSeen = true; persist(); } }

/* ---------- right panel ---------- */
let current = null;
function open(kind, arg) {
  current = {kind, arg};
  const p = $("#panel");
  const [title, html] = PANELS[kind](arg);
  p.innerHTML = `<header><h2 id="ptitle">${title}</h2><button id="pclose">Close</button></header>
    <div class="body">${kind === "box" || kind === "note" ? `<label class="switch"><input type="checkbox" id="techsw"${S.tech ? " checked" : ""}> Show technical names</label>` : ""}${html}</div>`;
  p.classList.add("open"); document.body.classList.add("panel-open");
  p.setAttribute("aria-labelledby", "ptitle");
  $("#pclose").addEventListener("click", close);
  const sw = $("#techsw"); if (sw) sw.addEventListener("change", () => act("tech"));
  wirePanel(p);
  $("#ptitle").setAttribute("tabindex", "-1"); $("#ptitle").focus();
}
function close() {
  $("#panel").classList.remove("open"); document.body.classList.remove("panel-open");
  current = null; world.querySelectorAll(".sel").forEach(x => x.classList.remove("sel"));
}

function evidenceHtml(refs) {
  return (refs || []).map(r => {
    const e = EVID[r]; if (!e) return "";
    const s = SRC[e.source] || {};
    const q = e.kind === "data" ? "" : "“", qq = e.kind === "data" ? "" : "”";
    return `<div class="quote${e.voice ? " voice" : ""}">${q}${esc(e.text)}${qq}
      <span class="src">${e.voice ? "In their words · " : ""}${esc(s.title || e.source)}${s.kind ? " · " + esc(s.kind) : ""}${s.date ? " · " + esc(s.date) : ""}${e.where ? " · " + esc(e.where) : ""}</span></div>`;
  }).join("");
}
function noteHtml(n, withJump) {
  const r = ROLE[n.role] || {label:n.role, color:"#888"};
  const dec = DECISIONS.filter(d => (d.notes || []).includes(n.id));
  return `<div class="card ${n.urgency || "info"}">
    <div class="small"><span class="swatch" style="background:${r.color}"></span><b>${esc(r.label)}</b> · ${URG[n.urgency || "info"]}</div>
    <h3 style="margin:4px 0">${gl(n.title, true)}</h3>
    ${n.body ? `<p>${gl(n.body, true)}</p>` : ""}
    ${n.recommend ? `<p><b>We suggest:</b> ${gl(n.recommend, true)}</p>` : ""}
    ${(n.evidence || []).length ? evidenceHtml(n.evidence) : `<p class="small">No evidence linked yet.</p>`}
    ${n.question ? `<p><b>Question:</b> ${gl(n.question, true)}</p>${answerHtml(n)}` : ""}
    ${dec.length ? `<p class="small">Part of ${dec.map(d => `<button class="mini" data-open-decision="${esc(d.id)}">decision ${esc(d.id)}</button>`).join(" ")}</p>` : ""}
    ${withJump && BOX[n.anchor] ? `<button class="mini" data-jump-to="${esc(n.anchor)}">Show where this note sits</button>` : ""}
  </div>`;
}
function answerHtml(n) {
  const a = S.answers[n.id] || {};
  const v = S.votes[n.id] || 0;
  const mv = MERGED && MERGED.questions && MERGED.questions[n.id];
  let merged = "";
  if (mv) {
    const tot = (mv.agree + mv.change + mv.unsure) || 1;
    merged = `<div class="tally" aria-hidden="true"><i class="a" style="width:${mv.agree / tot * 100}%"></i><i class="c" style="width:${mv.change / tot * 100}%"></i><i class="u" style="width:${mv.unsure / tot * 100}%"></i></div>
      <div class="small">Reviewers: ${mv.agree} agree · ${mv.change} want a change · ${mv.unsure} not sure · ${plural(mv.dots, "dot")} ${mv.split ? '<span class="badge split">Split</span>' : ""}</div>
      ${(mv.comments || []).map(c => `<p class="small"><b>${esc(c.who)}:</b> ${esc(c.text)}</p>`).join("")}`;
  }
  return `${merged}<div class="answer" role="group" aria-label="Your answer">
      ${[["agree", "Agree"], ["change", "Change it"], ["unsure", "Not sure"]].map(([k, l]) => `<button data-ans="${esc(n.id)}" data-choice="${k}" aria-pressed="${a.choice === k}">${l}</button>`).join("")}
      <span class="dots"><span class="small">Dots</span><button class="mini" data-dot="${esc(n.id)}" data-d="-1" aria-label="Take a dot back">−</button><span class="n">${v}</span><button class="mini" data-dot="${esc(n.id)}" data-d="1" aria-label="Add a dot">+</button></span>
    </div>
    <label class="sr" for="c-${esc(n.id)}">Comment</label>
    <textarea id="c-${esc(n.id)}" data-comment="${esc(n.id)}" placeholder="Your comment (optional)">${esc(a.comment || "")}</textarea>`;
}
function questionList() {
  return NOTES.filter(n => (n.question || "").trim() && S.roles[n.role] !== false).map(n => {
    const mv = MERGED && MERGED.questions && MERGED.questions[n.id] || {};
    const g = GAPS.find(g => g.id === n.anchor);
    return {id:n.id, n, urgency:n.urgency || "info", dots:(mv.dots || 0) + (S.votes[n.id] || 0), impact:g ? g.impact || 0 : 0};
  }).sort((a, b) => URG_ORDER[a.urgency] - URG_ORDER[b.urgency] || b.dots - a.dots || b.impact - a.impact);
}
const dotsLeft = () => DOT_BUDGET - Object.values(S.votes).reduce((a, b) => a + b, 0);

const PANELS = {
  box(id) {
    const info = BOX[id]; const b = info.box;
    world.querySelectorAll(".sel").forEach(x => x.classList.remove("sel"));
    if (nodes[id]) nodes[id].classList.add("sel");
    const m = MODEL.maps[info.mi] || {};
    const lane = (m.lanes || []).find(l => l.id === b.lane);
    const gaps = GAPS.filter(g => (g.anchors || []).includes(id));
    const ch = sinceChanged[id];
    const notes = notesOn(id);
    const where = info.kind === "step" ? `Step ${info.k + 1} · ${esc(lane ? lane.label : b.lane)}` : info.kind === "journey" ? `Journey ${info.ji + 1}` : info.kind === "stage" ? `Stage ${info.si + 1}` : "";
    return [esc(titleOf(b)), `
      <p class="small">${where} ${pill(b.status)}</p>
      ${b.title && b.text ? `<p>${gl(b.text, true)}</p>` : ""}${b.summary ? `<p>${gl(b.summary, true)}</p>` : ""}${b.sub ? `<p>${gl(b.sub, true)}</p>` : ""}
      ${b.pain ? `<p><b>Pain point:</b> ${gl(b.pain, true)}</p>` : ""}
      ${b.moment ? `<p><b>A moment that matters.</b> Get this right and people trust the rest.</p>` : ""}
      ${b.feeling ? `<p><i class="feel ${b.feeling}"></i>${FEEL[b.feeling]}</p>` : ""}
      ${sinceAdded.has(id) ? `<p><span class="chip new">New</span> since the last review.</p>` : ""}
      ${ch ? `<p><span class="chip changed">Changed</span> since the last review: ${ch.map(esc).join(", ")}.</p>` : ""}
      ${b.checked ? `<p class="small">Checked ${esc(b.checked)}.</p>` : ""}
      ${b.detail && S.tech ? `<h3>Technical names</h3><p class="techname">${esc(b.detail)}</p>` : ""}
      ${(b.evidence || []).length ? `<h3>Evidence</h3>${evidenceHtml(b.evidence)}` : ""}
      ${gaps.length ? `<h3>Gaps here</h3>${gaps.map(g => `<button class="mini" data-open-gap="${esc(g.id)}">${esc(g.id)}: ${esc(g.title)}</button>`).join(" ")}` : ""}
      <h3>${notes.length ? `Notes from ${plural(notes.length, "role")}` : "Notes"}</h3>
      ${notes.length ? notes.map(n => noteHtml(n)).join("") : `<p class="small">No notes here from the roles you are showing.</p>`}`];
  },
  note(n) { return [`${esc((ROLE[n.role] || {}).label || n.role)} note`, noteHtml(n, true)]; },
  notes(arg) { return [arg.title, NOTES.filter(n => arg.anchors.includes(n.anchor) && S.roles[n.role] !== false).map(n => noteHtml(n, true)).join("")]; },
  outcome(o) {
    return [esc(o.measure), `${o.baseline ? `<p><b>Before:</b> ${esc(o.baseline)}</p>` : ""}${o.target ? `<p><b>Target:</b> ${esc(o.target)}</p>` : ""}
      <p><b>Result:</b> ${o.result ? esc(o.result) : "Not measured yet."}</p>${o.checked ? `<p class="small">Measured ${esc(o.checked)}.</p>` : ""}
      ${o.becomes_evidence ? `<h3>Feeds back as evidence</h3>${evidenceHtml([o.becomes_evidence])}` : ""}`];
  },
  questions() {
    const qs = questionList();
    let html = `<p class="small">Every note ends in a question. Answer the ones you can. You have <b id="dleft">${dotsLeft()}</b> of ${DOT_BUDGET} dots to mark what matters most. Your answers stay on this computer until you use <b>Share my answers</b>.</p>
      <label class="small" for="reviewer">Your name, for the saved file</label><input type="text" id="reviewer" value="${esc(S.reviewer)}" placeholder="Your name">
      ${MERGED ? `<p class="small">Showing answers from ${plural(MERGED.reviewers.length, "reviewer")}: ${MERGED.reviewers.map(esc).join(", ")}.</p>` : ""}`;
    let cur = null;
    qs.forEach(q => {
      if (q.urgency !== cur) { cur = q.urgency; html += `<h3>${URG[cur]}</h3>`; }
      const r = ROLE[q.n.role] || {label:q.n.role, color:"#888"};
      const where = BOX[q.n.anchor] ? titleOf(BOX[q.n.anchor].box) : q.n.anchor;
      html += `<div class="card ${cur}"><div class="small"><span class="swatch" style="background:${r.color}"></span>${esc(r.label)} · about <button class="mini" data-jump-to="${esc(q.n.anchor)}">${esc(where)}</button></div>
        <p><b>${gl(q.n.question, true)}</b></p><p class="small">${gl(q.n.body || "", true)}</p>
        ${(q.n.evidence || []).length ? `<details><summary class="small">Evidence (${q.n.evidence.length})</summary>${evidenceHtml(q.n.evidence)}</details>` : ""}
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
        ${(g.stories || []).map(s => `<p><b>${gl(s.as, true)}</b></p><ul>${(s.done_when || []).map(d => `<li>Done when ${gl(d, true)}</li>`).join("")}</ul>`).join("")}
        ${(g.anchors || []).filter(a => BOX[a]).map(a => `<button class="mini" data-jump-to="${esc(a)}">Show: ${esc(titleOf(BOX[a].box))}</button>`).join(" ")}
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
    return ["Whose notes to show", `<div class="row"><button class="mini" data-roles="all">Show all</button><button class="mini" data-roles="none">Hide all</button></div>
      ${ROLES.map(r => `<div class="rolerow"><input type="checkbox" id="r-${esc(r.id)}" data-role="${esc(r.id)}"${S.roles[r.id] !== false ? " checked" : ""}>
        <label for="r-${esc(r.id)}"><span class="swatch" style="background:${r.color}"></span><b>${esc(r.label)}</b> <span class="small">${plural(count(r.id), "note")}</span>
        ${r.asks ? `<br><span class="small">Always asks: ${esc(r.asks)}</span>` : ""}
        ${(r.jobs || []).length ? `<br><span class="small">Jobs to be done: ${r.jobs.map(esc).join("; ")}</span>` : ""}</label></div>`).join("")}`];
  },
  key() {
    return ["What the colours mean", `<h3>Status of each box</h3><p class="legend">${Object.keys(STATUS).map(pill).join(" ")}</p>
      <h3>Notes</h3><p>Each note is one role's comment and ends in a question. A box shows how many notes it has; red means at least one must be decided. The coloured edge on a note shows how urgent it is:</p>
      <p class="legend"><span><span class="swatch" style="background:var(--must)"></span>Must decide</span><span><span class="swatch" style="background:var(--should)"></span>Should decide</span><span><span class="swatch" style="background:var(--info)"></span>For information</span></p>
      <h3>Roles</h3><p class="legend">${ROLES.map(r => `<span><span class="swatch" style="background:${r.color}"></span>${esc(r.label)}</span>`).join(" ")}</p>
      <h3>Marks on boxes</h3><p class="legend"><span class="chip moment">Moment that matters</span> <span class="chip pain">Pain point</span> <span class="chip new">New</span> <span class="chip changed">Changed</span> <span class="chip stale">May be out of date</span></p>`];
  },
  keys() {
    return ["Keyboard shortcuts", `<p class="small">Everything also works with the buttons on screen. These are only shortcuts.</p>
      <ul><li><b>Tab</b> and <b>Enter</b>: move between boxes and open one</li><li><b>W</b>: walk me through it; <b>→</b> and <b>←</b>: next and back during the walk-through</li>
      <li><b>F</b>: fit to screen; <b>+</b> and <b>−</b>: zoom</li><li><b>Q</b>: questions to decide</li><li><b>T</b>: today or planned (on a chain view)</li>
      <li><b>N</b>: show all notes on the map</li><li><b>X</b>: show technical names</li><li><b>1</b> to <b>9</b>: switch view</li><li><b>Esc</b>: close the panel or menu</li></ul>
      <p class="small">Move around by dragging or scrolling. Zoom with Ctrl and scroll, or pinch.</p>`];
  },
};

function wirePanel(p) {
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
    if (d > 0 && dotsLeft() <= 0) return toast("No dots left. Take one back from another question first.");
    S.votes[id] = Math.max(0, v + d); if (!S.votes[id]) delete S.votes[id]; persist();
    b.parentElement.querySelector(".n").textContent = S.votes[id] || 0;
    const dl = $("#dleft"); if (dl) dl.textContent = dotsLeft();
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
  const vo = $("#voiceonly", p); if (vo) vo.addEventListener("change", () => open("evidence", vo.checked));
  wireTerms(p);
}
function jumpTo(id) {
  const info = BOX[id];
  if (info && info.kind === "gap") return open("gaps");
  const mi = mapOfAnchor(id);
  if (mi >= 0) showMap(mi);
  if (info && info.kind === "item" && !nodes[id]) setMode(info.box.when === "today" ? "today" : "planned");
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
}
world.addEventListener("click", e => { const el = e.target.closest("[role=button]"); if (el && el._data) activate(el); });
world.addEventListener("keydown", e => {
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

/* ---------- share ---------- */
function reviewData() {
  return {format:"decisioncraft-review/1", model:MODEL.title, model_fingerprint:META.fingerprint || "",
    reviewer:S.reviewer || "", saved_at:new Date().toISOString(), answers:S.answers, dots:S.votes, decisions:S.decisions};
}
function saveReview() {
  const blob = new Blob([JSON.stringify(reviewData(), null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  const who = (S.reviewer || "reviewer").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  a.href = URL.createObjectURL(blob); a.download = `review-${who || "reviewer"}.json`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  toast("Saved. Send the file to whoever runs the review.");
}
function copyQuestions() {
  let out = `# Questions to decide: ${MODEL.title}\n`, cur = null;
  questionList().forEach(q => {
    if (q.urgency !== cur) { cur = q.urgency; out += `\n## ${URG[cur]}\n\n`; }
    const a = S.answers[q.id] || {};
    out += `- ${q.n.question} (${(ROLE[q.n.role] || {label:q.n.role}).label})${a.choice ? ` — my answer: ${a.choice}` : ""}${a.comment ? ` — ${a.comment}` : ""}\n`;
  });
  const done = () => toast("Copied as a list");
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(out).then(done, () => fallbackCopy(out, done));
  else fallbackCopy(out, done);
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
  if (walkAt >= 0 && (k === "arrowright" || k === "arrowleft")) { walk(walkAt + (k === "arrowright" ? 1 : -1)); e.preventDefault(); return; }
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
  else if (k === "t" && KIND[m.template] === "chain") setMode(S.mode === "today" ? "planned" : "today");
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
hint();
addEventListener("resize", () => apply());
})();
