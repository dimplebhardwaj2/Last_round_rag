// Live interview controller: Meet-style stage, voice loop, transcript, progress.
import { InterviewClient } from "./interviewClient.js";
import { loadConfig, saveReport } from "./storage.js";
import { ASSESS_FOCUS } from "./config.js";
import { $, el, escapeHtml, toast } from "./ui.js";
import { speak, stopSpeaking, createRecognizer, AudioMeter } from "./voice.js";
import { icon, hydrate } from "./icons.js";
import { createAvatar } from "./live2d.js";
import { fetchTTSUrl, audioDuration, estimateSeconds } from "./tts.js";

const cfg = loadConfig();
if (!cfg) location.href = "/setup.html";

let live2d = null;        // Live2D avatar instance (null -> orb fallback)
let ttsOk = true;         // backend neural TTS available
let turnTimer = null;     // fires "your turn" when the spoken question ends
let currentAudio = null;  // currently-playing question audio
let audioCtx = null;      // unlocked by the start-gate gesture, shared with lip-sync

const avatarWrap = $("#avatarWrap"), avatar = $("#avatar"), statusText = $("#statusText");
const qOverlay = $("#qOverlay"), qText = $("#qText"), transcript = $("#transcript");
const answerInput = $("#answerInput"), sendBtn = $("#sendBtn"), micBtn = $("#micBtn");
const spkBtn = $("#spkBtn"), endBtn = $("#endBtn"), camBtn = $("#camBtn");
const waveCanvas = $("#waveCanvas");

const total = cfg.max_questions || 5;
let ready = false, answered = 0, recording = false, ended = false;
let voiceOn = cfg.voice !== false, meter = null, startTs = null;
let connectionFailed = false;

$("#roleBadge").textContent = `${cfg.role} / ${cfg.level} / ${cfg.interview_type.replace("_", " ")}`;
$("#roleSub").textContent = `${cfg.style} interviewer`;
$("#progTotal").textContent = total;
const focusList = $("#criteriaLive");
ASSESS_FOCUS.forEach(f => focusList.append(el("div", { class: "cl-item" },
  el("span", { class: "cl-ic", html: icon(f.ic, { size: 16 }) }),
  el("span", {}, f.label),
  el("span", { class: "cl-state" }, "Assessing..."))));

function setAvatar(mode) {
  avatarWrap.className = "avatar-wrap" + (mode ? " " + mode : "");
  document.body.dataset.mode = mode || "ready";
}
function setStatus(t) { statusText.textContent = t; }
function setProgress() {
  $("#progNum").textContent = answered;
  $("#progPct").textContent = Math.round((answered / total) * 100) + "%";
  $("#progBarFill").style.width = (answered / total) * 100 + "%";
}
function enableInput(on) {
  sendBtn.disabled = !on;
  micBtn.disabled = !on;
  micBtn.style.opacity = on ? "1" : ".5";
  document.body.classList.toggle("input-ready", on);
}

function bubble(kind, who, text) {
  const av = kind === "ai" ? icon("user", { size: 15 }) : "You";
  const m = el("div", { class: `msg ${kind}` },
    el("span", { class: "av", html: kind === "me" ? "" : av }),
    el("div", { class: "body" },
      el("div", { class: "who" }, who),
      el("div", { class: "text", html: escapeHtml(text) })));
  if (kind === "me") m.querySelector(".av").textContent = "You";
  transcript.append(m);
  transcript.scrollTop = transcript.scrollHeight;
}

const client = new InterviewClient({
  onOpen() {
    setAvatar("thinking");
    setStatus("Preparing your first question...");
  },
  onQuestion(text) {
    bubble("ai", "Interviewer", text);
    qOverlay.style.display = "block";
    qText.textContent = text;
    deliverQuestion(text);
  },
  onReport(report) {
    ended = true;
    stopAllSpeech();
    stopRecording();
    saveReport(report || { error: "No report produced." });
    setAvatar("");
    setStatus("Evaluation ready - redirecting...");
    setTimeout(() => location.href = "/report.html", 700);
  },
  onError(msg) {
    connectionFailed = true;
    bubble("sys", "System", msg);
    setAvatar("");
    setStatus("Error");
    ready = false;
    enableInput(false);
  },
  onClose() {
    if (!ended && !connectionFailed) setStatus("Disconnected.");
  },
});

// Speak the question: neural TTS audio drives Live2D lip-sync (RMS analyser),
// with graceful fallbacks to browser speech.
async function deliverQuestion(text) {
  setAvatar("speaking");
  setStatus("Speaking...");
  enableInput(false);

  if (voiceOn && ttsOk) {
    try {
      const url = await fetchTTSUrl(text);
      if (ended) return;
      const dur = (await audioDuration(url)) || estimateSeconds(text);
      const audio = new Audio(url);
      currentAudio = audio;
      audio.addEventListener("ended", onSpeechEnd);
      if (live2d) live2d.attach(audio, audioCtx);   // analyse this audio -> move the mouth
      await audio.play().catch(() => {});
      clearTimeout(turnTimer);
      turnTimer = setTimeout(onSpeechEnd, dur * 1000 + 1500);   // backup if 'ended' misses
      return;
    } catch {
      ttsOk = false;                        // backend TTS unavailable -> use browser voice
    }
  }
  if (voiceOn && "speechSynthesis" in window) speak(text, { onEnd: yourTurn });
  else yourTurn();
}

