// Fetch neural TTS audio (edge-tts) from the backend as a playable blob URL.

export async function fetchTTSUrl(text) {
  const res = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("tts " + res.status);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// Read an audio file's duration (seconds) without playing it.
export function audioDuration(url) {
  return new Promise((resolve) => {
    const a = new Audio();
    a.preload = "metadata";
    a.addEventListener("loadedmetadata", () => resolve(isFinite(a.duration) ? a.duration : 0));
    a.addEventListener("error", () => resolve(0));
    a.src = url;
  });
}

// Rough fallback estimate when metadata isn't available (~150 wpm).
export function estimateSeconds(text) {
  return Math.max(2, (text.split(/\s+/).length / 150) * 60);
}
