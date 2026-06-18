// Thin WebSocket client for the interview protocol.
//   send:    {type:"start", config} | {type:"answer", text} | {type:"end"}
//   receive: {type:"question", text} | {type:"report", report} | {type:"error", message}

import { WS_URL } from "./config.js";

export class InterviewClient {
  constructor(handlers = {}) { this.h = handlers; this.ws = null; }

  connect(config) {
    this.ws = new WebSocket(WS_URL());
    this.ws.onopen = () => {
      this.ws.send(JSON.stringify({ type: "start", config }));
      this.h.onOpen?.();
    };
    this.ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "question") this.h.onQuestion?.(m.text);
      else if (m.type === "report") this.h.onReport?.(m.report);
      else if (m.type === "error") this.h.onError?.(m.message);
    };
    this.ws.onclose = () => this.h.onClose?.();
    this.ws.onerror = () => this.h.onError?.("Connection error.");
  }

  answer(text) { this._send({ type: "answer", text }); }
  end() { this._send({ type: "end" }); }

  _send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
  }
}
