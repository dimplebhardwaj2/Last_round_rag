// Voice: text-to-speech, speech recognition, and a live mic visualizer.
// All browser-native and free (Web Speech API + Web Audio API).

// ---- Text to speech ----
export function speak(text, { onStart, onEnd } = {}) {
  if (!("speechSynthesis" in window) || !text) { onEnd?.(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1.02; u.pitch = 1.0;
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find(v => /en[-_]US/i.test(v.lang) && /natural|google|jenny|aria/i.test(v.name))
    || voices.find(v => /en/i.test(v.lang));
  if (preferred) u.voice = preferred;
  u.onstart = () => onStart?.();
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

export const stopSpeaking = () => window.speechSynthesis?.cancel();

// ---- Speech to text ----
export function createRecognizer({ onResult, onInterim, onStart, onEnd, onError } = {}) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return { supported: false, start() {}, stop() {} };

  const rec = new SR();
  rec.lang = "en-US";
  rec.continuous = true;
  rec.interimResults = true;
  let finalText = "";

  rec.onstart = () => { finalText = ""; onStart?.(); };
  rec.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += t + " ";
      else interim += t;
    }
    onInterim?.((finalText + interim).trim());
  };
  rec.onerror = (e) => onError?.(e.error);
  rec.onend = () => onEnd?.(finalText.trim());

  return {
    supported: true,
    start() { try { rec.start(); } catch {} },
    stop() { try { rec.stop(); } catch {} },
  };
}

// ---- Live mic visualizer (Web Audio analyser) ----
export class AudioMeter {
  constructor() { this.ctx = null; this.stream = null; this.analyser = null; this.raf = null; }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 256;
    src.connect(this.analyser);
    this.data = new Uint8Array(this.analyser.frequencyBinCount);
  }

  level() {
    if (!this.analyser) return 0;
    this.analyser.getByteFrequencyData(this.data);
    let sum = 0;
    for (const v of this.data) sum += v;
    return Math.min(1, (sum / this.data.length) / 90);
  }

  // Draw animated bars onto a canvas; call once, it self-loops until stop().
  drawWaveform(canvas, { onLevel } = {}) {
    const c = canvas.getContext("2d");
    const render = () => {
      this.raf = requestAnimationFrame(render);
      if (!this.analyser) return;
      this.analyser.getByteFrequencyData(this.data);
      const w = canvas.width, h = canvas.height;
      c.clearRect(0, 0, w, h);
      const bars = 48, step = Math.floor(this.data.length / bars);
      const bw = w / bars;
      let peak = 0;
      for (let i = 0; i < bars; i++) {
        const v = this.data[i * step] / 255;
        peak = Math.max(peak, v);
        const bh = Math.max(2, v * h);
        const grad = c.createLinearGradient(0, h, 0, h - bh);
        grad.addColorStop(0, "#2563eb"); grad.addColorStop(1, "#60a5fa");
        c.fillStyle = grad;
        c.fillRect(i * bw + 1, h - bh, bw - 2, bh);
      }
      onLevel?.(peak);
    };
    render();
  }

  stop() {
    cancelAnimationFrame(this.raf);
    this.stream?.getTracks().forEach(t => t.stop());
    this.ctx?.close().catch(() => {});
    this.ctx = this.analyser = this.stream = null;
  }
}
