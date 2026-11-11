/* Hamlet Pump – dashboard card.
 *
 *   type: custom:hamlet-pump-card
 *   pump: Borehole        # optional: name or entry id, default = first pump
 *   show_today: true      # water / run time / starts today
 *
 * Loaded automatically by the Hamlet Pump integration – no resource to add.
 */
(() => {
const DOMAIN = "hamlet_pump";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v) => (v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? null : Number(v));
const fmtW = (w) => { w = num(w); if (w === null) return "–"; return Math.abs(w) >= 1000 ? `${(w / 1000).toFixed(1)} kW` : `${Math.round(w)} W`; };
const fmtL = (l) => { l = num(l); if (l === null) return "–"; return l >= 10000 ? `${(l / 1000).toFixed(1)} kL` : `${Math.round(l).toLocaleString()} L`; };
const fmtMin = (s) => { s = num(s); if (s === null) return "–"; const m = Math.round(s / 60); return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m} min`; };
const tstr = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");

const STYLE = `
:host { --c-water: #2a78d6; --c-water2: #6fb1f2; --c-run: #1baf7a; --c-ok: var(--success-color, #2e9e4f);
  --c-warn: var(--warning-color, #e08a00); --c-bad: var(--error-color, #db4437);
  --muted: var(--secondary-text-color); --line: var(--divider-color, rgba(127,127,127,.2)); --accent: var(--primary-color); --tank: #3f6b4a; }
:host([dark]) { --c-water: #3987e5; --c-water2: #2c5f99; --c-run: #199e70; --tank: #34573d; }
ha-card { padding: 16px; display: flex; flex-direction: column; gap: 12px; overflow: hidden; }
.head { display: flex; align-items: center; gap: 10px; min-width: 0; }
.head .name { font-size: 16px; font-weight: 500; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
.head ha-icon { --mdc-icon-size: 22px; color: var(--bc, var(--muted)); }
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; white-space: nowrap;
  background: color-mix(in srgb, var(--bc, var(--muted)) 16%, transparent); }
.badge .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--bc, var(--muted)); }
.badge.pulse .dot { animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .3; } }
.main { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 14px; align-items: center; }
.pic svg { display: block; width: 96px; height: auto; overflow: visible; }
.wave { animation: wave 4s ease-in-out infinite alternate; } @keyframes wave { to { transform: translateX(-20px); } }
.imp { transform-box: fill-box; transform-origin: center; } .spin .imp { animation: spin .7s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .wave, .spin .imp, .badge.pulse .dot { animation: none; } }
.stats { display: grid; gap: 6px; min-width: 0; }
.stat { display: flex; align-items: center; gap: 8px; font-size: 13px; min-width: 0; }
.stat ha-icon { --mdc-icon-size: 18px; color: var(--ic, var(--muted)); flex: none; }
.stat .l { color: var(--muted); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat .v { font-variant-numeric: tabular-nums; white-space: nowrap; font-weight: 500; }
.reason { font-size: 13px; color: var(--muted); line-height: 1.35; }
.alarm { font-size: 13px; padding: 8px 10px; border-radius: 8px; display: flex; gap: 8px; align-items: center;
  background: color-mix(in srgb, var(--c-bad) 12%, transparent); }
.alarm span { flex: 1; }
.modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.modes button, .alarm button { font: inherit; font-size: 13px; padding: 8px 2px; border-radius: 10px; cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 2px;
  background: transparent; color: var(--primary-text-color); border: 1px solid var(--line); }
.alarm button { padding: 4px 10px; border-color: var(--c-bad); color: var(--c-bad); }
.modes button ha-icon { --mdc-icon-size: 20px; }
.modes button[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--text-primary-color, #fff); }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.foot { display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: 12px; color: var(--muted); flex-wrap: wrap; }
.foot a { color: var(--accent); text-decoration: none; font-weight: 500; cursor: pointer; }
.msg { color: var(--muted); font-size: 14px; padding: 8px 0; }
`;

function miniPic(s) {
  const L = s.live || {}; const run = !!L.running;
  if (s.type === "booster") {
    const p = num(L.pressure), max = Math.max(6, Math.ceil((p || 0) * 1.25)), fr = p === null ? 0 : Math.min(1, p / max);
    const r = 40, cx = 48, cy = 46, pt = (f) => { const a = ((135 + 270 * f) * Math.PI) / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
    const arc = (b) => { const [x1, y1] = pt(0), [x2, y2] = pt(b); return `M${x1.toFixed(1)} ${y1.toFixed(1)} A${r} ${r} 0 ${b * 270 > 180 ? 1 : 0} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`; };
    return `<svg viewBox="0 0 96 96"><path d="${arc(1)}" fill="none" stroke="var(--line)" stroke-width="8" stroke-linecap="round"/>
      ${fr > 0.01 ? `<path d="${arc(fr)}" fill="none" stroke="var(--c-water)" stroke-width="8" stroke-linecap="round"/>` : ""}
      <text x="${cx}" y="${cy + 6}" text-anchor="middle" style="font-size:22px;font-weight:300;fill:var(--primary-text-color)">${p === null ? "–" : p.toFixed(1)}</text>
      <text x="${cx}" y="${cy + 20}" text-anchor="middle" style="font-size:10px;fill:var(--muted)">bar</text>
      <g class="${run ? "spin" : ""}"><circle cx="${cx}" cy="86" r="8" fill="none" stroke="${run ? "var(--c-run)" : "var(--muted)"}" stroke-width="1.6"/><g class="imp"><path d="M${cx} 80 v12 M${cx - 6} 86 h12" stroke="${run ? "var(--c-run)" : "var(--muted)"}" stroke-width="1.6"/></g></g></svg>`;
  }
  if (s.type === "irrigation") {
    return `<svg viewBox="0 0 96 96"><g transform="translate(24 20) scale(2)"><path d="M6 10 Q13 -2 20 10" fill="none" stroke="var(--c-water)" stroke-width="2" stroke-linecap="round" stroke-dasharray="2 3" opacity="${run ? 1 : .25}"/>
      <rect x="10" y="12" width="6" height="10" rx="1.5" fill="${run ? "var(--c-water)" : "var(--muted)"}"/><rect x="7" y="21" width="12" height="3" rx="1" fill="var(--muted)"/></g></svg>`;
  }
  const lvl = num(L.level); const frac = lvl !== null ? Math.max(0, Math.min(1, lvl / 100)) : L.tank_full ? 0.95 : L.tank_low ? 0.12 : 0.5;
  const known = lvl !== null || s.features.tank_full || s.features.tank_low;
  const wy = 12 + 76 * (1 - frac);
  return `<svg viewBox="0 0 96 96"><defs><clipPath id="c"><rect x="14" y="8" width="68" height="84" rx="10"/></clipPath></defs>
    <rect x="12" y="6" width="72" height="88" rx="12" fill="var(--tank)"/>
    <g clip-path="url(#c)"><rect x="14" y="8" width="68" height="84" fill="color-mix(in srgb, var(--card-background-color, #fff) 82%, var(--tank))"/>
      ${known ? `<g class="wave"><path d="M-10 ${wy} q 10 -4 20 0 t 20 0 t 20 0 t 20 0 t 20 0 t 20 0 V 100 H -10 Z" fill="var(--c-water)"/></g>` : ""}</g>
    <text x="48" y="58" text-anchor="middle" style="font-size:22px;font-weight:300;fill:#fff;paint-order:stroke;stroke:rgba(0,0,0,.25);stroke-width:2px">${lvl !== null ? Math.round(lvl) + "%" : L.tank_full ? "Full" : L.tank_low ? "Low" : ""}</text>
    ${run ? `<circle cx="80" cy="12" r="7" fill="var(--c-run)"/><path d="M77 12 h6 M80 9 v6" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>` : ""}</svg>`;
}

class HamletPumpCard extends HTMLElement {
  static getStubConfig() { return { type: "custom:hamlet-pump-card" }; }

  setConfig(config) {
    this._config = { show_today: true, ...config };
    if (this._hass) this._connect(true);
  }
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this.toggleAttribute("dark", !!hass.themes?.darkMode);
    if (first) this._connect(false);
  }
  getCardSize() { return 4; }
  getGridOptions() { return { columns: 6, min_columns: 4, rows: "auto" }; }

  connectedCallback() { if (this._hass && !this._unsub && this._entryId) this._subscribe(); }
  disconnectedCallback() { if (this._unsub) { this._unsub(); this._unsub = null; } }

  _shell() {
    if (this._root) return;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div id="body"><div class="msg">Loading pump…</div></div></ha-card>`;
    this._root = this.shadowRoot.getElementById("body");
    this._root.addEventListener("click", (ev) => this._click(ev));
  }

  async _connect(reconfigured) {
    this._shell();
    if (reconfigured && this._unsub) { this._unsub(); this._unsub = null; }
    try {
      const list = await this._hass.callWS({ type: `${DOMAIN}/list` });
      const want = (this._config?.pump || "").toString().trim().toLowerCase();
      const hit = want ? list.find((e) => e.entry_id === this._config.pump || e.name.toLowerCase() === want) : list[0];
      if (!hit) {
        this._root.innerHTML = `<div class="msg">${list.length ? `No pump called “${esc(this._config.pump)}”. Available: ${list.map((e) => esc(e.name)).join(", ")}` : "Hamlet Pump isn't set up yet – add it in Settings → Devices &amp; services."}</div>`;
        return;
      }
      this._entryId = hit.entry_id;
      this._subscribe();
    } catch (e) {
      this._root.innerHTML = `<div class="msg">Hamlet Pump integration not found (${esc(e.message || e.code || e)}).</div>`;
    }
  }

  async _subscribe() {
    if (!this._entryId || this._unsub || !this.isConnected) return;
    try {
      this._unsub = await this._hass.connection.subscribeMessage((snap) => { this._snap = snap; this._render(); }, { type: `${DOMAIN}/subscribe`, entry_id: this._entryId });
    } catch (e) { /* retry on next connect */ }
  }

  async _click(ev) {
    const t = ev.target.closest("[data-mode],[data-open],[data-reset]");
    if (!t) return;
    if (t.dataset.open !== undefined) {
      history.pushState(null, "", "/hamlet-pump");
      window.dispatchEvent(new CustomEvent("location-changed"));
      return;
    }
    try {
      const msg = t.dataset.reset !== undefined ? { type: `${DOMAIN}/reset`, entry_id: this._entryId }
        : { type: `${DOMAIN}/set_mode`, entry_id: this._entryId, mode: t.dataset.mode, ...(t.dataset.mode === "run" && this._snap?.zones?.length ? { zone: 0 } : {}) };
      this._snap = await this._hass.callWS(msg); this._render();
    } catch (e) {
      this._hass.callService?.("persistent_notification", "create", { title: "Hamlet Pump", message: e.message || String(e) });
    }
  }

  _render() {
    const s = this._snap; if (!s || !this._root) return;
    const d = s.decision || {}; const L = s.live || {}; const f = s.features || {}; const T = s.today || {};
    const run = !!L.running;
    const color = s.fault || ["Fault", "VFD fault", "Offline"].includes(d.status) ? "var(--c-bad)"
      : ["Resting", "Tank low", "Rain skip", "Rain delay", "Waiting", "Load shed"].includes(d.status) ? "var(--c-warn)" : run ? "var(--c-run)" : d.status === "Off" ? "var(--muted)" : "var(--c-water)";
    const st = (icon, ic, l, v) => `<div class="stat" style="--ic:${ic}"><ha-icon icon="${icon}"></ha-icon><span class="l">${l}</span><span class="v">${v}</span></div>`;
    const stats = [];
    if (f.pressure && s.type !== "booster") stats.push(st("mdi:gauge", "var(--c-water)", "Pressure", `${num(L.pressure)?.toFixed(1) ?? "–"} bar`));
    if (f.level && s.type !== "borehole") stats.push(st("mdi:storage-tank", "var(--c-water)", "Supply tank", `${Math.round(num(L.level) ?? 0)}%`));
    stats.push(st("mdi:waves-arrow-right", "var(--c-water)", "Flow", run ? `${num(L.flow_est)?.toFixed(0) ?? "–"} L/min` : "–"));
    stats.push(st("mdi:flash", "#eda100", "Power", fmtW(L.power_est)));
    if (this._config.show_today) {
      stats.push(st("mdi:water", "var(--c-water)", "Water today", fmtL(T.litres)));
      stats.push(st("mdi:timer-outline", "var(--muted)", "Ran today", `${fmtMin(T.run_s)} · ${Math.round(T.starts || 0)}×`));
    }
    const mb = (m, icon, label) => `<button data-mode="${m}" aria-pressed="${s.mode === m}"><ha-icon icon="${icon}"></ha-icon>${label}</button>`;
    const html = `
      <div class="head" style="--bc:${color}"><ha-icon icon="${s.type === "irrigation" ? "mdi:sprinkler-variant" : s.type === "booster" ? "mdi:water-pump" : "mdi:storage-tank"}"></ha-icon>
        <span class="name" data-open>${esc(s.name)}</span><span class="badge ${run ? "pulse" : ""}"><span class="dot"></span>${esc(d.status || "…")}</span></div>
      <div class="main"><div class="pic">${miniPic(s)}</div><div class="stats">${stats.join("")}</div></div>
      ${s.fault ? "" : `<div class="reason">${esc(d.reason || "")}</div>`}
      ${s.fault ? `<div class="alarm"><span>Locked out – open the page for details.</span><button data-reset>Reset</button></div>` : ""}
      <div class="modes">${mb("auto", "mdi:auto-mode", "Auto")}${mb("run", "mdi:timer-play-outline", s.type === "irrigation" ? "Water" : "Run")}${mb("on", "mdi:power", "On")}${mb("off", "mdi:power-off", "Off")}</div>
      <div class="foot"><span>${s.mode === "run" && s.run_until ? `Running until ${tstr(s.run_until)}` : s.next && s.type !== "booster" ? `Next ${s.type === "irrigation" ? "program" : "timer"} ${tstr(s.next)}` : ""}</span><a data-open>Pumps page ›</a></div>`;
    if (this._root._html !== html) { this._root._html = html; this._root.innerHTML = html; }
  }
}

if (!customElements.get("hamlet-pump-card")) customElements.define("hamlet-pump-card", HamletPumpCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "hamlet-pump-card")) {
  window.customCards.push({ type: "hamlet-pump-card", name: "Hamlet Pump", description: "Borehole, pressure pump or irrigation – status, tank / pressure and quick controls.", preview: false });
}
})();
