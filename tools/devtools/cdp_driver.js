// Minimal CDP driver — no dependencies, uses Node's built-in WebSocket.
// Usage: node cdp.js <url> <outPrefix> [windowW] [windowH]
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const url = process.argv[2];
const outPrefix = process.argv[3];
const W = process.argv[4] || "1920";
const H = process.argv[5] || "1080";
const PORT = 9333;
const profile = path.join(os.tmpdir(), "cdp-profile-" + Date.now());

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--hide-scrollbars", `--user-data-dir=${profile}`,
  `--remote-debugging-port=${PORT}`, `--window-size=${W},${H}`, "about:blank",
], { stdio: "ignore" });

async function targetWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const targets = await r.json();
      const page = targets.find((t) => t.type === "page");
      if (page && page.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error("chrome devtools never came up");
}

function client(ws) {
  let id = 0;
  const pending = new Map();
  const events = [];
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
    } else if (msg.method) events.push(msg.method);
  });
  return {
    send(method, params = {}) {
      const myId = ++id;
      return new Promise((resolve, reject) => {
        pending.set(myId, { resolve, reject });
        ws.send(JSON.stringify({ id: myId, method, params }));
      });
    },
    saw: (m) => events.includes(m),
  };
}

async function evaluate(c, expression) {
  const r = await c.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("JS threw: " + JSON.stringify(r.exceptionDetails));
  return r.result.value;
}

(async () => {
  const wsUrl = await targetWs();
  const ws = new WebSocket(wsUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  const c = client(ws);

  await c.send("Page.enable");
  await c.send("Runtime.enable");
  await c.send("Page.navigate", { url });
  for (let i = 0; i < 80 && !c.saw("Page.loadEventFired"); i++) await sleep(250);
  await sleep(4000);   // let the model recalc land and charts render

  const consoleErrors = await evaluate(c, `(() => {
    // nothing retroactive available; just report that the app initialised
    return document.documentElement.dataset.uiFit || "NO data-ui-fit (js may have thrown)";
  })()`);
  console.log("app state:", consoleErrors);

  // --- click the "Transport" ROW LABEL (not the chevron) ---
  const before = await evaluate(c, `(() => {
    const t = [...document.querySelectorAll('.lg-subcat-title')].find(e => e.textContent.trim().startsWith('Transport'));
    const row = t && t.closest('.lg-subcat-row');
    return {
      found: !!t,
      rowHasExpandableClass: !!(row && row.classList.contains('is-expandable')),
      titleCursor: t ? getComputedStyle(t).cursor : null,
      railOpen: document.getElementById('lg-rail-col').classList.contains('is-open'),
      openFlyouts: document.querySelectorAll('.lg-flyout.is-open').length,
      chevronExpanded: row ? row.querySelector('.lg-expand-btn').getAttribute('aria-expanded') : null,
    };
  })()`);
  console.log("before click:", JSON.stringify(before));

  await evaluate(c, `[...document.querySelectorAll('.lg-subcat-title')].find(e => e.textContent.trim().startsWith('Transport')).click()`);
  await sleep(700);   // past the .34s rail + .3s panel + row stagger

  const after = await evaluate(c, `(() => {
    const open = document.querySelector('.lg-flyout.is-open');
    const row = [...document.querySelectorAll('.lg-subcat-title')].find(e => e.textContent.trim().startsWith('Transport')).closest('.lg-subcat-row');
    return {
      railOpen: document.getElementById('lg-rail-col').classList.contains('is-open'),
      railWidth: Math.round(document.getElementById('lg-rail-col').getBoundingClientRect().width),
      openFlyoutLabel: open ? open.querySelector('.lg-flyout-head span').textContent.trim() : null,
      openFlyoutRows: open ? open.querySelectorAll('.lg-flyout-row').length : 0,
      chevronExpanded: row.querySelector('.lg-expand-btn').getAttribute('aria-expanded'),
      pageScrollsX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
  })()`);
  console.log("after click on the LABEL:", JSON.stringify(after));

  let shot = await c.send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(`${outPrefix}-open.png`, Buffer.from(shot.data, "base64"));

  // --- click it again to close ---
  await evaluate(c, `[...document.querySelectorAll('.lg-subcat-title')].find(e => e.textContent.trim().startsWith('Transport')).click()`);
  await sleep(700);
  const closed = await evaluate(c, `(() => ({
    railOpen: document.getElementById('lg-rail-col').classList.contains('is-open'),
    openFlyouts: document.querySelectorAll('.lg-flyout.is-open').length,
  }))()`);
  console.log("after second click (toggle closed):", JSON.stringify(closed));

  // --- and confirm the chevron still works on its own ---
  await evaluate(c, `document.querySelectorAll('.lg-expand-btn')[1].click()`);
  await sleep(600);
  const viaChevron = await evaluate(c, `(() => {
    const open = document.querySelector('.lg-flyout.is-open');
    return { openFlyoutLabel: open ? open.querySelector('.lg-flyout-head span').textContent.trim() : null };
  })()`);
  console.log("after clicking a CHEVRON:", JSON.stringify(viaChevron));
  shot = await c.send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(`${outPrefix}-chevron.png`, Buffer.from(shot.data, "base64"));

  ws.close();
  chrome.kill();
  await sleep(300);
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  console.log("done");
})().catch(async (e) => {
  console.error("FAILED:", e.message);
  chrome.kill();
  process.exit(1);
});
