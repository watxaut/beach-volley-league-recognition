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
  const TOUCH_HOLD_S = 1.0;       // a touch stays marked on the picture this long
  const TOUCH_LEAD = 2;           // ... and shows this many frames before its contact
  const BALL_TRAIL = 10;          // frames of ball path drawn behind the ball

  let M = null;                   // the match as the run read it
  let R = null;                   // the review as stored
  let cur = 0;                    // index into M.points
  let draft = null;               // the verdict being edited
  let reviewed = false;           // the open point had (or got) a verdict
  let gapAt = null;               // index into M.gaps while the dead time is watched
  let gvid = null;                // the dead-time copy's <video>, made on first use
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
  const gaps = () => M.gaps || [];
  const gap = () => (gapAt == null ? null : gaps()[gapAt]);
  // What is playing: a point's stretch of the rally copy, or a gap's stretch
  // of the dead-time copy (one frame kept in `step`).
  const seg = () => {
    const g = gap();
    if (!g) return point().segment;
    const c = g.segment;
    return c && { first: c.first, last: c.first + (c.n - 1) * c.step, copy_first: c.copy_first, step: c.step };
  };
  const vid = () => (gapAt == null ? video : gvid);
  const frameOf = (t) => Math.floor(t * M.fps + 0.01);
  const copyPos = (src) => seg().copy_first + Math.floor((src - seg().first) / (seg().step || 1));
  const srcOf = (copyFrame) => seg().first + (copyFrame - seg().copy_first) * (seg().step || 1);
  const curSrc = () => srcOf(frameOf(vid().currentTime));
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
    redraw();
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
    renderWarnings();
  }

  // What the rules of the game say does not add up (who serves, ends every 7).
  function renderWarnings() {
    let box = $("warnings");
    if (!box) {
      box = document.createElement("div");
      box.id = "warnings";
      box.className = "rv-warnings";
      $("chips").after(box);
    }
    box.innerHTML = (R.warnings || []).map((w) => `<p>⚠ ${esc(w)}</p>`).join("");
  }

  function fail(err) {
    console.error(err);
    $("scores").innerHTML = `<span class="rv-off">ERROR — ${esc(err.message)} (reload the page)</span>`;
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

  function gapChip(g, i) {
    if (!g || !g.segment) return "";
    const missing = R.missing_points.filter((m) => m.after_point === g.after_point).length;
    const seen = (R.gaps || {})[g.after_point];
    const state = missing ? "missing" : seen === "tail" ? "tail" : seen === "checked" ? "ok" : g.flagged ? "flagged" : "";
    const title = `Dead time ${g.after_point ? `after point ${g.after_point}` : "before the first point"} · ` +
      `${Math.round(g.seconds)} s` + (g.why.length ? ` · ${g.why.join(", ")}` : "") +
      (missing ? ` · ${missing} point(s) missing` : "") + (seen === "tail" ? " · the rest of the point before it" : "");
    return `<button class="rv-gap ${state} ${i === gapAt ? "current" : ""}" data-g="${i}" title="${esc(title)}">` +
      `${missing ? "+" : "·"}</button>`;
  }

  function renderChips() {
    const switches = new Set(M.run.switch_after || []);
    const gapAfter = new Map(gaps().map((g, i) => [g.after_point, i]));
    const chipOf = (n) => (gapAfter.has(n) ? gapChip(gaps()[gapAfter.get(n)], gapAfter.get(n)) : "");
    $("chips").innerHTML = chipOf(0) + M.points.map((p, i) => {
      const v = R.verdicts[p.point];
      const cls = ["rv-chip", v ? v.status : "", v && v.run_changed ? "changed" : "",
                   i === cur && gapAt == null ? "current" : ""].filter(Boolean).join(" ");
      const title = `Point ${p.point} · ${clock(p.start_time_s)} · winner ${p.winner ?? "?"}` +
        (v && v.run_changed ? " · the run changed since your review" : "");
      return `<button class="${cls}" data-i="${i}" title="${esc(title)}">${p.point}</button>` +
        chipOf(p.point) + (switches.has(p.point) ? `<span class="rv-switch" title="Side switch"></span>` : "");
    }).join("");
  }

  // ------------------------------------------------------------------ panel
  const winnerOptions = (sel) => [["", "?"], ["A", "A"], ["B", "B"]].map(([val, txt]) =>
    `<option value="${val}"${(sel ?? "") === val ? " selected" : ""}>${txt}</option>`).join("");

  const missingRows = (afterPoint) => R.missing_points.map((m, i) => (m.after_point !== afterPoint ? "" :
    `<div class="rv-missing" data-missing="${i}">a point${m.at_frame != null ? ` (frame ${m.at_frame})` : ""}, won by
       <select data-f="m-winner">${winnerOptions(m.winner)}</select> served by
       <select data-f="m-serve">${winnerOptions(m.serve_team)}</select>
       <input data-f="m-note" placeholder="what happened" value="${esc(m.note)}">
       <button data-act="drop-missing">✕</button></div>`)).join("");

  function renderGapPanel() {
    const g = gap(), seen = (R.gaps || {})[g.after_point], clear = seen === "checked" || seen === "tail";
    const found = R.missing_points.some((m) => m.after_point === g.after_point);
    const where = !g.after_point ? "Before point 1" : g.before_point == null ? `After point ${g.after_point}`
      : `Between point ${g.after_point} and ${g.before_point}`;
    $("panel").innerHTML = `
      <div class="rv-card">
        <div class="rv-head">
          <span class="n">Dead time</span><span class="rv-muted">${where}</span>
          <span class="rv-state ${clear ? "ok" : ""}">${seen === "tail" ? `✓ the rest of point ${g.after_point}` : clear ? "✓ checked" : "not checked"}</span>
        </div>
        <p class="rv-facts"><b>${Math.round(g.seconds)} s</b>, shown ${g.segment.step}× faster ·
          the ball was played <b>${g.contacts ?? "?"}</b> times</p>
        ${g.why.length ? `<p class="rv-warn">Worth a look: ${g.why.map(esc).join("; ")}.</p>` : ""}
        <p class="rv-facts">Is there a rally here that should be a point (a serve, play, the ball down)?</p>
        <div class="rv-row" style="margin-top:10px">
          <button class="primary" data-act="ok">${found ? "Done, next" : "Nothing here, next"} (Enter)</button>
          <button data-act="add-missing">A point is missing here (M)</button>
          ${g.after_point ? `<button data-act="gap-tail">It is the rest of point ${g.after_point} (R)</button>` : ""}
        </div>
        ${missingRows(g.after_point)}
        <p class="rv-facts">A NEW rally starts with a serve. Play that goes on from the point before (the picture of that
          point stopped too early) is the same point: press R, do not add a point. M and R keep the frame on the picture.</p>
      </div>`;
    redraw();
  }

  function renderPanel() {
    if (gapAt != null) { renderGapPanel(); return; }
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

    const missing = missingRows(p.point);
    const after = gaps().findIndex((g) => g.after_point === p.point);
    const g = after < 0 ? null : gaps()[after];
    const gapLine = !g ? "" : `<p class="rv-facts">Dead time until the next point: <b>${Math.round(g.seconds)} s</b>` +
      (g.contacts != null ? `, the ball played ${g.contacts} times` : "") +
      ((R.gaps || {})[g.after_point] === "tail" ? " · ✓ THIS point goes on there (the run cut it short)"
        : (R.gaps || {})[g.after_point] === "checked" ? " · ✓ checked" : "") +
      (g.segment ? ` <button data-act="open-gap" data-g="${after}">Watch it (G)</button>`
                 : ` · no picture (run <code>make review-gaps</code>)`) + `</p>`;

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
        ${gapLine}
        ${missing}
        <div class="rv-row"><button data-act="add-missing">+ a point is missing after this one (M)</button></div>
      </div>`;
    redraw();
  }

  function renderTimeline() {
    const tl = $("timeline"), s = seg();
    tl.querySelectorAll(".rv-tick, .rv-rally").forEach((n) => n.remove());
    if (!s) return;
    const span = Math.max(1, s.last - s.first), at = (f) => `${(100 * (f - s.first)) / span}%`;
    if (gapAt != null) return;
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

  // The touch the rally is at: the last one played (a touch shows from
  // TOUCH_LEAD frames before its contact), and how many frames ago it was.
  function touchAt(src) {
    let now = null, n = 0, i = 0;
    for (const t of touches()) {
      if (t.removed) continue;
      i += 1;
      if (t.frame <= src + TOUCH_LEAD) { now = t; n = i; }
    }
    return now ? { touch: now, n, age: src - now.frame } : null;
  }

  function markNow(src) {
    const at = touchAt(src), hold = Math.round(M.fps * TOUCH_HOLD_S);
    $("panel").querySelectorAll(".rv-touches tr").forEach((tr) =>
      tr.classList.toggle("now", at != null && Number(tr.dataset.seek) === at.touch.frame));
    const bar = $("touchNow");
    bar.hidden = !at;
    if (at) {
      const who = at.touch.player ?? "nobody";
      bar.innerHTML = `<span class="n">${at.n}</span> <b>${esc(at.touch.action)}</b> · ` +
        `<span style="color:${COLORS[who] || "#fff"}">${esc(who)}</span>`;
      bar.classList.toggle("fresh", at.age <= hold);
    }
    return at && at.age <= hold ? { ...at, hold } : null;
  }

  function plate(text, cx0, top, color, dpr, size = 13) {
    const W = canvas.width, H = canvas.height;
    ctx.font = `700 ${size * dpr}px -apple-system, "Segoe UI", sans-serif`;
    const tw = ctx.measureText(text).width + 10 * dpr, th = (size + 6) * dpr;
    const px = Math.min(Math.max(cx0 - tw / 2, 0), W - tw), py = Math.min(Math.max(top - th, 0), H - th);
    ctx.fillStyle = "rgba(0,0,0,0.82)";
    ctx.fillRect(px, py, tw, th);
    ctx.fillStyle = color;
    ctx.fillText(text, px + 5 * dpr, py + th / 2 + dpr);
    return py;
  }

  function draw(copyFrame) {
    const dpr = sizeCanvas();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!M || !draft || !seg() || copyFrame < 0) return;
    const src = srcOf(copyFrame), s = seg();
    $("cursor").style.left = `${(100 * (src - s.first)) / Math.max(1, s.last - s.first)}%`;
    $("clock").textContent = `frame ${src}`;
    if (gapAt != null) { $("touchNow").hidden = true; return; }
    const hit = markNow(src);
    if (!trk || src < trk.first || src - trk.first >= trk.bodies.length) return;
    const [cx, cy, cw, ch] = M.crop, sx = canvas.width / cw, sy = canvas.height / ch;
    const names = labelMap(), H = canvas.height, k = src - trk.first;
    const X = (x) => (x - cx) * sx, Y = (y) => (y - cy) * sy;
    ctx.textBaseline = "middle";

    // The ball: where it is, and where it came from.
    for (let back = BALL_TRAIL; back >= 1; back--) {
      const b = trk.ball[k - back];
      if (!b) continue;
      ctx.fillStyle = `rgba(255,255,255,${0.55 * (1 - back / (BALL_TRAIL + 1))})`;
      ctx.beginPath(); ctx.arc(X(b[0]), Y(b[1]), 2.5 * dpr, 0, 2 * Math.PI); ctx.fill();
    }
    const ball = trk.ball[k];
    if (ball) {
      ctx.lineWidth = 2 * dpr; ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.beginPath(); ctx.arc(X(ball[0]), Y(ball[1]), 9 * dpr, 0, 2 * Math.PI); ctx.stroke();
    }

    let toucher = null;
    for (const [label, x1, y1, x2, y2, track] of trk.bodies[k]) {
      const name = names[label ?? `T${track}`] ?? label ?? `T${track}`;
      const color = COLORS[name] || "#ffffff";
      const bx1 = X(x1), by1 = Y(y1), bx2 = X(x2), by2 = Y(y2);
      const isToucher = hit != null && hit.touch.player === name;
      if (boxes || isToucher) {
        const w = isToucher ? 4 : 2.5;
        ctx.lineWidth = (w + 2) * dpr; ctx.strokeStyle = "rgba(0,0,0,0.6)"; ctx.strokeRect(bx1, by1, bx2 - bx1, by2 - by1);
        ctx.lineWidth = w * dpr; ctx.strokeStyle = color; ctx.strokeRect(bx1, by1, bx2 - bx1, by2 - by1);
      }
      const top = plate(by1 > H - 4 * dpr ? `${name} ↓` : name, (bx1 + bx2) / 2, by1 - 3 * dpr, color, dpr);
      if (isToucher) toucher = { x: (bx1 + bx2) / 2, top, color };
    }

    // The touch itself: the action over the player who made it (over the
    // ball when nobody is credited or the player is out of the picture).
    if (hit) {
      const word = hit.touch.action.toUpperCase() + (hit.touch.player ? "" : " · nobody");
      const color = COLORS[hit.touch.player] || "#ffffff";
      if (toucher) plate(word, toucher.x, toucher.top - 3 * dpr, color, dpr, 17);
      else if (ball) plate(word, X(ball[0]), Y(ball[1]) - 16 * dpr, color, dpr, 17);
      else plate(word, canvas.width / 2, 30 * dpr, color, dpr, 17);
      if (ball) {
        ctx.lineWidth = 3 * dpr; ctx.strokeStyle = color;
        ctx.beginPath(); ctx.arc(X(ball[0]), Y(ball[1]), 15 * dpr, 0, 2 * Math.PI); ctx.stroke();
      }
    }
  }

  function tick(copyFrame) {
    if (!M || !seg()) return;
    lastCopyFrame = copyFrame;
    if (!vid().paused && (copyFrame >= copyPos(seg().last) || copyFrame < seg().copy_first)) {
      seek(seg().first);
      return;
    }
    draw(copyFrame);
  }

  function seek(src) {
    const s = seg();
    if (!s) return;
    src = Math.min(Math.max(src, s.first), s.last);
    vid().currentTime = (copyPos(src) + 0.5) / M.fps;
  }

  function step(n) { vid().pause(); seek(curSrc() + n * (seg().step || 1)); }

  function jumpTouch(dir) {
    const frames = touches().filter((t) => !t.removed).map((t) => t.frame), src = curSrc();
    const next = dir > 0 ? frames.find((f) => f > src) : frames.reverse().find((f) => f < src);
    if (next != null) { video.pause(); seek(next); }
  }

  // One loop for the whole page: every screen refresh, show the frame the
  // video is on. The exact frame comes from the video's own frame callback
  // where the browser has one; the clock is the fallback. A failure in one
  // frame is shown and never stops the loop.
  let exact = -1, exactAt = 0, shown = -1, dirty = false;
  if (video.requestVideoFrameCallback) {
    const onFrame = (now, meta) => {
      video.requestVideoFrameCallback(onFrame);
      if (!M) return;
      exact = frameOf(meta.mediaTime);
      exactAt = now;
    };
    video.requestVideoFrameCallback(onFrame);
  }
  const loop = (now) => {
    requestAnimationFrame(loop);
    if (!M || !draft) return;
    const byClock = frameOf(vid().currentTime);
    const frame = gapAt == null && now - exactAt < 150 && Math.abs(exact - byClock) <= 2 ? exact : byClock;
    if (frame === shown && !dirty) return;
    shown = frame;
    dirty = false;
    try { tick(frame); } catch (err) { fail(err); }
  };
  requestAnimationFrame(loop);
  const redraw = () => { dirty = true; };
  const replay = () => { if (seg()) { seek(seg().first); vid().play(); } };
  video.addEventListener("ended", replay);
  window.addEventListener("resize", redraw);
  window.addEventListener("error", (e) => fail(e.error || new Error(e.message)));

  // ------------------------------------------------------------------ points
  function showVideo(which, size) {
    video.hidden = which !== video;
    if (gvid) gvid.hidden = which !== gvid;
    if (size) $("videoBox").style.setProperty("--ar", String(size[0] / size[1]));
  }

  function openGap(i) {
    const g = gaps()[i];
    if (!g || !g.segment) return;
    flushNote();
    if (!gvid) {
      gvid = document.createElement("video");
      gvid.muted = true; gvid.playsInline = true; gvid.preload = "auto";
      gvid.src = `${BASE}/gaps-video`;
      gvid.addEventListener("ended", replay);
      gvid.addEventListener("loadedmetadata", () => {
        if (gapAt != null) { showVideo(gvid, [gvid.videoWidth, gvid.videoHeight]); seek(seg().first); }
      });
      $("videoBox").prepend(gvid);
    }
    video.pause();
    gapAt = i;
    trk = null;
    lastCopyFrame = -1;
    $("videoBox").style.visibility = "visible";
    showVideo(gvid, gvid.videoWidth ? [gvid.videoWidth, gvid.videoHeight] : null);
    renderChips();
    renderPanel();
    renderTimeline();
    redraw();
    if (gvid.readyState >= 1) seek(seg().first);
    gvid.playbackRate = speed;
    gvid.play().catch(() => {});
  }

  function gapDone(tail = false) {
    const g = gap();
    if (tail && !g.after_point) return;
    const body = tail ? { checked: true, tail_frame: curSrc() } : { checked: true };
    saving = saving.then(() => api(`/gap/${g.after_point}`, body)).then(applyState).catch(fail);
    const next = M.points.findIndex((p) => p.point === g.before_point);
    if (next >= 0) openPoint(next); else { gvid.pause(); R.gaps = { ...(R.gaps || {}), [g.after_point]: tail ? "tail" : "checked" }; renderPanel(); }
  }

  async function openPoint(i) {
    if (i < 0 || i >= M.points.length) return;
    flushNote();
    if (gvid) gvid.pause();
    gapAt = null;
    showVideo(video, M.size);
    cur = i;
    const v = R.verdicts[point().point];
    draft = blank();
    if (v) for (const k of Object.keys(draft)) if (v[k] != null) draft[k] = JSON.parse(JSON.stringify(v[k]));
    reviewed = !!v;
    trk = null;
    lastCopyFrame = -1;
    redraw();
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
      if (point().point === number) { trk = loaded; redraw(); }
    } catch (err) { trackCache.delete(number); fail(err); }
  }

  function allRight() {
    if (gapAt != null) { gapDone(); return; }
    flushNote();
    draft.status = hasCorrections(draft) ? "corrected" : "ok";
    reviewed = true;
    save();
    // The dead time after this point comes next when it is worth a look and
    // nobody looked yet; any other gap is one tap away (its dot, or G).
    const after = gaps().findIndex((g) => g.after_point === point().point);
    const g = after < 0 ? null : gaps()[after];
    if (g && g.segment && g.flagged && !(R.gaps || {})[g.after_point]) openGap(after);
    else if (cur + 1 < M.points.length) openPoint(cur + 1);
    else { renderPanel(); video.pause(); }
  }

  function watchGap() {
    const after = gaps().findIndex((g) => g.after_point === point().point);
    if (gapAt == null && after >= 0) openGap(after);
  }

  function leaveGap(dir) {
    const g = gap(), n = dir < 0 ? g.after_point : g.before_point;
    const i = M.points.findIndex((p) => p.point === n);
    if (i >= 0) openPoint(i);
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
    if (gapAt != null) {
      vid().pause();
      R.missing_points.push({ after_point: gap().after_point, at_frame: curSrc(), winner: null, note: "" });
    } else {
      R.missing_points.push({ after_point: point().point, winner: null, note: "" });
    }
    saveMatch();
    renderChips();
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
    const g = e.target.closest("[data-g]"), b = e.target.closest("[data-i]");
    if (g) openGap(Number(g.dataset.g));
    else if (b) openPoint(Number(b.dataset.i));
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
    else if (act === "open-gap") openGap(Number(b.dataset.g));
    else if (act === "gap-tail") gapDone(true);
    else if (act === "drop-missing") {
      R.missing_points.splice(Number(b.closest("[data-missing]").dataset.missing), 1);
      saveMatch();
      renderChips();
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
    if (f === "m-winner" || f === "m-note" || f === "m-serve") {
      const m = R.missing_points[Number(el.closest("[data-missing]").dataset.missing)];
      if (f === "m-winner") m.winner = el.value || null;
      else if (f === "m-serve") m.serve_team = el.value || null;
      else m.note = el.value;
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

  const playPause = () => (vid().paused ? vid().play() : vid().pause());
  $("btnPlay").addEventListener("click", playPause);
  $("btnBack").addEventListener("click", () => step(-1));
  $("btnFwd").addEventListener("click", () => step(1));
  $("btnSpeed").addEventListener("click", toggleSpeed);
  $("btnBoxes").addEventListener("click", toggleBoxes);

  function toggleSpeed() {
    speed = speed === 1 ? 0.5 : speed === 0.5 ? 0.25 : 1;
    vid().playbackRate = speed;
    $("btnSpeed").textContent = `Speed ${speed}×`;
  }

  function toggleBoxes() {
    boxes = !boxes;
    $("btnBoxes").textContent = boxes ? "Boxes on" : "Boxes off";
    $("btnBoxes").classList.toggle("on", boxes);
    redraw();
  }

  // A clicked button keeps the keyboard focus, and the browser then presses it
  // again on the next Space / Enter: the key meant for the video would undo
  // the click. Buttons here never keep the focus.
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) b.blur();
  });

  document.addEventListener("keydown", (e) => {
    if (!M || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target.matches("input, textarea, select")) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const always = {
      Enter: allRight, " ": playPause, ArrowLeft: () => step(-1), ArrowRight: () => step(1),
      m: addMissing, s: toggleSpeed,
    };
    const keys = gapAt != null ? { ...always, "[": () => leaveGap(-1), "]": () => leaveGap(1), r: () => gapDone(true) } : {
      ...always,
      ArrowUp: () => jumpTouch(-1), ArrowDown: () => jumpTouch(1),
      "[": () => openPoint(cur - 1), "]": () => openPoint(cur + 1),
      1: () => toggleFix("near_swapped"), 2: () => toggleFix("far_swapped"),
      3: () => toggleFix("sides_swapped"), 4: () => toggleFix("other"),
      w: cycleWinner, x: () => { draft.not_a_point = !draft.not_a_point; edited(); },
      t: addTouch, u: undo, b: toggleBoxes, g: watchGap,
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
    renderWarnings();
    const first = M.points.findIndex((p) => !R.verdicts[p.point]);
    const start = () => openPoint(first < 0 ? 0 : first);
    if (video.readyState >= 1) start(); else video.addEventListener("loadedmetadata", start, { once: true });
  }).catch(fail);
})();
