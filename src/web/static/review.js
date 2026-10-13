// Match review page (src/web/review.py): one rally at a time from the rally
// copy, the post-run labels on the bodies, the owner's verdict per point.
(() => {
  "use strict";

  const KEY = window.REVIEW_KEY;
  const BASE = `/review/${encodeURIComponent(KEY)}`;
  const $ = (id) => document.getElementById(id);
  const video = $("video"), canvas = $("overlay"), ctx = canvas.getContext("2d");
  const COLORS = { P1A: "#ffd166", P2A: "#ff8c42", P1B: "#4cc9f0", P2B: "#c39bff" };
  const FIXES = [["near_swapped", "1", "Near pair swapped"], ["far_swapped", "2", "Far pair swapped"],
                 ["sides_swapped", "3", "Squads on the wrong halves"], ["other", "4", "Labels wrong, other"]];
  const TOUCH_FLASH = 6;          // frames around a touch its caption stays up

  let M = null;                   // the match as the run read it
  let R = null;                   // the review as stored
  let cur = 0;                    // index into M.points
  let draft = null;               // the verdict being edited
  let reviewed = false;           // the open point had (or got) a verdict
  let trk = null;                 // bodies + ball of the open point
  let boxes = false, speed = 1, lastCopyFrame = -1;
  const trackCache = new Map();
  let saving = Promise.resolve();
  let noteTimer = null;

  // ------------------------------------------------------------------ helpers
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clock = (s) => (s == null ? "" :
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`);
  const point = () => M.points[cur];
  const seg = () => point().segment;
  const frameOf = (t) => Math.floor(t * M.fps + 0.01);
  const copyPos = (src) => seg().copy_first + (src - seg().first);
  const srcOf = (copyFrame) => seg().first + (copyFrame - seg().copy_first);
  const curSrc = () => srcOf(frameOf(video.currentTime));
  const other = (team) => (team === "A" ? "B" : "A");

  async function api(path, body) {
    const res = await fetch(BASE + path, body === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
    return res.json();
  }

  function blank() {
    return { status: null, labels: {}, names: {}, winner: null, not_a_point: false, touches: {}, added: [], note: "" };
  }

  // Run label -> the player the owner says it is (mirror of review.label_map).
  function labelMap() {
    const l = draft.labels, near = point().near_team;
    const trueNear = l.sides_swapped && near ? other(near) : near;
    const out = {};
    for (const label of M.players) {
      let n = label[1], squad = label[2];
      if (l.sides_swapped) squad = other(squad);
      const onNear = trueNear != null && squad === trueNear, onFar = trueNear != null && squad !== trueNear;
      if ((onNear && l.near_swapped) || (onFar && l.far_swapped)) n = n === "1" ? "2" : "1";
      out[label] = `P${n}${squad}`;
    }
    return Object.assign(out, draft.names);     // T4 -> the player the owner named
  }

  function hasCorrections(v) {
    return Object.keys(v.labels).length > 0 || Object.keys(v.names).length > 0 || v.winner != null || v.not_a_point ||
      Object.keys(v.touches).length > 0 || v.added.length > 0 || v.note.trim() !== "";
  }

  // The point's touches as the owner left them, in frame order.
  function touches() {
    const names = labelMap();
    const rows = point().touches.map((t) => {
      const fix = draft.touches[t.frame] || {};
      return { frame: t.frame, run: t, removed: !!fix.remove,
               action: fix.action ?? t.action,
               player: "player" in fix ? fix.player : (names[t.player] ?? t.player),
               fixedAction: fix.action != null, fixedPlayer: "player" in fix };
    });
    draft.added.forEach((t, i) => rows.push({ frame: t.frame, added: i, action: t.action, player: t.player }));
    return rows.sort((a, b) => a.frame - b.frame);
  }

  // ------------------------------------------------------------------ saving
  function edited(render = true) {
    draft.status = hasCorrections(draft) ? "corrected" : (reviewed ? "ok" : null);
    if (draft.status) reviewed = true;
    save();
    if (render) renderPanel();
    renderTimeline();
    draw(lastCopyFrame);
  }

  function save() {
    const number = point().point;
    const body = JSON.parse(JSON.stringify(draft));
    saving = saving.then(() => api(`/point/${number}`, body)).then(applyState).catch(fail);
  }

  function saveMatch() {
    const body = { owner_final_score: R.owner_final_score, missing_points: R.missing_points };
    saving = saving.then(() => api("/match", body)).then(applyState).catch(fail);
  }

  function applyState(state) {
    R = state;
    renderChips();
    renderScores();
  }

  function fail(err) {
    console.error(err);
    $("scores").innerHTML = `<span class="rv-off">NOT SAVED — ${esc(err.message)}</span>`;
  }

  // ------------------------------------------------------------------ header
  function renderScores() {
    const run = M.run.final_score || {}, rev = R.reviewed_score, own = R.owner_final_score || {};
    const off = own.A != null && (own.A !== rev.A || own.B !== rev.B);
    const done = Object.keys(R.verdicts).length;
    $("scores").innerHTML =
      `<span>${done} / ${M.points.length} reviewed</span>` +
      `<span>Run <b>A ${run.A ?? "?"} – B ${run.B ?? "?"}</b></span>` +
      `<span class="${off ? "rv-off" : ""}">After review <b>A ${rev.A} – B ${rev.B}</b>` +
      `${rev.undecided ? ` (+${rev.undecided} undecided)` : ""}</span>` +
      `<span>Yours A <input id="ownA" inputmode="numeric" value="${own.A ?? ""}"> – B ` +
      `<input id="ownB" inputmode="numeric" value="${own.B ?? ""}"></span>`;
    for (const id of ["ownA", "ownB"]) {
      $(id).addEventListener("change", () => {
        const a = parseInt($("ownA").value, 10), b = parseInt($("ownB").value, 10);
        R.owner_final_score = Number.isFinite(a) && Number.isFinite(b) ? { A: a, B: b } : null;
        saveMatch();
      });
    }
  }

  function renderChips() {
    const switches = new Set(M.run.switch_after || []);
    const gaps = new Set(R.missing_points.map((m) => m.after_point));
    $("chips").innerHTML = M.points.map((p, i) => {
      const v = R.verdicts[p.point];
      const cls = ["rv-chip", v ? v.status : "", v && v.run_changed ? "changed" : "",
                   i === cur ? "current" : "", switches.has(p.point) ? "switch" : "",
                   gaps.has(p.point) ? "gap" : ""].filter(Boolean).join(" ");
      const title = `Point ${p.point} · ${clock(p.start_time_s)} · winner ${p.winner ?? "?"}` +
        (v && v.run_changed ? " · the run changed since your review" : "");
      return `<button class="${cls}" data-i="${i}" title="${esc(title)}">${p.point}</button>`;
    }).join("");
  }

  // ------------------------------------------------------------------ panel
  function renderPanel() {
    const p = point(), v = R.verdicts[p.point];
    const state = draft.status === "ok" ? "✓ all right" : draft.status === "corrected" ? "● corrected" : "not reviewed";
    const effWinner = draft.winner == null ? p.winner : (draft.winner === "none" ? null : draft.winner);
    const players = (sel) => [["", "nobody"]].concat(M.players.map((x) => [x, x]))
      .concat(sel && !M.players.includes(sel) ? [[sel, `${sel} (no name)`]] : [])
      .map(([val, txt]) => `<option value="${val}"${(sel ?? "") === val ? " selected" : ""}>${txt}</option>`).join("");
    const actions = (sel) => M.actions.map((a) =>
      `<option${a === sel ? " selected" : ""}>${a}</option>`).join("");

    const rows = touches().map((t, i) => {
      const tag = t.added != null ? "added" :
        [t.run.outcome, t.run.spike_type, t.run.observed ? "" : "not seen"].filter(Boolean).join(" · ");
      const key = t.added != null ? `data-added="${t.added}"` : `data-frame="${t.frame}"`;
      return `<tr class="${t.removed ? "removed" : ""}" ${key} data-seek="${t.frame}">
        <td class="t">${i + 1}</td>
        <td><select data-f="action" class="${t.fixedAction || t.added != null ? "fixed" : ""}">${actions(t.action)}</select></td>
        <td><select data-f="player" class="${t.fixedPlayer || t.added != null ? "fixed" : ""}">${players(t.player)}</select></td>
        <td class="rv-tag">${esc(tag)}</td>
        <td><button data-act="${t.added != null ? "drop-added" : "toggle-remove"}" title="Not a touch">${t.removed ? "↺" : "✕"}</button></td>
      </tr>`;
    }).join("");

    const missing = R.missing_points.map((m, i) => (m.after_point !== p.point ? "" :
      `<div class="rv-missing" data-missing="${i}">a point, won by
         <select data-f="m-winner">${[["", "?"], ["A", "A"], ["B", "B"]].map(([val, txt]) =>
           `<option value="${val}"${(m.winner ?? "") === val ? " selected" : ""}>${txt}</option>`).join("")}</select>
         <input data-f="m-note" placeholder="what happened" value="${esc(m.note)}">
         <button data-act="drop-missing">✕</button></div>`)).join("");

    // Bodies the run gave no name (a half whose two players it could not tell apart).
    const unnamed = [...new Set(p.touches.map((t) => t.player).filter((x) => /^T\d+$/.test(x || "")))].sort();
    const naming = unnamed.map((u) => `<label>${u} is <select data-f="name" data-u="${u}" class="${draft.names[u] ? "fixed" : ""}">${
      [["", "?"]].concat(M.players.map((x) => [x, x])).map(([val, txt]) =>
        `<option value="${val}"${(draft.names[u] ?? "") === val ? " selected" : ""}>${txt}</option>`).join("")}</select></label>`).join(" ");

    $("panel").innerHTML = `
      <div class="rv-card">
        <div class="rv-head">
          <span class="n">Point ${p.point}</span>
          <span class="rv-muted">${clock(p.start_time_s)}</span>
          <span class="score">A ${p.score_before.A} – B ${p.score_before.B} → <b>A ${p.score_after.A} – B ${p.score_after.B}</b></span>
          <span class="rv-state ${draft.status || ""}">${state}</span>
        </div>
        <p class="rv-facts">Serve <b>${esc(p.serve_team ?? "?")}</b> (${esc(p.serve_player ?? "nobody")}) ·
          winner <b>${esc(p.winner ?? "undecided")}</b> (${esc(p.winner_source ?? "—")}) ·
          ends: ${esc(p.end_kind ?? "?")} · near half: <b>${esc(p.near_team ?? "?")}</b></p>
        ${p.flags.length ? `<p class="rv-facts">Flags: ${p.flags.map(esc).join(", ")}</p>` : ""}
        ${v && v.run_changed ? `<p class="rv-warn">The run reads this point differently than when you reviewed it. Look again.</p>` : ""}
        ${seg() ? "" : `<p class="rv-warn">This rally is not in the rally copy (the copy is older than the reconstruction): no picture.</p>`}
        <div class="rv-row" style="margin-top:10px">
          <button class="primary" data-act="ok">${hasCorrections(draft) ? "Done, next" : "All right, next"} (Enter)</button>
          <button data-act="undo">Undo my review (U)</button>
        </div>
      </div>
      <div class="rv-card">
        <h2>Who is who</h2>
        <div class="rv-row">${FIXES.map(([k, key, txt]) =>
          `<button data-act="fix" data-k="${k}" class="${draft.labels[k] ? "on" : ""}">${txt} (${key})</button>`).join("")}</div>
        ${naming ? `<div class="rv-row"><span class="rv-muted">The run could not tell these apart:</span> ${naming}</div>` : ""}
      </div>
      <div class="rv-card">
        <h2>The point</h2>
        <div class="rv-row">Winner (W)
          ${[["A", "A"], ["B", "B"], ["none", "nobody"]].map(([val, txt]) =>
            `<button data-act="winner" data-k="${val}" class="${(effWinner ?? "none") === val ? (draft.winner != null ? "on" : "primary") : ""}">${txt}</button>`).join("")}
          <button data-act="not-a-point" class="${draft.not_a_point ? "on" : ""}">Not a point (X)</button>
        </div>
      </div>
      <div class="rv-card">
        <h2>Touches</h2>
        <table class="rv-touches"><tbody>${rows}</tbody></table>
        <div class="rv-row" style="margin-top:8px"><button data-act="add-touch">+ a touch at this frame (T)</button></div>
      </div>
      <div class="rv-card">
        <h2>Note</h2>
        <textarea id="note" placeholder="Anything the buttons cannot say (N)">${esc(draft.note)}</textarea>
      </div>
      <div class="rv-card">
        <h2>After this point</h2>
        ${missing}
        <div class="rv-row"><button data-act="add-missing">+ a point is missing after this one (M)</button></div>
      </div>`;
    markNow(lastCopyFrame);
  }

  function renderTimeline() {
    const tl = $("timeline"), s = seg();
    tl.querySelectorAll(".rv-tick, .rv-rally").forEach((n) => n.remove());
    if (!s) return;
    const span = Math.max(1, s.last - s.first), at = (f) => `${(100 * (f - s.first)) / span}%`;
    const p = point(), rally = document.createElement("div");
    rally.className = "rv-rally";
    rally.style.left = at(p.start_frame);
    rally.style.width = `${(100 * (p.end_frame - p.start_frame)) / span}%`;
    tl.prepend(rally);
    for (const t of touches()) {
      const tick = document.createElement("div");
      tick.className = `rv-tick${t.added != null ? " added" : ""}${t.removed ? " removed" : ""}`;
      tick.style.left = at(t.frame);
      tick.style.background = t.added != null ? "" : (COLORS[t.player] || "");
      tick.title = `${t.action} · ${t.player ?? "nobody"}`;
      tl.appendChild(tick);
    }
  }

  // ------------------------------------------------------------------ video
  function sizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    return dpr;
  }

  function markNow(copyFrame) {
    if (!seg() || copyFrame < 0) return;
    const src = srcOf(copyFrame);
    let now = null;
    for (const t of touches()) if (!t.removed && t.frame <= src) now = t;
    $("panel").querySelectorAll(".rv-touches tr").forEach((tr) =>
      tr.classList.toggle("now", now != null && Number(tr.dataset.seek) === now.frame));
    const near = now && src - now.frame <= TOUCH_FLASH ? now : null;
    $("touchNow").hidden = !near;
    if (near) $("touchNow").textContent = `${near.action} · ${near.player ?? "nobody"}`;
    return near;
  }

  function draw(copyFrame) {
    const dpr = sizeCanvas();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!seg() || copyFrame < 0) return;
    const src = srcOf(copyFrame), s = seg();
    $("cursor").style.left = `${(100 * (src - s.first)) / Math.max(1, s.last - s.first)}%`;
    $("clock").textContent = `frame ${src}`;
    const near = markNow(copyFrame);
    if (!trk || src < trk.first || src - trk.first >= trk.bodies.length) return;
    const [cx, cy, cw, ch] = M.crop, sx = canvas.width / cw, sy = canvas.height / ch;
    const names = labelMap(), W = canvas.width, H = canvas.height;
    ctx.font = `700 ${13 * dpr}px -apple-system, "Segoe UI", sans-serif`;
    ctx.textBaseline = "middle";
    for (const [label, x1, y1, x2, y2, track] of trk.bodies[src - trk.first]) {
      const name = names[label ?? `T${track}`] ?? label ?? `T${track}`;
      const color = COLORS[name] || "#ffffff";
      const bx1 = (x1 - cx) * sx, by1 = (y1 - cy) * sy, bx2 = (x2 - cx) * sx, by2 = (y2 - cy) * sy;
      if (boxes) { ctx.strokeStyle = color; ctx.lineWidth = 1.5 * dpr; ctx.strokeRect(bx1, by1, bx2 - bx1, by2 - by1); }
      const below = by1 > H - 4 * dpr;
      const text = below ? `${name} ↓` : name;
      const tw = ctx.measureText(text).width + 10 * dpr, th = 19 * dpr;
      const px = Math.min(Math.max((bx1 + bx2) / 2 - tw / 2, 0), W - tw);
      const py = Math.min(Math.max(by1 - th - 3 * dpr, 0), H - th);
      ctx.fillStyle = "rgba(0,0,0,0.82)";
      ctx.fillRect(px, py, tw, th);
      ctx.fillStyle = color;
      ctx.fillText(text, px + 5 * dpr, py + th / 2 + dpr);
    }
    const ball = trk.ball[src - trk.first];
    if (near && ball) {
      ctx.strokeStyle = COLORS[near.player] || "#ffffff";
      ctx.lineWidth = 2.5 * dpr;
      ctx.beginPath();
      ctx.arc((ball[0] - cx) * sx, (ball[1] - cy) * sy, 16 * dpr, 0, 2 * Math.PI);
      ctx.stroke();
    }
  }

  function tick(copyFrame) {
    if (!M || !seg()) return;
    lastCopyFrame = copyFrame;
    if (!video.paused && (copyFrame >= copyPos(seg().last) || copyFrame < seg().copy_first)) {
      seek(seg().first);
      return;
    }
    draw(copyFrame);
  }

  function seek(src) {
    const s = seg();
    if (!s) return;
    src = Math.min(Math.max(src, s.first), s.last);
    video.currentTime = (copyPos(src) + 0.5) / M.fps;
  }

  function step(n) { video.pause(); seek(curSrc() + n); }

  function jumpTouch(dir) {
    const frames = touches().filter((t) => !t.removed).map((t) => t.frame), src = curSrc();
    const next = dir > 0 ? frames.find((f) => f > src) : frames.reverse().find((f) => f < src);
    if (next != null) { video.pause(); seek(next); }
  }

  if (video.requestVideoFrameCallback) {
    const onFrame = (_now, meta) => { tick(frameOf(meta.mediaTime)); video.requestVideoFrameCallback(onFrame); };
    video.requestVideoFrameCallback(onFrame);
  } else {
    const loop = () => { tick(frameOf(video.currentTime)); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }
  video.addEventListener("ended", () => { if (seg()) { seek(seg().first); video.play(); } });
  window.addEventListener("resize", () => draw(lastCopyFrame));

  // ------------------------------------------------------------------ points
  async function openPoint(i) {
    if (i < 0 || i >= M.points.length) return;
    flushNote();
    cur = i;
    const v = R.verdicts[point().point];
    draft = blank();
    if (v) for (const k of Object.keys(draft)) if (v[k] != null) draft[k] = JSON.parse(JSON.stringify(v[k]));
    reviewed = !!v;
    trk = null;
    lastCopyFrame = -1;
    renderChips();
    renderPanel();
    renderTimeline();
    const s = seg();
    $("videoBox").style.visibility = s ? "visible" : "hidden";
    if (!s) { video.pause(); return; }
    seek(s.first);
    video.playbackRate = speed;
    video.play().catch(() => {});
    const number = point().point;
    if (!trackCache.has(number)) {
      trackCache.set(number, api(`/tracks?first=${s.first}&last=${s.last}`));
    }
    try {
      const loaded = await trackCache.get(number);
      if (point().point === number) { trk = loaded; draw(lastCopyFrame); }
    } catch (err) { trackCache.delete(number); fail(err); }
  }

  function allRight() {
    flushNote();
    draft.status = hasCorrections(draft) ? "corrected" : "ok";
    reviewed = true;
    save();
    if (cur + 1 < M.points.length) openPoint(cur + 1); else { renderPanel(); video.pause(); }
  }

  function undo() {
    draft = blank();
    reviewed = false;
    edited();
  }

  function toggleFix(k) {
    if (draft.labels[k]) delete draft.labels[k]; else draft.labels[k] = true;
    edited();
  }

  function setWinner(w) {
    const run = point().winner ?? "none";
    draft.winner = w === run ? null : w;
    edited();
  }

  function cycleWinner() {
    const eff = draft.winner == null ? point().winner : (draft.winner === "none" ? null : draft.winner);
    setWinner(eff === "A" ? "B" : "A");
  }

  function addTouch() {
    video.pause();
    draft.added.push({ frame: curSrc(), action: "block", player: null });
    draft.added.sort((a, b) => a.frame - b.frame);
    edited();
  }

  function addMissing() {
    R.missing_points.push({ after_point: point().point, winner: null, note: "" });
    saveMatch();
    renderPanel();
  }

  function flushNote() {
    if (noteTimer == null) return;
    clearTimeout(noteTimer);
    noteTimer = null;
    edited(false);
  }

  // ------------------------------------------------------------------ events
  $("chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-i]");
    if (b) openPoint(Number(b.dataset.i));
  });

  $("timeline").addEventListener("click", (e) => {
    const s = seg();
    if (!s) return;
    const box = $("timeline").getBoundingClientRect();
    seek(Math.round(s.first + ((e.clientX - box.left) / box.width) * (s.last - s.first)));
  });

  $("panel").addEventListener("click", (e) => {
    const b = e.target.closest("[data-act]");
    if (!b) {
      const tr = e.target.closest("tr[data-seek]");
      if (tr && !e.target.closest("select")) { video.pause(); seek(Number(tr.dataset.seek)); }
      return;
    }
    const tr = b.closest("tr"), act = b.dataset.act;
    if (act === "ok") allRight();
    else if (act === "undo") undo();
    else if (act === "fix") toggleFix(b.dataset.k);
    else if (act === "winner") setWinner(b.dataset.k);
    else if (act === "not-a-point") { draft.not_a_point = !draft.not_a_point; edited(); }
    else if (act === "add-touch") addTouch();
    else if (act === "add-missing") addMissing();
    else if (act === "drop-missing") {
      R.missing_points.splice(Number(b.closest("[data-missing]").dataset.missing), 1);
      saveMatch();
      renderPanel();
    } else if (act === "drop-added") { draft.added.splice(Number(tr.dataset.added), 1); edited(); }
    else if (act === "toggle-remove") {
      const f = tr.dataset.frame;
      if (draft.touches[f] && draft.touches[f].remove) delete draft.touches[f];
      else draft.touches[f] = { remove: true };
      edited();
    }
  });

  $("panel").addEventListener("change", (e) => {
    const el = e.target, f = el.dataset.f;
    if (!f) return;
    if (f === "name") {
      if (el.value) draft.names[el.dataset.u] = el.value; else delete draft.names[el.dataset.u];
      edited();
      return;
    }
    if (f === "m-winner" || f === "m-note") {
      const m = R.missing_points[Number(el.closest("[data-missing]").dataset.missing)];
      if (f === "m-winner") m.winner = el.value || null; else m.note = el.value;
      saveMatch();
      return;
    }
    const tr = el.closest("tr"), value = f === "player" ? (el.value || null) : el.value;
    if (tr.dataset.added != null) {
      draft.added[Number(tr.dataset.added)][f] = value;
    } else {
      const frame = tr.dataset.frame, run = point().touches.find((t) => String(t.frame) === frame);
      const fix = { ...(draft.touches[frame] || {}) };
      delete fix.remove;
      // A choice equal to what the page would show anyway is no correction.
      const shown = f === "player" ? (labelMap()[run.player] ?? run.player) : run.action;
      if (value === shown) delete fix[f]; else fix[f] = value;
      if (Object.keys(fix).length) draft.touches[frame] = fix; else delete draft.touches[frame];
    }
    edited();
  });

  $("panel").addEventListener("input", (e) => {
    if (e.target.id !== "note") return;
    draft.note = e.target.value;
    clearTimeout(noteTimer);
    noteTimer = setTimeout(() => { noteTimer = null; edited(false); }, 600);
  });

  $("btnPlay").addEventListener("click", () => (video.paused ? video.play() : video.pause()));
  $("btnBack").addEventListener("click", () => step(-1));
  $("btnFwd").addEventListener("click", () => step(1));
  $("btnSpeed").addEventListener("click", toggleSpeed);
  $("btnBoxes").addEventListener("click", toggleBoxes);

  function toggleSpeed() {
    speed = speed === 1 ? 0.5 : speed === 0.5 ? 0.25 : 1;
    video.playbackRate = speed;
    $("btnSpeed").textContent = `Speed ${speed}×`;
  }

  function toggleBoxes() {
    boxes = !boxes;
    $("btnBoxes").textContent = boxes ? "Boxes on" : "Boxes off";
    draw(lastCopyFrame);
  }

  document.addEventListener("keydown", (e) => {
    if (!M || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target.matches("input, textarea, select")) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const keys = {
      Enter: allRight, " ": () => (video.paused ? video.play() : video.pause()),
      ArrowLeft: () => step(-1), ArrowRight: () => step(1),
      ArrowUp: () => jumpTouch(-1), ArrowDown: () => jumpTouch(1),
      "[": () => openPoint(cur - 1), "]": () => openPoint(cur + 1),
      1: () => toggleFix("near_swapped"), 2: () => toggleFix("far_swapped"),
      3: () => toggleFix("sides_swapped"), 4: () => toggleFix("other"),
      w: cycleWinner, x: () => { draft.not_a_point = !draft.not_a_point; edited(); },
      t: addTouch, m: addMissing, u: undo, s: toggleSpeed, b: toggleBoxes,
      n: () => $("note").focus(),
    };
    if (keys[k]) { e.preventDefault(); keys[k](); }
  });

  window.addEventListener("beforeunload", flushNote);

  // ------------------------------------------------------------------ start
  api("/data").then((d) => {
    M = d.match;
    R = d.review;
    if (M.size) $("videoBox").style.setProperty("--ar", String(M.size[0] / M.size[1]));
    renderScores();
    const first = M.points.findIndex((p) => !R.verdicts[p.point]);
    const start = () => openPoint(first < 0 ? 0 : first);
    if (video.readyState >= 1) start(); else video.addEventListener("loadedmetadata", start, { once: true });
  }).catch(fail);
})();
