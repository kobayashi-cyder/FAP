(()=>{
"use strict";

const $ = (s) => document.querySelector(s);
const messages = $("#messages");
const input = $("#input");
const send = $("#send");
const nativeOnly = $("#nativeOnly");
const apiBaseInput = $("#apiBase");
const SESSION_KEY = "fap.native.ui.session.v1";
const API_KEY = "fap.native.ui.api.v1";

let session = localStorage.getItem(SESSION_KEY);
if (!session) {
  const seed = globalThis.crypto?.getRandomValues?.(new Uint32Array(2)) || [Date.now(), Math.random()*1e9];
  session = "n_" + Array.from(seed).join("_");
  localStorage.setItem(SESSION_KEY, session);
}
$("#sessionLabel").textContent = session.slice(-18);

const storedApi = localStorage.getItem(API_KEY);
if (storedApi) apiBaseInput.value = storedApi;
apiBaseInput.addEventListener("change", () => {
  localStorage.setItem(API_KEY, apiBaseInput.value.trim());
  checkApi();
});

const native = {
  module: null,
  engine: 0,
  analyze: null,
  free: null,
  version: null
};

function state(id, text, kind="muted") {
  const el = $(id);
  el.textContent = text;
  el.className = "pill " + kind;
}

function escapeText(v) {
  return String(v ?? "");
}

function addMessage(role, text, meta = {}, artifacts = []) {
  $("#empty")?.remove();
  const article = document.createElement("article");
  article.className = "message " + role;

  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "YOU" : role === "error" ? "ERROR" : role === "system" ? "NATIVE" : "FAP";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = escapeText(text);
  article.append(who, bubble);

  const metaEntries = Object.entries(meta).filter(([,v]) => v !== undefined && v !== null && v !== "");
  if (metaEntries.length) {
    const line = document.createElement("div");
    line.className = "traceLine";
    line.textContent = metaEntries.map(([k,v]) => k + ": " + v).join(" · ");
    article.append(line);
  }

  for (const a of artifacts || []) {
    if (!a) continue;
    const box = document.createElement("div");
    box.className = "artifact";
    const raw = a.src || a.url || "";
    const src = resolveArtifact(raw);
    if (a.type === "image" && src) {
      const el = document.createElement("img");
      el.src = src;
      el.alt = a.name || "artifact";
      box.append(el);
    } else if (a.type === "audio" && src) {
      const el = document.createElement("audio");
      el.controls = true;
      el.src = src;
      box.append(el);
    } else if (a.type === "video" && src) {
      const el = document.createElement("video");
      el.controls = true;
      el.src = src;
      box.append(el);
    } else if (src) {
      const el = document.createElement("a");
      el.href = src;
      el.target = "_blank";
      el.rel = "noopener";
      el.textContent = a.name || src;
      box.append(el);
    }
    if (box.childNodes.length) article.append(box);
  }

  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function apiBase() {
  return apiBaseInput.value.trim().replace(/\/$/, "");
}

function resolveArtifact(src) {
  if (!src) return "";
  if (/^https?:\/\//i.test(src) || src.startsWith("data:") || src.startsWith("blob:")) return src;
  return src.startsWith("/") ? apiBase() + src : apiBase() + "/" + src;
}

async function jsonFetch(url, options={}) {
  const res = await fetch(url, {
    ...options,
    headers: {"Content-Type":"application/json", ...(options.headers || {})}
  });
  const raw = await res.text();
  let data = {};
  try { data = raw ? JSON.parse(raw) : {}; }
  catch { data = {error: raw || ("HTTP " + res.status)}; }
  if (!res.ok) throw new Error(data.error || data.message || ("HTTP " + res.status));
  return data;
}

function updateTrace(d) {
  const b = d?.budget || {};
  const values = {
    routes: Number(b.routes ?? 1),
    steps: Number(b.steps ?? 8),
    verify: Number(b.verify ?? 1),
    retries: Number(b.retries ?? 0)
  };
  for (const [key,val] of Object.entries(values)) {
    $("#" + key).textContent = String(val);
    const meter = $("#" + key + "Meter");
    if (meter) meter.value = val;
  }

  const rr = d?.response_redundancy || {};
  $("#responseLanes").textContent = String(rr.active_lanes ?? 6) + " / " + String(rr.capacity ?? 64);
  $("#synthesisWidth").textContent = String(rr.synthesis_width ?? 2) + " / 8";
  $("#coverageTarget").textContent = Math.round(Number(rr.coverage_target ?? 0.55) * 100) + "%";
  $("#extraPath").textContent = d?.extra_path ? "YES" : "NO";
  $("#multiIntents").textContent = String(d?.multi_intents ?? 0);
  $("#resourceId").textContent = d?.resource_id || "—";
  $("#actionId").textContent = d?.action_id || "—";
  const route = d?.route || "—";
  $("#routeBadge").textContent = "route: " + route;
  $("#routeBadge").className = "pill " + (route === "—" ? "muted" : "");
}

function profile() {
  return {
    confidence: Number($("#confidence").value),
    uncertainty: Number($("#uncertainty").value),
    disagreement: $("#disagreement").checked ? 1 : 0,
    counterexample: $("#counterexample").checked ? 1 : 0
  };
}

function bindRange(id) {
  const el = $("#" + id);
  const out = $("#" + id + "Value");
  const sync = () => out.textContent = Number(el.value).toFixed(2);
  el.addEventListener("input", sync);
  sync();
}
bindRange("confidence");
bindRange("uncertainty");

async function initNative() {
  if (typeof globalThis.createFapNativeModule !== "function") {
    state("#nativeState", "WASM NOT BUILT", "warn");
    $("#wasmLabel").textContent = "build_wasm.sh required";
    return false;
  }
  try {
    state("#nativeState", "WASM STARTING", "warn");
    const mod = await globalThis.createFapNativeModule({
      locateFile: (name) => "./" + name
    });
    native.module = mod;
    const create = mod.cwrap("fap_native_engine_create", "number", ["string"]);
    const destroy = mod.cwrap("fap_native_engine_destroy", null, ["number"]);
    const analyze = mod.cwrap(
      "fap_native_engine_analyze_json",
      "number",
      ["number","string","number","number","number","number"]
    );
    const free = mod.cwrap("fap_native_string_free", null, ["number"]);
    const version = mod.cwrap("fap_native_version", "string", []);

    native.engine = create("/");
    native.analyze = analyze;
    native.free = free;
    native.version = version;
    native.destroy = destroy;

    const v = version();
    $("#version").textContent = "v" + v;
    $("#wasmLabel").textContent = "loaded";
    state("#nativeState", "NATIVE READY", "ready");
    return true;
  } catch (err) {
    console.error(err);
    state("#nativeState", "WASM ERROR", "bad");
    $("#wasmLabel").textContent = err.message || String(err);
    return false;
  }
}

function nativeAnalyze(text) {
  if (!native.engine || !native.analyze || !native.module) return null;
  const p = profile();
  const ptr = native.analyze(
    native.engine,
    text,
    p.uncertainty,
    p.disagreement,
    p.counterexample,
    p.confidence
  );
  if (!ptr) return null;
  try {
    const raw = native.module.UTF8ToString(ptr);
    return JSON.parse(raw);
  } finally {
    native.free(ptr);
  }
}

async function checkApi() {
  try {
    const s = await jsonFetch(apiBase() + "/api/v1/status", {method:"GET"});
    state("#apiState", String(s.state || "READY").toUpperCase(), s.state === "degraded" ? "warn" : "ready");
    return true;
  } catch {
    state("#apiState", "API OFFLINE", "muted");
    return false;
  }
}

async function submit(text) {
  text = String(text || "").trim();
  if (!text) return;
  addMessage("user", text);
  input.value = "";
  resize();
  send.disabled = true;

  let trace = null;
  try {
    trace = nativeAnalyze(text);
    if (trace) updateTrace(trace);
  } catch (err) {
    addMessage("error", "C++ネイティブ解析に失敗しました。", {error: err.message});
  }

  if (nativeOnly.checked) {
    if (trace) {
      addMessage("system", "Native analysis completed.", {
        route: trace.route || "—",
        extra_path: trace.extra_path ? "yes" : "no",
        intents: trace.multi_intents ?? 0,
        response_lanes: trace.response_redundancy?.active_lanes ?? 0,
        synthesis: trace.response_redundancy?.synthesis_width ?? 0
      });
    } else {
      addMessage("system", "WASMが未ロードのためNative only処理を実行できません。");
    }
    send.disabled = false;
    input.focus();
    return;
  }

  try {
    const d = await jsonFetch(apiBase() + "/api/v1/chat", {
      method:"POST",
      body: JSON.stringify({
        text,
        session,
        client: {
          name:"FAP_Native_UI",
          protocol:"1.0",
          native_version: native.version ? native.version() : null,
          native_trace: trace
        }
      })
    });
    addMessage("fap", d.reply || "", {
      ability: d.ability,
      route: Array.isArray(d.route) ? d.route.join(" → ") : d.route,
      confidence: typeof d.confidence === "number" ? d.confidence.toFixed(2) : undefined,
      response_lanes: d.response_redundancy?.active_lanes,
      synthesis: d.response_redundancy?.synthesis_width
    }, d.artifacts || []);
    state("#apiState", String(d.status?.state || "READY").toUpperCase(), d.status?.state === "degraded" ? "warn" : "ready");
  } catch (err) {
    state("#apiState", "API OFFLINE", "muted");
    const fallback = trace
      ? "会話APIへ接続できません。C++ネイティブ解析は完了しています。"
      : "会話APIとC++ WASMの両方が利用できません。";
    addMessage("system", fallback, {
      api: apiBase(),
      route: trace?.route || "—",
      error: err.message
    });
  } finally {
    send.disabled = false;
    input.focus();
  }
}

function resize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 220) + "px";
}

$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  submit(input.value);
});
input.addEventListener("input", resize);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submit(input.value);
  }
});
$("#clear").addEventListener("click", () => {
  messages.innerHTML = '<div id="empty" class="emptyState"><strong>Cleared</strong><span>表示のみ消去しました。FAP側の状態は変更していません。</span></div>';
});
$("#reconnect").addEventListener("click", checkApi);

window.addEventListener("beforeunload", () => {
  if (native.engine && native.destroy) native.destroy(native.engine);
});

Promise.allSettled([initNative(), checkApi()]).then(() => input.focus());
})();