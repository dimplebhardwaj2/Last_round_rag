// Final evaluation: score hero, radar chart, criteria, strengths/improvements.
import { loadReport, loadConfig } from "./storage.js";
import { $, el, escapeHtml } from "./ui.js";
import { icon, hydrate } from "./icons.js";

const r = loadReport();
const cfg = loadConfig();
const body = $("#reportBody");

if (cfg) $("#reportMeta").textContent = `${cfg.role} / ${cfg.level} / ${cfg.interview_type.replace("_", " ")} interview`;

if (!r || r.error) {
  body.append(el("div", { class: "card card-pad" },
    el("h3", {}, "We couldn't generate a full report"),
    el("p", { class: "muted" }, r?.error || "Try a longer interview with more detailed answers.")));
} else {
  render(r);
}
hydrate();

function ring(score) {
  const pct = Math.max(0, Math.min(1, (score || 0) / 5));
  const R = 86, C = 2 * Math.PI * R, off = C * (1 - pct);
  return `<div class="score-ring"><svg width="200" height="200">
      <circle cx="100" cy="100" r="${R}" fill="none" stroke="#eef1f6" stroke-width="14"/>
      <circle cx="100" cy="100" r="${R}" fill="none" stroke="url(#g)" stroke-width="14" stroke-linecap="round"
        stroke-dasharray="${C}" stroke-dashoffset="${C}" transform="rotate(-90 100 100)">
        <animate attributeName="stroke-dashoffset" from="${C}" to="${off}" dur="1.1s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1"/>
      </circle>
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#7047EB"/><stop offset="55%" stop-color="#EF5DB6"/><stop offset="100%" stop-color="#31D9DF"/></linearGradient></defs>
    </svg><div class="val"><div class="big">${score}<small>/5</small></div><div class="tag">overall</div></div></div>`;
}

function render(r) {
  body.append(el("div", { class: "card score-hero", html:
    ring(r.overall_score) +
    `<div class="verdict"><div class="pill">${escapeHtml(r.verdict || "Assessment")}</div>
       <h2>How that round went</h2><p>${escapeHtml(r.summary || "")}</p></div>` }));

  const grid = el("div", { class: "eval-grid" });
  const radarCard = el("div", { class: "card panel-card" },
    el("h3", { html: icon("target") + "<span>Readiness radar</span>" }),
    el("div", { class: "radar-box", html: '<canvas id="radar" width="300" height="300"></canvas>' }));
  const critCard = el("div", { class: "card panel-card" }, el("h3", { html: icon("bar-chart") + "<span>Criteria breakdown</span>" }));
  const critList = el("div", { class: "criteria" });
  (r.criteria || []).forEach(c => critList.append(el("div", { class: "crit", html:
    `<div class="crit-head"><span class="name">${escapeHtml(c.name)}</span><span class="sc">${c.score}/5</span></div>
     <div class="bar"><span style="width:${(c.score / 5) * 100}%"></span></div>
     <div class="cmt">${escapeHtml(c.comment || "")}</div>` })));
  critCard.append(critList);
  grid.append(radarCard, critCard);
  body.append(grid);

  const liItems = (arr, ic) => (arr || []).map(x => `<li>${icon(ic, { size: 18 })}<span>${escapeHtml(x)}</span></li>`).join("");
  body.append(el("div", { class: "cols-2", html:
    `<div class="card panel-card list-card good"><h3>${icon("check-circle")}<span>Strengths</span></h3><ul>${liItems(r.strengths, "check-circle")}</ul></div>
     <div class="card panel-card list-card improve"><h3>${icon("target")}<span>Improvements</span></h3><ul>${liItems(r.improvements, "arrow-right")}</ul></div>` }));

  if (r.model_answer) {
    body.append(el("div", { class: "card model-answer", html:
      `<h3>${icon("lightbulb")}<span>Model answer</span></h3><p>${escapeHtml(r.model_answer)}</p>` }));
  }

  if (r.criteria?.length) drawRadar($("#radar"), r.criteria);
}

function drawRadar(cv, items) {
  const c = cv.getContext("2d"), W = cv.width, cx = W / 2, cy = W / 2, R = 100;
  const n = items.length, ang = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  c.clearRect(0, 0, W, W);

  c.strokeStyle = "#e9edf3";
  c.fillStyle = "#94a3b8";
  c.lineWidth = 1;
  for (let r = 1; r <= 5; r++) {
    c.beginPath();
    for (let i = 0; i <= n; i++) {
      const a = ang(i % n), rr = (R * r) / 5;
      const x = cx + rr * Math.cos(a), y = cy + rr * Math.sin(a);
      i ? c.lineTo(x, y) : c.moveTo(x, y);
    }
    c.stroke();
  }

  c.font = "600 11px Inter, sans-serif";
  c.textAlign = "center";
  c.textBaseline = "middle";
  items.forEach((it, i) => {
    const a = ang(i), x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    c.beginPath();
    c.moveTo(cx, cy);
    c.lineTo(x, y);
    c.strokeStyle = "#e9edf3";
    c.stroke();
    const lx = cx + (R + 22) * Math.cos(a), ly = cy + (R + 16) * Math.sin(a);
    c.fillStyle = "#64748b";
    c.fillText((it.name || "").split(" ")[0], lx, ly);
  });

  c.beginPath();
  items.forEach((it, i) => {
    const a = ang(i), rr = (R * (it.score || 0)) / 5;
    const x = cx + rr * Math.cos(a), y = cy + rr * Math.sin(a);
    i ? c.lineTo(x, y) : c.moveTo(x, y);
  });
  c.closePath();
  const grad = c.createLinearGradient(0, 0, W, W);
  grad.addColorStop(0, "rgba(112,71,235,.30)");
  grad.addColorStop(0.55, "rgba(239,93,182,.24)");
  grad.addColorStop(1, "rgba(49,217,223,.25)");
  c.fillStyle = grad;
  c.fill();
  c.strokeStyle = "#7047EB";
  c.lineWidth = 2;
  c.stroke();
  items.forEach((it, i) => {
    const a = ang(i), rr = (R * (it.score || 0)) / 5;
    c.beginPath();
    c.arc(cx + rr * Math.cos(a), cy + rr * Math.sin(a), 3.5, 0, 7);
    c.fillStyle = "#7047EB";
    c.fill();
  });
}
