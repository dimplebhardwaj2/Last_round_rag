// Setup controller: build the form, ingest resume/JD files, save config, continue.
import { ROLES, LEVELS, STYLES, TYPES } from "./config.js";
import { saveConfig } from "./storage.js";
import { $, el, toast } from "./ui.js";
import { AudioMeter } from "./voice.js";
import { icon, hydrate } from "./icons.js";

const state = { type: "behavioral", style: "Technical" };
const docs = {
  resume: { text: "", name: "" },
  jd: { text: "", name: "" },
};
let step = 0;
let pdfjsPromise = null;

const MAX_DOC_BYTES = 8 * 1024 * 1024;
const MAX_STORED_CHARS = 60000;

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

$("#resumeFile").addEventListener("change", (e) => handleDocument(e.target.files?.[0], "resume"));
$("#jdFile").addEventListener("change", (e) => handleDocument(e.target.files?.[0], "jd"));

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
  if (!docs.resume.text || !docs.jd.text) {
    updateDocSummary(true);
    toast("Upload both resume and job description first.");
    return;
  }
  meter?.stop();
  saveConfig({
    role: roleSel.value,
    level: levelSel.value,
    style: state.style,
    interview_type: state.type,
    resume_text: docs.resume.text,
    resume_file_name: docs.resume.name,
    jd_text: docs.jd.text,
    jd_file_name: docs.jd.name,
    max_questions: parseInt(maxq.value, 10),
    voice: $("#voice").checked,
  });
  location.href = "/interview.html";
});

hydrate();
showStep(0);
updateDocSummary(false);

async function handleDocument(file, kind) {
  if (!file) return;
  const card = kind === "resume" ? $("label[for='resumeFile']") : $("label[for='jdFile']");
  const status = kind === "resume" ? $("#resumeStatus") : $("#jdStatus");
  card.classList.remove("ready", "error");
  status.textContent = "Reading...";

  try {
    const text = await extractDocumentText(file);
    if (text.length < 80) throw new Error("Document text is too short to personalize the interview.");
    docs[kind] = {
      name: file.name,
      text: text.slice(0, MAX_STORED_CHARS),
    };
    card.classList.add("ready");
    status.textContent = `${file.name} - ${wordCount(text)} words`;
    updateDocSummary(false);
  } catch (err) {
    docs[kind] = { text: "", name: "" };
    card.classList.add("error");
    status.textContent = "Upload failed";
    updateDocSummary(true, err.message);
    toast(err.message || "Could not read that file.");
  }
}

async function extractDocumentText(file) {
  if (file.size > MAX_DOC_BYTES) {
    throw new Error("Use a document under 8 MB.");
  }

  const name = file.name.toLowerCase();
  if (file.type === "application/pdf" || name.endsWith(".pdf")) {
    return extractPdfText(file);
  }
  if (
    file.type.startsWith("text/")
    || name.endsWith(".txt")
    || name.endsWith(".md")
  ) {
    return cleanText(await file.text());
  }
  throw new Error("Upload a PDF, TXT, or MD file.");
}

async function extractPdfText(file) {
  const pdfjs = await loadPdfJs();
  const bytes = new Uint8Array(await file.arrayBuffer());
  const pdf = await pdfjs.getDocument({ data: bytes }).promise;
  const pages = [];
  for (let pageNo = 1; pageNo <= pdf.numPages; pageNo++) {
    const page = await pdf.getPage(pageNo);
    const content = await page.getTextContent();
    pages.push(content.items.map((item) => item.str || "").join(" "));
  }
  return cleanText(pages.join("\n"));
}

async function loadPdfJs() {
  if (!pdfjsPromise) {
    pdfjsPromise = import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs")
      .then((pdfjs) => {
        pdfjs.GlobalWorkerOptions.workerSrc =
          "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.mjs";
        return pdfjs;
      });
  }
  return pdfjsPromise;
}

function cleanText(text) {
  return (text || "")
    .replace(/\s+/g, " ")
    .replace(/\u0000/g, "")
    .trim();
}

function wordCount(text) {
  return cleanText(text).split(/\s+/).filter(Boolean).length;
}

function updateDocSummary(isError, message = "") {
  const box = $("#docSummary");
  const complete = Boolean(docs.resume.text && docs.jd.text);
  box.classList.toggle("ready", complete && !isError);
  box.classList.toggle("error", Boolean(isError));
  const text = box.querySelector("span:last-child");
  if (complete) {
    text.textContent = "Resume and job description are ready for personalized RAG retrieval.";
  } else if (isError && message) {
    text.textContent = message;
  } else {
    text.textContent = "Both documents are required for personalized RAG retrieval.";
  }
}
