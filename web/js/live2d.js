// Live2D avatar (pixi-live2d-display). Renders a rigged 2D interviewer and lip-syncs
// to an <audio> element via Web Audio RMS analysis. Libs are global (PIXI.live2d),
// loaded from CDN in interview.html. Any failure -> caller falls back to the orb.

const MODEL_URL =
  "https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display/test/assets/haru/haru_greeter_t03.model3.json";

// Common mouth-open parameter ids across Cubism 4 / 2 models.
const MOUTH_IDS = ["ParamMouthOpenY", "PARAM_MOUTH_OPEN_Y"];

export async function createAvatar(canvas) {
  if (!window.PIXI || !window.PIXI.live2d) throw new Error("Live2D libraries not loaded");

  const app = new PIXI.Application({
    view: canvas,
    backgroundAlpha: 0,
    antialias: true,
    autoDensity: true,
    resolution: window.devicePixelRatio || 1,
    resizeTo: canvas.parentElement,
  });

  const model = await PIXI.live2d.Live2DModel.from(MODEL_URL, { autoHitTest: false, autoFocus: false });
  app.stage.addChild(model);

  function fit() {
    const cw = canvas.clientWidth || 320;
    const ch = canvas.clientHeight || 420;
    const ZOOM = 1.9;                 // >1 crops to an upper-body portrait
    const HEAD_MARGIN = 0.06;         // gap above the head
    model.anchor.set(0.5, 0.5);       // center the model on its position
    model.scale.set((ch * ZOOM) / model.height);
    model.position.set(cw / 2, ch * (HEAD_MARGIN + ZOOM / 2));  // centered, head near top
  }
  fit();
  window.addEventListener("resize", fit);

  // --- mouth control ---------------------------------------------------------
  // Set the mouth AFTER motions are applied each update, so idle animation can't
  // overwrite it. This is the reliable place to inject lip-sync.
  let mouth = 0, target = 0;
  const core = model.internalModel.coreModel;
  const setMouth = (v) => { for (const id of MOUTH_IDS) { try { core.setParameterValueById(id, v); } catch {} } };

  const mm = model.internalModel.motionManager;
  const originalUpdate = mm.update.bind(mm);
  mm.update = function (coreModel, now) {
    const r = originalUpdate(coreModel, now);
    mouth += (target - mouth) * 0.5;          // smooth toward target
    setMouth(mouth);
    return r;
  };

  // --- audio analysis (RMS -> mouth target) ----------------------------------
  let actx = null, analyser = null, srcNode = null, buf = null, raf = 0;

  function attach(audioEl, sharedCtx) {
    try {
      actx = sharedCtx || actx || new (window.AudioContext || window.webkitAudioContext)();
      if (actx.state === "suspended") actx.resume();
      try { srcNode?.disconnect(); analyser?.disconnect(); } catch {}
      cancelAnimationFrame(raf);

      srcNode = actx.createMediaElementSource(audioEl);
      analyser = actx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.1;
      srcNode.connect(analyser);
      analyser.connect(actx.destination);     // route to speakers
      buf = new Float32Array(analyser.fftSize);

      const loop = () => {
        raf = requestAnimationFrame(loop);
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
        const rms = Math.sqrt(sum / buf.length);
        target = Math.min(1, rms * 7);          // map volume -> mouth open
      };
      loop();
    } catch (e) {
      console.warn("Live2D lip-sync attach failed:", e);
    }
  }

  function stop() {
    target = 0;
    cancelAnimationFrame(raf);
  }

  return {
    app, model, attach, stop,
    destroy() {
      try { cancelAnimationFrame(raf); srcNode?.disconnect(); analyser?.disconnect(); app.destroy(true, { children: true }); } catch {}
      window.removeEventListener("resize", fit);
    },
  };
}
