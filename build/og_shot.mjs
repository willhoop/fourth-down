// Screenshot local HTML files at 1200x630 through headless Edge's DevTools port.
// Usage: node og_shot.mjs <port> <in.html> <out.png> [<in.html> <out.png> ...]
const [port, ...pairs] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets; for (let i = 0; i < 60; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await sleep(250); } }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map();
ws.addEventListener("message", (m) => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const fs = await import("fs");
await send("Emulation.setDeviceMetricsOverride", { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
for (let i = 0; i < pairs.length; i += 2) {
  await send("Page.navigate", { url: "file:///" + pairs[i].split(String.fromCharCode(92)).join("/") }); await sleep(i === 0 ? 2500 : 700);
  const s = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1200, height: 630, scale: 1 } });
  fs.writeFileSync(pairs[i + 1], Buffer.from(s.result.data, "base64"));
}
ws.close();
