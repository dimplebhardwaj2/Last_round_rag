// Hand off the interview config and the final report between pages.

const CONFIG_KEY = "lastround:config";
const REPORT_KEY = "lastround:report";

export const saveConfig = (cfg) => sessionStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
export const loadConfig = () => {
  try { return JSON.parse(sessionStorage.getItem(CONFIG_KEY)); }
  catch { return null; }
};

export const saveReport = (r) => sessionStorage.setItem(REPORT_KEY, JSON.stringify(r));
export const loadReport = () => {
  try { return JSON.parse(sessionStorage.getItem(REPORT_KEY)); }
  catch { return null; }
};
