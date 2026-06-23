const $ = (id) => document.getElementById(id);

// The endpoint is FIXED to the official server. It is intentionally NOT
// user-editable: this extension reads your Leonardo session, so it must only
// ever send it to GenityBoost — never to an arbitrary URL someone tells you to
// paste. background.js independently enforces the same allowlist.
const ENDPOINT = "https://api.genityboost.site/connect/account";

// load saved connect token
chrome.storage.local.get(["ctoken"], (r) => {
  $("ctoken").value = r.ctoken || "";
});

function setStatus(msg, cls) {
  const el = $("status");
  el.textContent = msg;
  el.className = cls || "muted";
}

$("btn").addEventListener("click", () => {
  const connectToken = $("ctoken").value.trim();
  chrome.storage.local.set({ ctoken: connectToken });
  $("btn").disabled = true;
  setStatus("Reading credentials & sending to the server...", "muted");

  chrome.runtime.sendMessage({ type: "connect", endpoint: ENDPOINT, connectToken }, (r) => {
    $("btn").disabled = false;
    if (!r) { setStatus("No response (service worker?).", "err"); return; }
    if (r.error) { setStatus("FAILED: " + r.error, "err"); return; }
    if (r.ok) {
      const left = (r.tokens == null ? "?" : r.tokens);
      setStatus(
        `CONNECTED \u2713\nemail: ${r.email}\nplan: ${r.plan || "?"}\ntokens left: ${left}\nsession until: ${(r.expiresAt || "").slice(0,10)}\n\nAccount linked. You can close this tab.`,
        "ok"
      );
    } else {
      const e = (r.out && (r.out.error || r.out.message)) || JSON.stringify(r.out || {});
      setStatus(`Server rejected (${r.status}): ${e}`, "err");
    }
  });
});
