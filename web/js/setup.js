// Setup controller: build the form, optional mic check, save config, continue.
import { ROLES, LEVELS, STYLES, TYPES } from "./config.js";
import { saveConfig } from "./storage.js";
import { $, el, toast } from "./ui.js";
import { AudioMeter } from "./voice.js";
import { icon, hydrate } from "./icons.js";

const state = { type: "behavioral", style: "Technical" };
let step = 0;

const roleSel = $("#role"), levelSel = $("#level");
ROLES.forEach(r => roleSel.append(el("option", {}, r)));
LEVELS.forEach(l => { const o = el("option", {}, l); if (l === "Mid-Level") o.selected = true; levelSel.append(o); });

function buildChoices(container, items, key, label) {
  items.forEach((it, i) => {
    const node = el("div", { class: "choice" },
      el("span", { class: "ic", html: icon(it.ic) }),
      label(it));
    if ((key === "type" && i === 0) || (key === "style" && it.id === "Technical")) node.classList.add("active");
    node.addEventListener("click", () => {
      [...container.children].forEach(c => c.classList.remove("active"));
      node.classList.add("active");
      state[key] = it.id;
    });
    container.append(node);
  });
}
buildChoices($("#types"), TYPES, "type", (t) => el("span", {}, t.label));
buildChoices($("#styles"), STYLES, "style", (s) => el("span", {}, s.id, el("small", {}, s.desc)));

const maxq = $("#maxq"), maxqVal = $("#maxqVal");
maxq.addEventListener("input", () => maxqVal.textContent = maxq.value);

const steps = [...document.querySelectorAll(".step")];
const dots = [...document.querySelectorAll("#stepDots span")];
const prevBtn = $("#prevStep");
const nextBtn = $("#nextStep");
const beginBtn = $("#begin");

function showStep(next, shouldScroll = false) {
  step = Math.max(0, Math.min(steps.length - 1, next));
  steps.forEach((node, i) => node.classList.toggle("active", i === step));
  dots.forEach((node, i) => node.classList.toggle("on", i <= step));
  $("#stepNow").textContent = step + 1;
  $("#stepSub").textContent = steps[step].dataset.sub || "";
  prevBtn.disabled = step === 0;
  nextBtn.classList.toggle("hidden", step === steps.length - 1);
  beginBtn.classList.toggle("hidden", step !== steps.length - 1);
  if (shouldScroll) {
    document.querySelector(".setup-card")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

prevBtn.addEventListener("click", () => showStep(step - 1, true));
nextBtn.addEventListener("click", () => showStep(step + 1, true));

let meter = null;
$("#micTest").addEventListener("click", async () => {
  if (meter) {
    meter.stop();
    meter = null;
    $("#micLevel").style.width = "0%";
    $("#micStatus").textContent = "Mic stopped.";
    return;
  }
  try {
    meter = new AudioMeter();
    await meter.start();
    $("#micStatus").textContent = "Speak - the bar should move.";
    const tick = () => {
      if (!meter) return;
      $("#micLevel").style.width = Math.round(meter.level() * 100) + "%";
      requestAnimationFrame(tick);
    };
    tick();
  } catch {
    $("#micStatus").textContent = "Mic blocked - you can type instead.";
    toast("Microphone unavailable.");
  }
});

$("#begin").addEventListener("click", () => {
  meter?.stop();
  saveConfig({
    role: roleSel.value,
    level: levelSel.value,
    style: state.style,
    interview_type: state.type,
    resume_text: $("#resume").value.trim(),
    max_questions: parseInt(maxq.value, 10),
    voice: $("#voice").checked,
  });
  location.href = "/interview.html";
});

hydrate();
showStep(0);
