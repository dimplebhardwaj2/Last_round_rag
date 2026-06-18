// Shared constants and the WebSocket URL builder.

export const WS_URL = () => {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/interview`;
};

export const ROLES = [
  "Software Engineer", "Backend Engineer", "Frontend Engineer",
  "Data Scientist", "Machine Learning Engineer", "DevOps Engineer", "Product Manager",
];

export const LEVELS = ["Junior", "Mid-Level", "Senior"];

export const STYLES = [
  { id: "Friendly", ic: "smile", desc: "Warm & encouraging" },
  { id: "Technical", ic: "cpu", desc: "Precise & neutral" },
  { id: "Challenging", ic: "flame", desc: "Probes hard" },
];

export const TYPES = [
  { id: "behavioral", label: "Behavioral", ic: "message-square" },
  { id: "coding", label: "Coding", ic: "code" },
  { id: "system_design", label: "System Design", ic: "server" },
];

// Criteria shown in the live panel (the dimensions the final report scores).
export const ASSESS_FOCUS = [
  { ic: "message-square", label: "Communication" },
  { ic: "cpu", label: "Technical depth" },
  { ic: "target", label: "Problem solving" },
  { ic: "clipboard", label: "Structure & clarity" },
];