function onSpeechEnd() {
  if (ready || ended) return;               // already handed control over
  clearTimeout(turnTimer);
  live2d?.stop();
  currentAudio = null;
  yourTurn();
}

function stopAllSpeech() {
  clearTimeout(turnTimer);
  stopSpeaking();
  live2d?.stop();
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
}

function yourTurn() {
  if (ended) return;
  setAvatar("");
  setStatus("Your turn - speak or type your answer");
  ready = true;
  enableInput(true);
  answerInput.focus();
}

function sendAnswer() {
  if (!ready || ended) return;
  const text = answerInput.value.trim();
  if (!text) {
    toast("Say or type something first.");
    return;
  }
  bubble("me", "You", text);
  client.answer(text);
  answerInput.value = "";
  answered++;
  setProgress();
  ready = false;
  enableInput(false);
  setAvatar("thinking");
  setStatus("Analyzing your answer...");
}

function endInterview() {
  if (ended) return;
  stopAllSpeech();
  stopRecording();
  client.end();
  ready = false;
  enableInput(false);
  setAvatar("thinking");
  setStatus("Wrapping up and scoring...");
}

const recognizer = createRecognizer({
  onInterim(t) {
    answerInput.value = t;
  },
  onEnd(finalText) {
    recording = false;
    micBtn.classList.remove("recording");
    stopMeter();
    if (finalText) {
      answerInput.value = finalText;
      sendAnswer();
    } else if (!ended) {
      yourTurn();
    }
  },
  onError() {
    toast("Didn't catch that - try again or type.");
  },
});

async function startRecording() {
  if (!ready || ended) return;
  if (!recognizer.supported) {
    toast("Voice input needs Chrome/Edge - please type.");
    answerInput.focus();
    return;
  }
  recording = true;
  micBtn.classList.add("recording");
  answerInput.value = "";
  setAvatar("listening");
  setStatus("Listening... click the mic again when done");
  waveCanvas.classList.remove("hidden");
  try {
    meter = new AudioMeter();
    await meter.start();
    meter.drawWaveform(waveCanvas, {
      onLevel: (lvl) => { avatar.style.transform = `scale(${1 + lvl * 0.1})`; },
    });
  } catch {
    // Visualizer is optional.
  }
  recognizer.start();
}
function stopMeter() {
  meter?.stop();
  meter = null;
  avatar.style.transform = "";
  waveCanvas.classList.add("hidden");
}
function stopRecording() {
  if (recording) recognizer.stop();
  stopMeter();
  recording = false;
  micBtn.classList.remove("recording");
}

micBtn.addEventListener("click", () => recording ? recognizer.stop() : startRecording());
sendBtn.addEventListener("click", sendAnswer);
endBtn.addEventListener("click", endInterview);
answerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendAnswer();
  }
});

spkBtn.addEventListener("click", () => {
  voiceOn = !voiceOn;
  spkBtn.classList.toggle("active", voiceOn);
  spkBtn.innerHTML = icon(voiceOn ? "volume-2" : "volume-x");
  if (!voiceOn) stopAllSpeech();
});

let camStream = null;
camBtn.addEventListener("click", async () => {
  const view = $("#selfview");
  if (camStream) {
    camStream.getTracks().forEach(t => t.stop());
    camStream = null;
    view.classList.add("hidden");
    camBtn.classList.remove("active");
    camBtn.innerHTML = icon("video");
    return;
  }
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true });
    $("#cam").srcObject = camStream;
    view.classList.remove("hidden");
    camBtn.classList.add("active");
  } catch {
    toast("Camera unavailable.");
  }
});

hydrate();

// Try to bring up the Live2D interviewer; fall back to the gradient orb on any failure.
(async () => {
  try {
    live2d = await createAvatar($("#live2dCanvas"));
    $("#live2dCanvas").classList.remove("hidden");
    document.querySelector(".stage-canvas")?.classList.add("live2d-on");
  } catch (e) {
    console.warn("Live2D unavailable — using the orb:", e);
  }
})();

enableInput(false);
setProgress();
setStatus("Click start when you're ready");
setInterval(() => {
  if (ended || !startTs) return;
  const s = Math.floor((Date.now() - startTs) / 1000);
  $("#timer").textContent = `${String((s / 60) | 0).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}, 500);

// Start gate: the click unlocks the AudioContext + media playback, then we connect.
$("#gateBtn").addEventListener("click", () => {
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
  } catch { /* ignore — falls back to browser speech */ }
  $("#gate").classList.add("hidden");
  setAvatar("thinking");
  setStatus("Connecting...");
  startTs = Date.now();
  client.connect(cfg);
});
