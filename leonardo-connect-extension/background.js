/* ============================================================================
   background.js — Leonardo Connect (MV3 service worker)
   ----------------------------------------------------------------------------
   Why an extension (not a console script)?
     Leonardo's auth cookies (__Secure-better-auth.session_token, session_data.0/1,
     cognito, CF_Access_Token) are all HttpOnly → they CANNOT be read via
     document.cookie in the console. Only an extension with the "cookies"
     permission can read them.

   What it does:
     1. Read Leonardo's durable cookies (chrome.cookies).
     2. Fetch accessToken + email + token balance via /api/auth/get-session.
     3. POST to the server pool endpoint ({email, cookies[], accessToken, ...}).
        The server stores the durable cookies → it can re-mint accessToken for
        ~45 days (no need to re-connect every hour).
   ============================================================================ */

const GET_SESSION = "https://app.leonardo.ai/api/auth/get-session";

// collect all cookies on leonardo.ai (all subdomains)
async function collectLeonardoCookies() {
  const domains = ["leonardo.ai", "app.leonardo.ai", "auth.leonardo.ai"];
  const seen = new Map();
  for (const domain of domains) {
    const list = await chrome.cookies.getAll({ domain });
    for (const c of list) seen.set(c.name + "@" + c.domain, c);
  }
  const out = [];
  for (const c of seen.values()) {
    out.push({
      name: c.name, value: c.value, domain: c.domain, path: c.path,
      secure: c.secure, httpOnly: c.httpOnly, sameSite: c.sameSite,
      expirationDate: c.expirationDate || null,
    });
  }
  return out;
}

async function fetchSession() {
  const r = await fetch(GET_SESSION, {
    headers: { Accept: "application/json", Referer: "https://app.leonardo.ai/" },
    credentials: "include",
  });
  if (!r.ok) throw new Error("get-session HTTP " + r.status);
  const j = await r.json();
  if (!j || !j.session) throw new Error("not logged in at app.leonardo.ai");
  return j;
}

async function fetchCredits(accessToken) {
  try {
    const r = await fetch("https://api.leonardo.ai/v1/graphql", {
      method: "POST",
      headers: { Authorization: "Bearer " + accessToken, "Content-Type": "application/json" },
      body: JSON.stringify({ query: "{ user_details { plan subscriptionTokens paidTokens } }" }),
    });
    const j = await r.json();
    return (j.data && j.data.user_details && j.data.user_details[0]) || {};
  } catch (_) {
    return {};
  }
}

async function doConnect(endpoint, connectToken) {
  // SECURITY: this extension reads the user's Leonardo session, so it must only
  // ever transmit it to the official GenityBoost server. Enforce an allowlist
  // here regardless of what the caller passed — defence against a tampered popup
  // or a social-engineering attempt to redirect credentials elsewhere.
  let host = "";
  try { host = new URL(endpoint).host; } catch (_) {}
  const ALLOWED = ["api.genityboost.site"];
  if (!ALLOWED.includes(host)) {
    throw new Error("blocked: endpoint must be " + ALLOWED[0]);
  }

  const sess = await fetchSession();
  const accessToken = sess.session.accessToken;
  const userId = sess.session.userId || sess.session.hasuraUserId;
  const email = (sess.user && sess.user.email) || "";
  const expiresAt = sess.session.expiresAt || null;

  const cookies = await collectLeonardoCookies();
  const names = new Set(cookies.map((c) => c.name));
  const missing = ["__Secure-better-auth.session_token",
    "__Secure-better-auth.session_data.0",
    "__Secure-better-auth.session_data.1"].filter((n) => !names.has(n));
  if (missing.length) {
    throw new Error("durable cookies incomplete (" + missing.join(", ") + "). Reload app.leonardo.ai and try again.");
  }

  const ud = await fetchCredits(accessToken);

  const payload = {
    provider: "leonardo",
    email,
    userId,
    accessToken,
    cookies,
    sessionExpiresAt: expiresAt,
    plan: ud.plan || null,
    subscriptionTokens: typeof ud.subscriptionTokens === "number" ? ud.subscriptionTokens : null,
    connectToken: connectToken || "",
    source: "leonardo_connect_extension",
  };

  const resp = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const out = await resp.json().catch(() => ({}));
  return { ok: resp.ok, status: resp.status, out, email, plan: payload.plan, tokens: payload.subscriptionTokens, expiresAt };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "connect") {
    doConnect(msg.endpoint, msg.connectToken)
      .then((r) => sendResponse(r))
      .catch((e) => sendResponse({ ok: false, error: String((e && e.message) || e) }));
    return true; // async
  }
});
