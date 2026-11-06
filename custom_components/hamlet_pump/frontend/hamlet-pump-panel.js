/* Hamlet Pump – sidebar panel for Home Assistant. No build step, no dependencies. */
const DOMAIN = "hamlet_pump";
const DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
const TYPE_LABEL = { borehole: "Borehole & tank", booster: "Pressure pump", irrigation: "Irrigation" };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v) => (v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? null : Number(v));
const fmtW = (w) => { w = num(w); if (w === null) return "–"; const a = Math.abs(w); return a >= 1000 ? `${(w / 1000).toFixed(a >= 10000 ? 0 : 1)} kW` : `${Math.round(w)} W`; };
const fmtL = (l) => { l = num(l); if (l === null) return "–"; return l >= 10000 ? `${(l / 1000).toFixed(1)} kL` : `${Math.round(l).toLocaleString()} L`; };
const fmtMin = (s) => { s = num(s); if (s === null) return "–"; const m = Math.round(s / 60); return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`; };
const hhmm = (mins) => `${String(Math.floor(mins / 60)).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`;
const tstr = (iso) => { if (!iso) return ""; const d = new Date(iso); return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); };
const dstr = (iso) => { if (!iso) return ""; const d = new Date(iso); const today = new Date(); const same = d.toDateString() === today.toDateString();
  return same ? tstr(iso) : `${d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" })} ${tstr(iso)}`; };

const STYLE = `
:host {
  display: block; min-height: 100%;
  background: var(--primary-background-color);
  color: var(--primary-text-color);
  font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif);
  --gap: 16px; --radius: var(--ha-card-border-radius, 12px);
  --card: var(--card-background-color, #fff);
  --muted: var(--secondary-text-color, #6b6b6b);
  --line: var(--divider-color, rgba(127,127,127,.2));
  --accent: var(--primary-color, #03a9f4);
  --c-water: #2a78d6; --c-water2: #6fb1f2; --c-run: #1baf7a; --c-power: #eda100;
  --c-ok: var(--success-color, #2e9e4f); --c-warn: var(--warning-color, #e08a00); --c-bad: var(--error-color, #db4437);
  --tank: #3f6b4a; --tank-hi: #4f8159;
}
:host([dark]) { --c-water: #3987e5; --c-water2: #2c5f99; --c-run: #199e70; --c-power: #c98500; --tank: #34573d; --tank-hi: #41704c; }
* { box-sizing: border-box; }
[hidden] { display: none !important; }
:host([embedded]) { min-height: 0; background: transparent; }
:host([embedded]) .toolbar { position: static; height: auto; min-height: 0; padding: 12px 16px 0; background: none; border: 0; color: var(--primary-text-color); max-width: 1240px; margin: 0 auto; }
:host([embedded]) #menu, :host([embedded]) .toolbar .title { display: none; }
.toolbar { display: flex; align-items: center; gap: 8px; height: var(--header-height, 56px); padding: 0 12px;
  background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff);
  border-bottom: var(--app-header-border-bottom, none); position: sticky; top: 0; z-index: 2; }
.toolbar .title { font-size: 20px; font-weight: 400; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tabs { display: flex; gap: 4px; overflow-x: auto; }
.tabs button { background: transparent; border: 0; color: inherit; opacity: .7; padding: 8px 12px; font: inherit; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.tabs button[aria-selected="true"] { opacity: 1; border-bottom-color: currentColor; }
main { max-width: 1240px; margin: 0 auto; padding: var(--gap); display: grid; gap: var(--gap); grid-template-columns: minmax(0, 1fr); }
@media (min-width: 900px) { main { grid-template-columns: 380px minmax(0, 1fr); } .span2 { grid-column: 1 / -1; } }
.card { background: var(--card); border-radius: var(--radius); box-shadow: var(--ha-card-box-shadow, none);
  border: 1px solid var(--ha-card-border-color, var(--line)); padding: 16px; min-width: 0; }
h2 { font-size: 16px; font-weight: 500; margin: 0 0 12px; display: flex; align-items: center; gap: 8px; }
h2 .sub { margin-left: auto; font-size: 13px; font-weight: 400; color: var(--muted); }
h3 { font-size: 14px; font-weight: 500; margin: 18px 0 4px; }
.muted { color: var(--muted); } .small { font-size: 13px; }
.loading { padding: 64px; text-align: center; color: var(--muted); }

/* hero */
.hero { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 12px; }
.pic { width: 260px; max-width: 100%; position: relative; }
.pic svg { display: block; width: 100%; height: auto; overflow: visible; }
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-size: 14px; font-weight: 500;
  background: color-mix(in srgb, var(--bc, var(--muted)) 14%, transparent); }
.badge .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--bc, var(--muted)); }
.badge.pulse .dot { animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .3; } }
.reason { font-size: 14px; color: var(--muted); min-height: 20px; }
.modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; width: 100%; }
.modes button { font: inherit; font-size: 14px; padding: 10px 4px; border-radius: 10px; cursor: pointer;
  background: transparent; color: var(--primary-text-color); border: 1px solid var(--line); display: flex; flex-direction: column; align-items: center; gap: 4px; }
.modes button ha-icon { --mdc-icon-size: 22px; }
.modes button[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--text-primary-color, #fff); }
button:focus-visible, input:focus-visible, select:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.chips { display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; }
.chip { font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--line); background: transparent; color: var(--primary-text-color); cursor: pointer; }
.chip[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
.alarm { width: 100%; text-align: left; border-radius: 10px; padding: 12px; display: flex; gap: 10px; align-items: flex-start;
  background: color-mix(in srgb, var(--ac, var(--c-bad)) 12%, transparent); border: 1px solid color-mix(in srgb, var(--ac, var(--c-bad)) 40%, transparent); font-size: 14px; }
.alarm ha-icon { color: var(--ac, var(--c-bad)); flex: none; }
.alarm .txt { flex: 1; }
.alarm .btn { flex: none; }

/* svg pieces */
.pipe { fill: none; stroke: var(--line); stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; }
.wet { fill: none; stroke: var(--c-water); stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; opacity: 0; }
.dots { fill: none; stroke: #fff; stroke-width: 2.5; stroke-linecap: round; stroke-dasharray: 1 10; opacity: 0; }
.on .wet { opacity: .55; } .on .dots { opacity: .95; animation: dots 0.9s linear infinite; }
@keyframes dots { to { stroke-dashoffset: -22; } }
.imp { transform-box: fill-box; transform-origin: center; } .spin .imp { animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.wave { animation: wave 4s ease-in-out infinite alternate; } @keyframes wave { to { transform: translateX(-30px); } }
.soil { fill: color-mix(in srgb, #8a6a43 22%, transparent); }
.lbl { font-size: 11px; fill: var(--muted); } .val { font-size: 26px; font-weight: 300; fill: var(--primary-text-color); font-variant-numeric: tabular-nums; }
.gtxt { font-size: 40px; font-weight: 300; fill: var(--primary-text-color); font-variant-numeric: tabular-nums; }
.spray { opacity: 0; } .zone.on .spray { opacity: 1; animation: spray 1.2s ease-out infinite; }
@keyframes spray { 0% { opacity: .9; transform: translateY(2px) scale(.7); } 100% { opacity: 0; transform: translateY(-6px) scale(1.15); } }
.spray { transform-box: fill-box; transform-origin: bottom center; }
@media (prefers-reduced-motion: reduce) { .on .dots, .spin .imp, .wave, .zone.on .spray, .badge.pulse .dot { animation: none; } }

/* zones */
.zones { display: grid; gap: 6px; width: 100%; }
.zone { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; text-align: left; font-size: 14px; }
.zone.on { border-color: var(--c-water); background: color-mix(in srgb, var(--c-water) 8%, transparent); }
.zone svg { width: 26px; height: 26px; flex: none; overflow: visible; }
.zone .zn { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* tiles */
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(124px, 1fr)); gap: 10px; }
.tile { border: 1px solid var(--line); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.tile .lab { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); }
.tile .lab ha-icon { --mdc-icon-size: 18px; color: var(--ic, var(--muted)); }
.tile .v { font-size: 24px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.tile .note { font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar { height: 6px; border-radius: 3px; background: var(--line); overflow: hidden; margin-top: 4px; }
.bar i { display: block; height: 100%; border-radius: 3px; background: var(--c-water); }
.totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-top: 14px; }
.totals > div { border-top: 1px solid var(--line); padding-top: 8px; font-size: 13px; color: var(--muted); }
.totals .v { font-size: 20px; color: var(--primary-text-color); font-variant-numeric: tabular-nums; }

/* chart */
.chartwrap { position: relative; }
.chartwrap svg { display: block; width: 100%; height: 230px; touch-action: pan-y; }
.axis text { fill: var(--muted); font-size: 11px; } .grid line { stroke: var(--line); }
.tip { position: absolute; pointer-events: none; background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 10px; font-size: 12px; box-shadow: 0 4px 16px rgba(0,0,0,.15); white-space: nowrap; display: none; z-index: 1; }
.tip .row { display: flex; gap: 14px; justify-content: space-between; } .tip .row span:last-child { font-variant-numeric: tabular-nums; }
.legendrow { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.key { display: inline-flex; align-items: center; gap: 6px; } .key i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.seg button { font: inherit; font-size: 13px; padding: 4px 12px; border: 0; background: transparent; color: var(--primary-text-color); cursor: pointer; }
.seg button[aria-pressed="true"] { background: var(--accent); color: var(--text-primary-color, #fff); }
.days14 svg { display: block; width: 100%; height: 120px; }
.empty { padding: 40px 0; text-align: center; color: var(--muted); font-size: 14px; }

/* forms */
.form { display: grid; gap: 2px; }
.field { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.field:last-child { border-bottom: 0; }
.field label { font-size: 14px; } .field .hint { display: block; font-size: 12px; color: var(--muted); }
.field .ctl { display: flex; align-items: center; gap: 6px; flex: none; font-size: 13px; color: var(--muted); }
input[type=time], input[type=number], input[type=text], select { font: inherit; font-size: 14px; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--line);
  background: var(--secondary-background-color, transparent); color: var(--primary-text-color); color-scheme: inherit; }
input[type=number] { width: 80px; } input[type=text] { width: 220px; max-width: 100%; }
.switch { position: relative; width: 40px; height: 22px; flex: none; display: inline-block; }
.switch input { opacity: 0; width: 100%; height: 100%; margin: 0; position: absolute; cursor: pointer; z-index: 1; }
.switch span { position: absolute; inset: 0; border-radius: 11px; background: var(--line); transition: .15s; }
.switch span::after { content: ""; position: absolute; width: 16px; height: 16px; left: 3px; top: 3px; border-radius: 50%; background: #fff; transition: .15s; box-shadow: 0 1px 2px rgba(0,0,0,.3); }
.switch input:checked + span { background: var(--accent); } .switch input:checked + span::after { transform: translateX(18px); }
.sched { display: grid; grid-template-columns: auto 1fr; gap: 10px 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--line); }
.sched .times { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.sched .times .del { margin-left: auto; }
.days { display: flex; gap: 4px; flex-wrap: wrap; grid-column: 2; }
.days button { font: inherit; font-size: 12px; width: 34px; height: 30px; border-radius: 8px; border: 1px solid var(--line); background: transparent; color: var(--muted); cursor: pointer; }
.days button[aria-pressed="true"] { background: color-mix(in srgb, var(--accent) 16%, transparent); border-color: var(--accent); color: var(--primary-text-color); }
.zmins { grid-column: 2; display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 6px 12px; font-size: 13px; color: var(--muted); }
.zmins label { display: flex; align-items: center; gap: 6px; justify-content: space-between; }
.zmins input { width: 64px; }
.iconbtn { background: transparent; border: 0; color: var(--muted); cursor: pointer; padding: 6px; border-radius: 50%; }
.iconbtn:hover { color: var(--c-bad); }
.actions { display: flex; gap: 8px; justify-content: flex-end; align-items: center; margin-top: 12px; flex-wrap: wrap; }
.btn { font: inherit; font-size: 14px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--line); background: transparent; color: var(--primary-text-color); cursor: pointer; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--text-primary-color, #fff); }
.btn.danger { border-color: var(--c-bad); color: var(--c-bad); }
.btn:disabled { opacity: .5; cursor: default; }
.msg { font-size: 13px; } .msg.err { color: var(--c-bad); } .msg.ok { color: var(--c-ok); }
.cols2 { display: grid; gap: 0 32px; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 900px) { .cols2 { grid-template-columns: 1fr 1fr; } }
details summary { cursor: pointer; font-size: 14px; color: var(--muted); padding: 4px 0; }
.rawgrid { display: grid; grid-template-columns: 1fr auto; gap: 4px 16px; font-size: 13px; margin-top: 8px; word-break: break-all; }
.events { display: grid; gap: 8px; font-size: 13px; }
.ev { display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.ev:last-child { border-bottom: 0; }
.ev ha-icon { --mdc-icon-size: 18px; grid-row: span 2; color: var(--ic, var(--muted)); }
.ev .t { color: var(--muted); font-size: 12px; }
`;

/* ------------------------------------------------------------------ drawings */
function tankSvg(snap, running) {
  const L = snap.live || {}, f = snap.features || {}, s = snap.settings || {};
  const lvl = num(L.level);
  let frac = lvl !== null ? Math.max(0, Math.min(1, lvl / 100)) : (L.tank_full ? 0.95 : L.tank_low ? 0.12 : 0.55);
  const known = lvl !== null || f.tank_full || f.tank_low;
  const tx = 132, ty = 34, tw = 104, th = 150, wy = ty + 8 + (th - 14) * (1 - frac);
  const flowOn = running ? "on" : "";
  const ground = 150;
  const pipe = `M44 196 V64 Q44 56 52 56 H${tx + 30} Q${tx + 38} 56 ${tx + 38} 48 V${ty + 4}`;
  const ribs = [0.2, 0.4, 0.6, 0.8].map((r) => `<line x1="${tx + 2}" x2="${tx + tw - 2}" y1="${ty + th * r}" y2="${ty + th * r}" stroke="rgba(0,0,0,.18)" stroke-width="2"/>`).join("");
  const marks = [];
  if (f.level) {
    const ys = (p) => ty + 8 + (th - 14) * (1 - p / 100);
    marks.push(`<line x1="${tx + tw + 2}" x2="${tx + tw + 10}" y1="${ys(s.stop_level)}" y2="${ys(s.stop_level)}" stroke="var(--muted)" stroke-width="1.5"/>
      <text class="lbl" x="${tx + tw + 13}" y="${ys(s.stop_level) + 4}">${s.stop_level}%</text>`);
    if (snap.type === "borehole") marks.push(`<line x1="${tx + tw + 2}" x2="${tx + tw + 10}" y1="${ys(s.start_level)}" y2="${ys(s.start_level)}" stroke="var(--muted)" stroke-width="1.5"/>
      <text class="lbl" x="${tx + tw + 13}" y="${ys(s.start_level) + 4}">${s.start_level}%</text>`);
  }
  const float = (on, y, label) => `<g><circle cx="${tx + tw - 16}" cy="${y}" r="6" fill="${on ? "var(--c-water)" : "var(--card)"}" stroke="var(--muted)" stroke-width="1.5"/>
    <text class="lbl" x="${tx + tw - 26}" y="${y + 4}" text-anchor="end">${label}</text></g>`;
  if (f.tank_full) marks.push(float(L.tank_full, ty + 22, "full"));
  if (f.tank_low) marks.push(float(L.tank_low, ty + th - 26, "low"));
  const big = lvl !== null ? `${Math.round(lvl)}<tspan font-size="14">%</tspan>` : L.tank_full ? "Full" : L.tank_low ? "Low" : "";
  return `<svg viewBox="0 0 270 205" role="img" aria-label="Tank ${lvl !== null ? Math.round(lvl) + " percent" : ""}">
    <defs><clipPath id="tclip"><rect x="${tx + 3}" y="${ty + 3}" width="${tw - 6}" height="${th - 6}" rx="12"/></clipPath>
      <linearGradient id="wg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--c-water2)"/><stop offset="1" stop-color="var(--c-water)"/></linearGradient></defs>
    <rect class="soil" x="0" y="${ground}" width="110" height="55"/>
    <line x1="0" x2="270" y1="${ground}" y2="${ground}" stroke="var(--muted)" stroke-width="1.5" stroke-dasharray="4 4" opacity=".6"/>
    <rect x="36" y="${ground - 8}" width="16" height="60" rx="2" fill="none" stroke="var(--muted)" stroke-width="1.5"/>
    <g class="${flowOn}"><path class="pipe" d="${pipe}"/><path class="wet" d="${pipe}"/><path class="dots" d="${pipe}"/></g>
    <g class="${running ? "spin" : ""}"><rect x="37" y="186" width="14" height="19" rx="3" fill="var(--card)" stroke="${running ? "var(--c-run)" : "var(--muted)"}" stroke-width="2"/>
      <g class="imp"><path d="M44 191 v9 M39.5 195.5 h9" stroke="${running ? "var(--c-run)" : "var(--muted)"}" stroke-width="2" stroke-linecap="round"/></g></g>
    <text class="lbl" x="58" y="${ground + 16}">borehole</text>
    <rect x="${tx}" y="${ty}" width="${tw}" height="${th}" rx="14" fill="var(--tank)"/>
    <rect x="${tx + 30}" y="${ty - 8}" width="${tw - 60}" height="12" rx="4" fill="var(--tank-hi)"/>
    <g clip-path="url(#tclip)"><rect x="${tx}" y="${ty}" width="${tw}" height="${th}" fill="color-mix(in srgb, var(--card) 82%, var(--tank))"/>
      ${known ? `<g class="wave"><path d="M${tx - 40} ${wy} q 15 -5 30 0 t 30 0 t 30 0 t 30 0 t 30 0 t 30 0 V ${ty + th + 4} H ${tx - 40} Z" fill="url(#wg)"/></g>` : ""}</g>
    ${ribs}
    <text class="val" x="${tx + tw / 2}" y="${ty + th / 2 + 9}" text-anchor="middle" style="fill:#fff;paint-order:stroke;stroke:rgba(0,0,0,.25);stroke-width:2px">${big}</text>
    ${marks.join("")}
  </svg>`;
}

function gaugeSvg(snap, running) {
  const L = snap.live || {};
  const p = num(L.pressure);
  const max = Math.max(6, Math.ceil(((p ?? 0) * 1.25) || 0));
  const sweep = 270, r = 84, cx = 110, cy = 104;
  const pt = (fr) => { const a = ((135 + sweep * fr) * Math.PI) / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
  const arc = (a, b) => { const [x1, y1] = pt(a), [x2, y2] = pt(b); return `M${x1.toFixed(1)} ${y1.toFixed(1)} A${r} ${r} 0 ${(b - a) * sweep > 180 ? 1 : 0} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`; };
  const fr = p === null ? 0 : Math.max(0, Math.min(1, p / max));
  const low = num(snap.settings?.low_pressure_bar) || 0;
  const ticks = Array.from({ length: max + 1 }, (_, i) => { const [x, y] = pt(i / max); const [x2, y2] = [cx + (r - 18) * Math.cos(((135 + sweep * i / max) * Math.PI) / 180), cy + (r - 18) * Math.sin(((135 + sweep * i / max) * Math.PI) / 180)];
    return `<text class="lbl" x="${x2.toFixed(1)}" y="${(y2 + 4).toFixed(1)}" text-anchor="middle">${i}</text>`; }).join("");
  const hz = num(L.hz), flow = num(L.flow ?? L.flow_est);
  return `<svg viewBox="0 0 220 200" role="img" aria-label="Pressure ${p ?? "unknown"} bar">
    <path d="${arc(0, 1)}" fill="none" stroke="var(--line)" stroke-width="14" stroke-linecap="round"/>
    ${low > 0 ? `<path d="${arc(0, Math.min(low / max, 1))}" fill="none" stroke="var(--c-bad)" stroke-width="14" stroke-linecap="butt" opacity=".35"/>` : ""}
    ${p !== null && fr > 0.005 ? `<path d="${arc(0, fr)}" fill="none" stroke="var(--c-water)" stroke-width="14" stroke-linecap="round"/>` : ""}
    ${ticks}
    <text class="gtxt" x="${cx}" y="${cy + 6}" text-anchor="middle">${p === null ? "–" : p.toFixed(1)}<tspan font-size="16"> bar</tspan></text>
    <text class="lbl" x="${cx}" y="${cy + 26}" text-anchor="middle">${[hz !== null ? `${hz.toFixed(0)} Hz` : "", flow !== null && running ? `${flow.toFixed(0)} L/min` : ""].filter(Boolean).join(" · ") || (p === null ? "no pressure sensor" : "pressure")}</text>
    <g class="${running ? "spin" : ""}" transform="translate(${cx - 13} ${cy + 46})"><circle cx="13" cy="13" r="13" fill="var(--card)" stroke="${running ? "var(--c-run)" : "var(--muted)"}" stroke-width="2"/>
      <g class="imp"><path d="M13 4 Q19 9 13 13 Q7 17 13 22 M4 13 Q9 7 13 13 Q17 19 22 13" fill="none" stroke="${running ? "var(--c-run)" : "var(--muted)"}" stroke-width="2" stroke-linecap="round"/></g></g>
  </svg>`;
}

const sprinkler = (on) => `<svg viewBox="0 0 26 26"><g class="spray"><path d="M6 10 Q13 -2 20 10" fill="none" stroke="var(--c-water)" stroke-width="2" stroke-linecap="round" stroke-dasharray="2 3"/></g>
  <rect x="10" y="12" width="6" height="10" rx="1.5" fill="${on ? "var(--c-water)" : "var(--muted)"}"/><rect x="7" y="21" width="12" height="3" rx="1" fill="var(--muted)"/></svg>`;

/* -------------------------------------------------------------------- panel */
class HamletPumpPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._entries = []; this._entryId = null; this._snap = null; this._history = null; this._days = [];
    this._day = "today"; this._draft = null; this._dirty = false; this._unsub = null; this._built = false; this._narrow = false;
    this._runMin = 30;
  }
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this.toggleAttribute("dark", !!hass.themes?.darkMode);
    if (this._menuBtn) this._menuBtn.hass = hass;
    if (first) this._init();
  }
  get hass() { return this._hass; }
  set narrow(v) { this._narrow = v; if (this._menuBtn) this._menuBtn.narrow = v; }
  set panel(v) { this._panel = v; }
  set route(v) { this._route = v; }

  connectedCallback() {
    if (this._hass && !this._unsub && this._entryId) this._subscribe();
    this._histTimer = setInterval(() => this._loadState(), 5 * 60 * 1000);
    this._clock = setInterval(() => this._snap && this._renderHero(), 30 * 1000);
  }
  disconnectedCallback() {
    this._unsubscribe();
    clearInterval(this._histTimer); clearInterval(this._clock);
  }

  async _init() {
    const root = this.shadowRoot;
    root.innerHTML = `<style>${STYLE}</style>
      <div class="toolbar"><span id="menu"></span><div class="title">Pumps</div><div class="tabs" role="tablist"></div></div>
      <main><div class="card span2 loading">Loading…</div></main>`;
    this._main = root.querySelector("main");
    const mb = document.createElement("ha-menu-button");
    mb.hass = this._hass; mb.narrow = this._narrow;
    root.getElementById("menu").appendChild(mb);
    this._menuBtn = mb;
    root.addEventListener("click", (ev) => this._click(ev));
    root.addEventListener("input", (ev) => this._input(ev));
    root.addEventListener("change", (ev) => this._input(ev));
    try {
      this._entries = await this._hass.callWS({ type: `${DOMAIN}/list` });
    } catch (e) {
      this._main.innerHTML = `<div class="card span2 loading">Could not reach the pump integration: ${esc(e.message)}</div>`;
      return;
    }
    if (!this._entries.length) {
      this._main.innerHTML = `<div class="card span2 loading">No pump set up yet. Go to Settings → Devices &amp; services → Add integration → Hamlet Pump.</div>`;
      return;
    }
    let saved = null;
    try { saved = localStorage.getItem("hamlet_pump_entry"); } catch (e) { /* storage blocked */ }
    await this._select(this._entries.some((e) => e.entry_id === saved) ? saved : this._entries[0].entry_id);
  }

  _renderTabs() {
    const tabs = this.shadowRoot.querySelector(".tabs");
    tabs.innerHTML = this._entries.length < 2 ? "" : this._entries.map((e) =>
      `<button role="tab" data-tab="${esc(e.entry_id)}" aria-selected="${e.entry_id === this._entryId}">${esc(e.name)}</button>`).join("");
  }

  async _select(id) {
    this._unsubscribe();
    this._entryId = id;
    try { localStorage.setItem("hamlet_pump_entry", id); } catch (e) { /* ignore */ }
    this._renderTabs();
    Object.assign(this, { _snap: null, _draft: null, _dirty: false, _built: false, _shown: null });
    await this._loadState();
    this._subscribe();
  }

  async _loadState() {
    if (!this._entryId) return;
    try {
      const s = await this._hass.callWS({ type: `${DOMAIN}/state`, entry_id: this._entryId });
      this._history = s.history; this._days = s.days || []; this._sensors = s.sensors || {}; this._isAdmin = s.is_admin;
      this._apply(s);
      this._renderChart(); this._renderDays(); this._renderRaw();
    } catch (e) {
      this._main.innerHTML = `<div class="card span2 loading">${esc(e.message)}</div>`;
    }
  }
  async _subscribe() {
    if (!this._entryId || this._unsub) return;
    try {
      this._unsub = await this._hass.connection.subscribeMessage((snap) => this._apply(snap), { type: `${DOMAIN}/subscribe`, entry_id: this._entryId });
    } catch (e) { console.warn("hamlet_pump subscribe failed", e); }
  }
  _unsubscribe() { if (this._unsub) { this._unsub(); this._unsub = null; } }

  _setHTML(el, html) { if (!el || el._html === html) return; el._html = html; el.innerHTML = html; }
  _editing() { const a = this.shadowRoot.activeElement; return !!(a && a.closest && a.closest("#client, #admin")); }
  $(id) { return this.shadowRoot.getElementById(id); }

  _apply(snap) {
    if (snap.entry_id !== this._entryId) return;
    this._snap = snap;
    const json = JSON.stringify(snap.settings);
    const redraw = json !== this._shown && !this._dirty && !this._editing();
    if (redraw) this._draft = JSON.parse(json);
    if (!this._built) this._layout();
    this.shadowRoot.querySelector(".toolbar .title").textContent = this._entries.length > 1 ? "Pumps" : snap.name;
    this._renderHero(); this._renderNow(); this._renderEvents();
    if (redraw || !this._shownZones) { this._shown = json; this._renderClient(); this._renderAdmin(); this._shownZones = true; }
  }

  _layout() {
    const t = this._snap.type;
    this._main.innerHTML = `
      <section class="card hero" id="hero"></section>
      <section class="card" id="now"></section>
      <section class="card span2" id="chart"></section>
      <section class="card" id="client"></section>
      <section class="card" id="events"></section>
      <section class="card span2" id="admin"></section>`;
    this._built = true;
    this._shownZones = false;
  }

  /* ------------------------------------------------------------- hero */
  _color(d, s) {
    if (!d) return "var(--muted)";
    if (s.fault || ["Fault", "VFD fault", "Offline"].includes(d.status)) return "var(--c-bad)";
    if (["Resting", "Tank low", "Rain skip", "Rain delay", "Waiting"].includes(d.status)) return "var(--c-warn)";
    if (this._snap.live?.running) return "var(--c-run)";
    if (d.status === "Off") return "var(--muted)";
    return "var(--c-water)";
  }

  _renderHero() {
    const s = this._snap; if (!s) return;
    const d = s.decision || {}; const L = s.live || {};
    const running = !!L.running;
    const color = this._color(d, s);
    let pic;
    if (s.type === "booster") pic = gaugeSvg(s, running);
    else if (s.type === "irrigation") pic = this._zonesHtml(s, running);
    else pic = tankSvg(s, running);
    const runFor = num(L.run_for_s);
    let alarm = "";
    if (s.fault) {
      alarm = `<div class="alarm"><ha-icon icon="mdi:alert-octagon"></ha-icon><div class="txt"><b>Pump locked out</b><br>${esc(s.fault)}</div>
        <button class="btn danger" data-act="reset">${this._confirmReset ? "Tap again" : "Reset"}</button></div>`;
    } else if (d.status === "Resting") {
      alarm = `<div class="alarm" style="--ac:var(--c-warn)"><ha-icon icon="mdi:timer-sand"></ha-icon><div class="txt">${esc(d.reason)}</div>
        <button class="btn" data-act="reset">Try now</button></div>`;
    } else if (L.cmd_error) {
      alarm = `<div class="alarm"><ha-icon icon="mdi:alert"></ha-icon><div class="txt">${esc(L.cmd_error)}</div></div>`;
    }
    const mode = s.mode;
    const mb = (m, icon, label) => `<button data-mode="${m}" aria-pressed="${mode === m}"><ha-icon icon="${icon}"></ha-icon>${label}</button>`;
    const runLabel = s.type === "irrigation" ? "Water" : "Run";
    const chips = mode === "run" && s.run_until
      ? `<div class="chips small muted">${s.type === "irrigation" && s.manual_zone !== null ? `Zone ${s.manual_zone + 1} · ` : ""}running until ${tstr(s.run_until)}</div>`
      : `<div class="chips">${[10, 30, 60, 120].map((m) => `<button class="chip" data-runmin="${m}" aria-pressed="${this._runMin === m}">${m < 60 ? m + " min" : m / 60 + " h"}</button>`).join("")}</div>`;
    this._setHTML(this.$("hero"), `
      <h2 style="width:100%;margin:0">${esc(s.name)}<span class="sub">${TYPE_LABEL[s.type] || ""}</span></h2>
      <div class="pic" style="${s.type === "irrigation" ? "width:100%" : ""}">${pic}</div>
      <span class="badge ${running ? "pulse" : ""}" style="--bc:${color}"><span class="dot"></span>${esc(d.status || "…")}${running && runFor !== null ? ` · ${fmtMin(runFor)}` : ""}</span>
      <div class="reason">${s.fault || d.status === "Resting" ? "" : esc(d.reason || "")}</div>
      ${alarm}
      <div class="modes">${mb("auto", "mdi:auto-mode", "Auto")}${mb("run", s.type === "irrigation" ? "mdi:sprinkler-variant" : "mdi:timer-play-outline", runLabel)}${mb("on", "mdi:power", "On")}${mb("off", "mdi:power-off", "Off")}</div>
      ${chips}`);
  }

  _zonesHtml(s, running) {
    const L = s.live || {}; const d = s.decision || {};
    if (!s.zones.length) {
      return `<div class="zone ${running ? "on" : ""}">${sprinkler(running)}<span class="zn">Pump only (no valves mapped)</span><span class="small muted">${running ? "watering" : ""}</span></div>`;
    }
    return `<div class="zones">${s.zones.map((z, i) => {
      const open = !!(L.zones || [])[i]; const active = d.on && d.zone === i;
      return `<div class="zone ${open ? "on" : ""}">${sprinkler(open)}<span class="zn">${i + 1}. ${esc(z)}</span>
        <span class="small muted">${active ? "watering" : open ? "open" : ""}</span>
        <button class="chip" data-zone="${i}">${active && s.mode === "run" ? "Stop" : `${this._runMin} min`}</button></div>`;
    }).join("")}</div>`;
  }

  /* ------------------------------------------------------------- right now */
  _renderNow() {
    const s = this._snap; const L = s.live || {}; const f = s.features || {}; const T = s.today || {};
    const tile = (icon, ic, lab, v, note, extra = "") => `<div class="tile"><div class="lab" style="--ic:${ic}"><ha-icon icon="${icon}"></ha-icon>${lab}</div><div class="v">${v}</div>${extra}<div class="note">${note || "&nbsp;"}</div></div>`;
    const tiles = [];
    const running = !!L.running;
    tiles.push(tile("mdi:pump", running ? "var(--c-run)" : "var(--muted)", "Pump", running ? "Running" : f.switch && L.is_on && s.type === "booster" ? "Standby" : "Stopped",
      running && L.run_for_s !== null ? `for ${fmtMin(L.run_for_s)}` : `${L.starts_hour ?? 0} starts this hour`));
    if (f.level) tiles.push(tile("mdi:storage-tank", "var(--c-water)", s.type === "borehole" ? "Tank" : "Supply tank", `${num(L.level)?.toFixed(0) ?? "–"}%`,
      s.settings.tank_litres && s.type === "borehole" && num(L.level) !== null ? `≈ ${fmtL(s.settings.tank_litres * L.level / 100)}` : "", `<div class="bar"><i style="width:${Math.max(0, Math.min(100, num(L.level) || 0))}%"></i></div>`));
    else if (f.tank_full || f.tank_low) tiles.push(tile("mdi:storage-tank", "var(--c-water)", "Tank", L.tank_full ? "Full" : L.tank_low ? "Low" : "OK", [f.tank_full ? `full float ${L.tank_full ? "up" : "down"}` : "", f.tank_low ? `low float ${L.tank_low ? "on" : "off"}` : ""].filter(Boolean).join(" · ")));
    if (f.pressure) tiles.push(tile("mdi:gauge", "var(--c-water)", "Pressure", `${num(L.pressure)?.toFixed(1) ?? "–"} bar`, ""));
    tiles.push(tile("mdi:waves-arrow-right", "var(--c-water)", "Flow", `${num(L.flow_est)?.toFixed(0) ?? "–"} L/min`, f.flow ? "flow sensor" : "estimated"));
    tiles.push(tile("mdi:flash", "var(--c-power)", "Power", fmtW(L.power_est), f.power ? "measured" : "estimated from rating"));
    if (f.amps) tiles.push(tile("mdi:current-ac", "var(--c-power)", "Current", `${num(L.amps)?.toFixed(1) ?? "–"} A`, ""));
    if (f.hz) tiles.push(tile("mdi:sine-wave", "var(--muted)", "Speed", `${num(L.hz)?.toFixed(0) ?? "–"} Hz`, num(L.hz) ? `${Math.round(num(L.hz) / 50 * 100)}% speed` : ""));
    if (f.vfd_fault) tiles.push(tile("mdi:alert-circle-outline", L.vfd_fault ? "var(--c-bad)" : "var(--c-ok)", "VFD", L.vfd_fault ? "Fault" : "OK", L.vfd_fault || ""));
    if (f.rain) tiles.push(tile("mdi:weather-rainy", "var(--c-water)", "Rain sensor", L.rain ? "Wet" : "Dry", ""));
    const next = s.next && (s.type !== "booster") ? `<div class="small muted" style="margin-top:10px">Next ${s.type === "irrigation" ? "program" : "timer"}: ${dstr(s.next)}</div>` : "";
    this._setHTML(this.$("now"), `<h2>Right now<span class="sub">${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></h2>
      <div class="tiles">${tiles.join("")}</div>
      <div class="totals">
        <div>Water today<div class="v">${fmtL(T.litres)}</div>${f.water === "estimate" ? "estimated" : f.water === "meter" ? "water meter" : "flow sensor"}</div>
        <div>Run time<div class="v">${fmtMin(T.run_s)}</div></div>
        <div>Starts<div class="v">${Math.round(T.starts || 0)}</div></div>
        <div>Energy<div class="v">${(num(T.kwh) || 0).toFixed(1)} kWh</div></div>
      </div>${next}`);
  }

  /* ------------------------------------------------------------- chart */
  _renderChart() {
    const s = this._snap, el = this.$("chart"); if (!s || !el) return;
    const rows = (this._history || {})[this._day] || [];
    const usePressure = s.type === "booster" && s.features.pressure;
    const useLevel = s.features.level;
    const lineName = usePressure ? "Pressure" : useLevel ? (s.type === "borehole" ? "Tank level" : "Supply tank") : null;
    const W = 1000, H = 230, padL = 40, padR = 40, padT = 10, padB = 24;
    const x = (m) => padL + (m / 1440) * (W - padL - padR);
    const pmax = usePressure ? Math.max(6, ...rows.map((r) => r[3] || 0)) : 100;
    const y = (v) => padT + (1 - v / pmax) * (H - padT - padB);
    const lmax = Math.max(10, ...rows.map((r) => r[5] || 0));
    const yl = (v) => H - padB - (v / lmax) * (H - padT - padB) * 0.45;
    let svg = `<g class="grid">${[0, 0.25, 0.5, 0.75, 1].map((f) => `<line x1="${padL}" x2="${W - padR}" y1="${y(pmax * f)}" y2="${y(pmax * f)}"/>`).join("")}</g>`;
    svg += `<g class="axis">${[0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => `<text x="${x(h * 60)}" y="${H - 6}" text-anchor="middle">${String(h).padStart(2, "0")}:00</text>`).join("")}
      ${lineName ? [0, 0.5, 1].map((f) => `<text x="${padL - 6}" y="${y(pmax * f) + 4}" text-anchor="end">${usePressure ? (pmax * f).toFixed(0) : Math.round(pmax * f) + "%"}</text>`).join("") : ""}
      <text x="${W - padR + 6}" y="${H - padB - (H - padT - padB) * 0.45 + 4}">${Math.round(lmax)} L</text></g>`;
    const bw = (W - padL - padR) / 288;
    svg += rows.filter((r) => r[1] > 0).map((r) => `<rect x="${x(r[0])}" y="${padT}" width="${bw + 0.5}" height="${H - padT - padB}" fill="var(--c-run)" opacity="${(0.1 + r[1] * 0.12).toFixed(2)}"/>`).join("");
    svg += rows.filter((r) => r[5] > 0).map((r) => `<rect x="${x(r[0]) + 0.5}" y="${yl(r[5])}" width="${Math.max(bw - 1, 1)}" height="${H - padB - yl(r[5])}" fill="var(--c-water2)" rx="1"/>`).join("");
    if (lineName) {
      const idx = usePressure ? 3 : 2;
      let path = "", pen = false;
      rows.forEach((r) => { if (r[idx] === null || r[idx] === undefined) { pen = false; return; } path += `${pen ? "L" : "M"}${x(r[0] + 2.5).toFixed(1)} ${y(r[idx]).toFixed(1)} `; pen = true; });
      svg += `<path d="${path}" fill="none" stroke="var(--c-water)" stroke-width="2.2" stroke-linejoin="round"/>`;
    }
    if (this._day === "today") { const n = new Date(); svg += `<line x1="${x(n.getHours() * 60 + n.getMinutes())}" x2="${x(n.getHours() * 60 + n.getMinutes())}" y1="${padT}" y2="${H - padB}" stroke="var(--muted)" stroke-dasharray="3 3"/>`; }
    svg += `<line id="cursor" x1="0" x2="0" y1="${padT}" y2="${H - padB}" stroke="var(--muted)" stroke-dasharray="2 3" style="display:none"/>`;
    const legend = `<span class="key"><i style="background:var(--c-run);opacity:.4"></i>Pump running</span>${lineName ? `<span class="key"><i style="background:var(--c-water)"></i>${lineName}</span>` : ""}<span class="key"><i style="background:var(--c-water2)"></i>Water (L per 5 min)</span>`;
    el.innerHTML = `<h2>Today's pumping<span class="sub"><span class="seg"><button data-day="today" aria-pressed="${this._day === "today"}">Today</button><button data-day="yesterday" aria-pressed="${this._day === "yesterday"}">Yesterday</button></span></span></h2>
      <div class="legendrow">${legend}</div>
      ${rows.length ? `<div class="chartwrap"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${svg}</svg><div class="tip"></div></div>` : `<div class="empty">No data yet – the chart fills in every 5 minutes.</div>`}
      <h3>Water per day</h3><div class="days14" id="days14"></div>`;
    this._chartRows = rows; this._chartX = { padL, padR, W };
    const wrap = el.querySelector(".chartwrap");
    if (wrap) {
      const svgEl = wrap.querySelector("svg"), tip = wrap.querySelector(".tip"), cur = wrap.querySelector("#cursor");
      const move = (ev) => {
        const b = svgEl.getBoundingClientRect(); const px = ((ev.clientX - b.left) / b.width) * W;
        const m = ((px - padL) / (W - padL - padR)) * 1440;
        let best = null; rows.forEach((r) => { if (best === null || Math.abs(r[0] - m) < Math.abs(best[0] - m)) best = r; });
        if (!best || Math.abs(best[0] - m) > 30) { tip.style.display = "none"; cur.style.display = "none"; return; }
        cur.setAttribute("x1", x(best[0] + 2.5)); cur.setAttribute("x2", x(best[0] + 2.5)); cur.style.display = "";
        tip.innerHTML = `<b>${hhmm(best[0])}</b>
          <div class="row"><span>Running</span><span>${Math.round(best[1] * 100)}%</span></div>
          ${best[2] !== null ? `<div class="row"><span>Tank</span><span>${best[2]}%</span></div>` : ""}
          ${best[3] !== null ? `<div class="row"><span>Pressure</span><span>${best[3]} bar</span></div>` : ""}
          <div class="row"><span>Power</span><span>${fmtW(best[4])}</span></div><div class="row"><span>Water</span><span>${fmtL(best[5])}</span></div>`;
        tip.style.display = "block";
        const left = ev.clientX - b.left; tip.style.left = `${Math.min(left + 12, b.width - tip.offsetWidth - 4)}px`; tip.style.top = "8px";
      };
      svgEl.addEventListener("pointermove", move);
      svgEl.addEventListener("pointerleave", () => { tip.style.display = "none"; cur.style.display = "none"; });
    }
    this._renderDays();
  }

  _renderDays() {
    const el = this.$("days14"); if (!el) return;
    const days = this._days || [];
    const max = Math.max(1, ...days.map((d) => d.litres || 0));
    const W = 1000, H = 120, bw = W / Math.max(days.length, 1);
    const bars = days.map((d, i) => {
      const h = ((d.litres || 0) / max) * (H - 34);
      const lab = new Date(d.day + "T12:00").toLocaleDateString([], { weekday: "short" }).slice(0, 2);
      return `<g><title>${d.day}: ${fmtL(d.litres || 0)}, ${fmtMin(d.run_s || 0)} running, ${Math.round(d.starts || 0)} starts</title>
        <rect x="${i * bw + bw * 0.18}" y="${H - 18 - h}" width="${bw * 0.64}" height="${Math.max(h, 0.5)}" rx="3" fill="${i === days.length - 1 ? "var(--c-water)" : "var(--c-water2)"}"/>
        ${d.litres ? `<text class="lbl" x="${i * bw + bw / 2}" y="${H - 22 - h}" text-anchor="middle" style="font-size:11px">${fmtL(d.litres)}</text>` : ""}
        <text class="lbl" x="${i * bw + bw / 2}" y="${H - 4}" text-anchor="middle" style="font-size:11px">${lab}</text></g>`;
    }).join("");
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="font-size:11px">${bars}</svg>`;
  }

  /* ------------------------------------------------------------- events */
  _renderEvents() {
    const s = this._snap; const ev = s.events || [];
    const icon = { fault: ["mdi:alert-octagon", "var(--c-bad)"], trip: ["mdi:timer-sand", "var(--c-warn)"], leak: ["mdi:water-alert", "var(--c-warn)"],
      cycling: ["mdi:repeat", "var(--c-warn)"], supply: ["mdi:storage-tank-outline", "var(--c-warn)"], vfd: ["mdi:alert-circle", "var(--c-bad)"], reset: ["mdi:restart", "var(--c-ok)"] };
    this._setHTML(this.$("events"), `<h2>Alerts<span class="sub">last 10</span></h2>
      ${ev.length ? `<div class="events">${ev.map((e) => { const [i, c] = icon[e.kind] || ["mdi:information-outline", "var(--muted)"];
        return `<div class="ev" style="--ic:${c}"><ha-icon icon="${i}"></ha-icon><span>${esc(e.msg)}</span><span class="t">${dstr(e.t)}</span></div>`; }).join("")}</div>`
        : `<div class="empty" style="padding:20px 0">No alerts – all good.</div>`}
      ${s.settings.notify_service ? `<div class="small muted" style="margin-top:8px">Alerts are also sent to ${esc(s.settings.notify_service)}</div>` : ""}`);
  }

  /* ------------------------------------------------------------- client settings */
  _field(key, label, unit, hint = "", attrs = "") {
    const v = this._draft[key];
    if (typeof v === "boolean") return `<div class="field"><label>${label}${hint ? `<span class="hint">${hint}</span>` : ""}</label><span class="ctl"><span class="switch"><input type="checkbox" data-k="${key}" ${v ? "checked" : ""} aria-label="${label}"><span></span></span></span></div>`;
    return `<div class="field"><label>${label}${hint ? `<span class="hint">${hint}</span>` : ""}</label><span class="ctl"><input type="number" data-k="${key}" value="${esc(v)}" ${attrs} aria-label="${label}">${unit}</span></div>`;
  }
  _actions(scope) {
    return `<div class="actions"><span class="msg" id="msg-${scope}"></span><button class="btn" data-act="cancel">Undo</button><button class="btn primary" data-save="${scope}">Save</button></div>`;
  }

  _renderClient() {
    const s = this._snap, D = this._draft, f = s.features;
    let html = "";
    if (s.type === "borehole") {
      html = `<h2>Tank filling</h2><div class="form">`;
      if (f.level) html += this._field("start_level", "Start filling below", "%", "", 'min="0" max="99"') + this._field("stop_level", "Stop at", "%", "", 'min="1" max="100"');
      else if (f.tank_full || f.tank_low) html += `<div class="small muted" style="padding:8px 0">Filling follows the float switches in the tank.</div>`;
      html += this._field("hours_enabled", "Only pump during set hours", "", "e.g. to keep the neighbours happy or follow municipal rules");
      if (D.hours_enabled) html += `<div class="field"><label>Pumping hours</label><span class="ctl"><input type="time" data-k="hours_start" value="${esc(D.hours_start)}"> to <input type="time" data-k="hours_end" value="${esc(D.hours_end)}"></span></div>`;
      html += `</div>`;
      if (!f.level && !f.tank_full && !f.tank_low) html += `<h3>Pump times</h3><div class="small muted">No level sensor or float – the pump runs during these times.</div>${this._schedHtml("schedules", false)}`;
      html += this._actions("client");
    } else if (s.type === "irrigation") {
      html = `<h2>Watering programs<span class="sub">${s.rain_delay_until ? `paused until ${dstr(s.rain_delay_until)}` : ""}</span></h2>
        ${this._schedHtml("programs", true)}
        <div class="form">${this._field("rain_skip", "Skip when the rain sensor is wet", "", f.rain ? "" : "No rain sensor mapped")}</div>
        <div class="field"><label>Rain delay<span class="hint">Pause all programs</span></label><span class="ctl">${[1, 2, 3, 7].map((d) => `<button class="chip" data-rain="${d}">${d} day${d > 1 ? "s" : ""}</button>`).join("")}${s.rain_delay_until ? `<button class="chip" data-rain="0">Clear</button>` : ""}</span></div>
        ${this._actions("client")}`;
    } else {
      html = `<h2>How it works</h2><div class="small" style="line-height:1.5">
        The ${f.hz ? "VFD" : "pressure switch"} starts and stops the pump as taps open and close. This app ${f.switch ? "keeps the pump enabled and switches it off when something is wrong" : "watches the pump and warns you when something is wrong (no switch mapped, monitor only)"}:
        <ul style="margin:8px 0 0;padding-left:20px;color:var(--muted)">
          ${num(s.settings.dry_run_w) || num(s.settings.dry_run_a) ? "<li>Dry-running</li>" : ""}
          ${num(s.settings.low_pressure_bar) ? `<li>No pressure while running (below ${s.settings.low_pressure_bar} bar)</li>` : ""}
          ${num(s.settings.max_continuous_minutes) ? `<li>Running non-stop for ${s.settings.max_continuous_minutes} min – a leak or tap left open</li>` : ""}
          ${num(s.settings.max_starts_per_hour) ? `<li>More than ${s.settings.max_starts_per_hour} starts an hour – pressure vessel needs air</li>` : ""}
          ${f.level || f.tank_low ? `<li>Supply tank running low</li>` : ""}
          ${f.vfd_fault ? "<li>VFD faults</li>" : ""}
        </ul></div>`;
    }
    this._setHTML(this.$("client"), html);
  }

  _schedHtml(key, program) {
    const s = this._snap; const list = this._draft[key] || [];
    const zones = s.zones.length ? s.zones : ["Pump"];
    const rows = list.map((p, i) => {
      const days = DAYS.map((d, j) => `<button data-day-toggle="${key}:${i}:${j}" aria-pressed="${(p.days || []).includes(j)}">${d}</button>`).join("");
      const total = program ? (p.minutes || []).slice(0, zones.length).reduce((a, b) => a + (Number(b) || 0), 0) : 0;
      return `<div class="sched">
        <span class="switch"><input type="checkbox" data-list="${key}:${i}:enabled" ${p.enabled ? "checked" : ""} aria-label="Enabled"><span></span></span>
        <div class="times">${program ? `<input type="text" style="width:120px" data-list="${key}:${i}:name" value="${esc(p.name)}" aria-label="Name">` : ""}
          <input type="time" data-list="${key}:${i}:start" value="${esc(p.start)}" aria-label="Start">
          ${program ? `<span class="small muted">${Math.round(total)} min total</span>` : `to <input type="time" data-list="${key}:${i}:end" value="${esc(p.end)}" aria-label="End">`}
          <button class="iconbtn del" data-del="${key}:${i}" aria-label="Remove"><ha-icon icon="mdi:delete-outline"></ha-icon></button></div>
        <div class="days">${days}</div>
        ${program ? `<div class="zmins">${zones.map((z, j) => `<label><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${j + 1}. ${esc(z)}</span><span><input type="number" min="0" max="240" data-list="${key}:${i}:minutes:${j}" value="${esc((p.minutes || [])[j] ?? 0)}"> min</span></label>`).join("")}</div>` : ""}
      </div>`;
    }).join("");
    return `<div>${rows || `<div class="small muted" style="padding:8px 0">None yet.</div>`}</div>
      <div class="actions" style="justify-content:flex-start"><button class="btn" data-add="${key}">+ Add ${program ? "program" : "time"}</button></div>`;
  }

  /* ------------------------------------------------------------- installer */
  _renderAdmin() {
    const s = this._snap, el = this.$("admin");
    if (!this._isAdmin) { el.hidden = true; return; }
    el.hidden = false;
    const t = s.type, f = s.features, L = s.live || {};
    const learnable = f.power || f.amps;
    let left = `<h3>Dry-run &amp; overload</h3><div class="form">`;
    if (f.power) left += this._field("dry_run_w", "Dry-run below", "W", "0 = off") + this._field("overload_w", "Overload above", "W", "0 = off");
    if (f.amps) left += this._field("dry_run_a", "Dry-run below", "A", "0 = off", 'step="0.1"') + this._field("overload_a", "Overload above", "A", "0 = off", 'step="0.1"');
    if (!learnable) left += `<div class="small muted" style="padding:8px 0">Map a power or current sensor (Configure) to get dry-run and overload protection.</div>`;
    left += this._field("dry_run_seconds", "Dry-run must last", "s") + this._field("start_grace_seconds", "Ignore after start", "s", "Pump needs a moment to prime")
      + this._field("rest_minutes", "Wait before trying again", "min") + this._field("max_retries", "Lock out after", "tries", "Then Reset is needed");
    left += `</div>`;
    if (learnable) left += `<div class="actions" style="justify-content:flex-start"><button class="btn" data-act="learn" ${L.running ? "" : "disabled"}>Learn from this run</button>
      <span class="small muted">${L.running ? `Now: ${f.power ? fmtW(L.power) : ""}${f.power && f.amps ? " · " : ""}${f.amps ? `${num(L.amps)?.toFixed(1)} A` : ""} → sets dry-run 60%, overload 140%` : "Start the pump and let it run normally, then tap Learn"}</span></div>`;

    let right = "";
    if (t === "borehole") {
      right += `<h3>Borehole</h3><div class="form">` + this._field("no_rise_minutes", "Tank must rise 1% within", "min", "Else: dry borehole / leak – 0 = off")
        + this._field("max_run_minutes", "Rest the borehole after", "min", "Continuous pumping – 0 = off") + this._field("borehole_rest_minutes", "Rest for", "min")
        + this._field("tank_litres", "Tank size", "L") + (f.tank_full && !f.tank_low && !f.level ? this._field("float_restart_minutes", "Refill after full float drops", "min") : "") + `</div>`;
    }
    if (t === "booster") {
      right += `<h3>Pressure pump</h3><div class="form">` + (f.pressure ? this._field("low_pressure_bar", "No-pressure trip below", "bar", "Running but no pressure – 0 = off", 'step="0.1"') + this._field("low_pressure_seconds", "No-pressure must last", "s") : "")
        + this._field("max_continuous_minutes", "Leak warning after running", "min", "Non-stop – 0 = off")
        + `<div class="field"><label>On a leak</label><span class="ctl"><select data-k="leak_action"><option value="alert" ${this._draft.leak_action === "alert" ? "selected" : ""}>Warn only</option><option value="stop" ${this._draft.leak_action === "stop" ? "selected" : ""}>Stop the pump</option></select></span></div>`
        + this._field("max_starts_per_hour", "Short-cycling warning above", "starts/h", "0 = off") + `</div>`;
    }
    if (t === "irrigation") right += `<h3>Irrigation</h3><div class="form">` + this._field("valve_lead_seconds", "Open valve before pump", "s") + `</div>`;
    if (t !== "borehole" && (f.level || f.tank_low)) {
      right += `<h3>Supply tank</h3><div class="form">` + (f.level ? this._field("supply_low_level", "Stop the pump below", "%") + this._field("supply_restart_level", "Start again above", "%") : `<div class="small muted" style="padding:8px 0">Stops while the low float is on.</div>`) + `</div>`;
    }
    right += `<h3>General</h3><div class="form">` + (f.power ? "" : this._field("rated_w", "Pump rating", "W", "Energy estimate – no meter"))
      + (f.flow || f.meter ? "" : this._field("flow_lpm", "Pump flow at full speed", "L/min", "Water estimate – no flow sensor or meter"))
      + this._field("min_switch_seconds", "Minimum time before a restart", "s", "Protects relay and motor")
      + `<div class="field"><label>Send alerts to<span class="hint">e.g. notify.mobile_app_wynand – blank = HA notifications only</span></label><span class="ctl"><input type="text" data-k="notify_service" value="${esc(this._draft.notify_service)}" placeholder="notify.mobile_app_…"></span></div></div>`;

    el.innerHTML = `<h2>Installer settings<span class="sub">admin only</span></h2>
      <div class="cols2"><div>${left}</div><div>${right}</div></div>
      ${this._actions("admin")}
      <details style="margin-top:12px"><summary>Live sensor check</summary><div class="rawgrid" id="raw"></div></details>
      <div class="small muted" style="margin-top:8px">To change which entities are used: Settings → Devices &amp; services → Hamlet Pump → Configure.</div>`;
    this._renderRaw();
  }

  _renderRaw() {
    const el = this.$("raw"); if (!el) return;
    el.innerHTML = Object.entries(this._sensors || {}).map(([k, v]) => `<span class="muted">${esc(k.replace(/_/g, " "))}</span><span>${esc(v)}</span>`).join("") || `<span class="muted">Nothing mapped</span><span></span>`;
  }

  /* ------------------------------------------------------------- events */
  async _call(msg) {
    try {
      const r = await this._hass.callWS({ entry_id: this._entryId, ...msg });
      if (r && r.entry_id) this._apply(r);
      return r;
    } catch (e) {
      this._toast(e.message || String(e));
      return null;
    }
  }
  _toast(text) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message: text }, bubbles: true, composed: true }));
  }

  async _click(ev) {
    const b = ev.target.closest("button"); if (!b) return;
    const d = b.dataset;
    if (d.tab) return this._select(d.tab);
    if (d.day) { this._day = d.day; return this._renderChart(); }
    if (d.runmin) { this._runMin = Number(d.runmin); this._renderHero(); return; }
    if (d.mode) {
      const s = this._snap;
      if (d.mode === "run") return this._call({ type: `${DOMAIN}/set_mode`, mode: "run", minutes: this._runMin, ...(s.zones.length ? { zone: 0 } : {}) });
      return this._call({ type: `${DOMAIN}/set_mode`, mode: d.mode });
    }
    if (d.zone !== undefined) {
      const s = this._snap, z = Number(d.zone);
      if (s.mode === "run" && s.manual_zone === z) return this._call({ type: `${DOMAIN}/set_mode`, mode: "auto" });
      return this._call({ type: `${DOMAIN}/set_mode`, mode: "run", minutes: this._runMin, zone: z });
    }
    if (d.rain !== undefined) return this._call({ type: `${DOMAIN}/rain_delay`, days: Number(d.rain) });
    if (d.act === "reset") {
      if (this._snap.fault && !this._confirmReset) { this._confirmReset = true; this._renderHero(); setTimeout(() => { this._confirmReset = false; this._snap && this._renderHero(); }, 4000); return; }
      this._confirmReset = false;
      return this._call({ type: `${DOMAIN}/reset` });
    }
    if (d.act === "learn") {
      const r = await this._call({ type: `${DOMAIN}/learn` });
      if (r && r.learned) { this._dirty = false; this._shown = null; this._apply(r); this._msg("admin", `Learned: ${Object.entries(r.learned).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(", ")}`, true); }
      return;
    }
    if (d.act === "cancel") { this._dirty = false; this._shown = null; return this._apply(this._snap); }
    if (d.save) return this._save(d.save);
    if (d.add) {
      const list = this._draft[d.add] = this._draft[d.add] || [];
      list.push(d.add === "programs" ? { enabled: true, name: `Program ${list.length + 1}`, days: [0, 2, 4], start: "05:00", minutes: (this._snap.zones.length ? this._snap.zones : [0]).map(() => 10) }
        : { enabled: true, days: [0, 1, 2, 3, 4, 5, 6], start: "08:00", end: "10:00" });
      this._dirty = true; return this._renderClient();
    }
    if (d.del) { const [k, i] = d.del.split(":"); this._draft[k].splice(Number(i), 1); this._dirty = true; return this._renderClient(); }
    if (d.dayToggle) {
      const [k, i, j] = d.dayToggle.split(":"); const it = this._draft[k][Number(i)]; const day = Number(j);
      it.days = it.days.includes(day) ? it.days.filter((x) => x !== day) : [...it.days, day].sort();
      this._dirty = true; b.setAttribute("aria-pressed", it.days.includes(day)); return;
    }
  }

  _input(ev) {
    const t = ev.target;
    if (t.dataset.k) {
      const k = t.dataset.k;
      this._draft[k] = t.type === "checkbox" ? t.checked : t.type === "number" ? (t.value === "" ? "" : Number(t.value)) : t.value;
      this._dirty = true;
      if (k === "hours_enabled" && ev.type === "change") this._renderClient();
    } else if (t.dataset.list) {
      const [k, i, field, j] = t.dataset.list.split(":");
      const it = this._draft[k][Number(i)];
      if (field === "minutes") { it.minutes = it.minutes || []; it.minutes[Number(j)] = Number(t.value) || 0; }
      else it[field] = t.type === "checkbox" ? t.checked : t.value;
      this._dirty = true;
    }
  }

  _msg(scope, text, ok) { const m = this.$(`msg-${scope}`); if (m) { m.textContent = text; m.className = `msg ${ok ? "ok" : "err"}`; } }

  async _save(scope) {
    const USER = ["start_level", "stop_level", "hours_enabled", "hours_start", "hours_end", "schedules", "programs", "rain_skip", "run_minutes"];
    const keys = scope === "client" ? USER : Object.keys(this._draft).filter((k) => !USER.includes(k));
    const changed = {};
    keys.forEach((k) => { if (JSON.stringify(this._draft[k]) !== JSON.stringify(this._snap.settings[k])) changed[k] = this._draft[k]; });
    if (!Object.keys(changed).length) return this._msg(scope, "Nothing changed", true);
    try {
      const r = await this._hass.callWS({ type: `${DOMAIN}/save_settings`, entry_id: this._entryId, settings: changed });
      this._dirty = false; this._shown = null; this._apply(r);
      this._msg(scope, "Saved", true);
    } catch (e) {
      this._msg(scope, e.message || String(e), false);
    }
  }
}

if (!customElements.get("hamlet-pump-panel")) customElements.define("hamlet-pump-panel", HamletPumpPanel);
