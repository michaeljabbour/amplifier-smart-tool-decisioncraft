/* Decisioncraft as an MCP App view (MCP Apps, protocol 2026-01-26). The host renders this page
   in a sandboxed iframe and talks to it over postMessage JSON-RPC: the view sends ui/initialize,
   then ui/notifications/initialized; the host sends the tool result, whose structuredContent
   carries {model, merged?, since?}. The canvas engine then starts with that model.
   Saving answers and asking the experts go back through the host (tools/call). No outside
   requests; when the host lacks a capability, the canvas falls back to downloads and prompts. */
(function () {
"use strict";
window.DC_DEFER = true;
let nextId = 1, booted = false, hostCaps = {};
const pending = new Map();
const parent = window.parent && window.parent !== window ? window.parent : null;

function post(msg) { if (parent) parent.postMessage(Object.assign({jsonrpc:"2.0"}, msg), "*"); }
function request(method, params) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, {resolve, reject});
    post({id, method, params: params || {}});
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error("The host did not answer.")); } }, 120000);
  });
}
function notify(method, params) { post({method, params: params || {}}); }

function setData(id, value) {
  const n = document.getElementById(id);
  if (n) n.textContent = value == null ? "" : JSON.stringify(value).replace(/</g, "\\u003c");
}
function showWaiting(text) {
  let w = document.getElementById("dc-app-wait");
  if (!w) {
    w = document.createElement("div"); w.id = "dc-app-wait";
    w.style.cssText = "position:fixed;inset:0;display:flex;align-items:center;justify-content:center;font:15px system-ui,sans-serif;color:#555;background:#f7f6f2;z-index:99";
    document.body.appendChild(w);
  }
  w.textContent = text;
}
function boot(sc) {
  const model = sc && (sc.model || (sc.result && sc.result.model));
  if (!model || !model.maps) {
    showWaiting(sc && sc.starter ? "A starter map is ready. Your agent fills it in, then draws it here."
      : sc && sc.plan ? "This was a dry run: nothing to draw yet."
      : "Nothing to draw yet: the tool returned no model.");
    return;
  }
  setData("dc-model", model);
  setData("dc-merged", sc.merged || null);
  setData("dc-since", sc.since || null);
  setData("dc-meta", Object.assign({generator:"decisioncraft", app:true}, sc.meta || {}));
  if (booted) return;  /* one view per tool result; a later call opens its own view */
  const w = document.getElementById("dc-app-wait"); if (w) w.remove();
  booted = true;
  document.title = model.title || "Decision map";
  window.__dcBoot();
  notify("ui/notifications/size-changed", {height: Math.max(640, Math.min(900, window.screen ? window.screen.height - 160 : 760))});
}

function toolResult(value) {
  if (!value) throw new Error("The host returned nothing.");
  if (value.isError) {
    const t = (value.content || []).map(c => c.text || "").join(" ").trim();
    throw new Error(t || "The tool reported an error.");
  }
  if (value.structuredContent) return value.structuredContent;
  const text = (value.content || []).map(c => c.text || "").join("");
  try { return JSON.parse(text); } catch (e) { return {text}; }
}

window.DC_HOST = {
  saveReview: async review => {
    if (hostCaps.serverTools) return toolResult(await request("tools/call", {name:"decisioncraft_save_review", arguments:{review}}));
    if (hostCaps.downloadFile) {
      const res = await request("ui/download-file", {contents:[{type:"resource", resource:{
        uri:"file:///review.json", mimeType:"application/json", text:JSON.stringify(review, null, 2)}}]});
      if (res && res.isError) throw new Error("The download was cancelled.");
      return {path:"review.json (downloaded)"};
    }
    throw new Error("This host can't save files.");
  },
  askExperts: async (note, roles, model, review) => {
    if (!hostCaps.serverTools) throw new Error("This host can't ask the experts from here.");
    const r = Object.assign({}, review, {notes:[note]});
    const out = toolResult(await request("tools/call", {name:"decisioncraft_review_notes",
      arguments:{model, review:r, roles}}));
    const back = ((out.review || {}).notes || []).find(x => x.id === note.id) || {};
    return {replies: back.replies || []};
  },
};

addEventListener("message", event => {
  const m = event.data;
  if (!m || m.jsonrpc !== "2.0") return;
  if (m.id != null && pending.has(m.id) && !m.method) {
    const p = pending.get(m.id); pending.delete(m.id);
    if (m.error) p.reject(new Error(m.error.message || "The host refused.")); else p.resolve(m.result);
    return;
  }
  if (m.method === "ui/notifications/tool-result") boot(m.params && m.params.structuredContent || toolResultSafe(m.params));
  else if (m.method === "ui/notifications/tool-cancelled") showWaiting("The tool was cancelled.");
  else if (m.method === "ui/resource-teardown" && m.id != null) post({id:m.id, result:{}});
  else if (m.method === "ping" && m.id != null) post({id:m.id, result:{}});
});
function toolResultSafe(p) { try { return toolResult(p); } catch (e) { return null; } }

/* Opened outside a host (for example from a saved file): just show the waiting note. */
if (!parent) { showWaiting("Open this view from an MCP host, or open canvas.html instead."); return; }
showWaiting("Drawing the decision map ...");
request("ui/initialize", {
  protocolVersion:"2026-01-26",
  appInfo:{name:"Decisioncraft", version:"__VERSION__"},
  appCapabilities:{availableDisplayModes:["inline", "fullscreen"]},
}).then(result => {
  hostCaps = (result && result.hostCapabilities) || {};
  notify("ui/notifications/initialized", {});
}).catch(() => notify("ui/notifications/initialized", {}));
})();
