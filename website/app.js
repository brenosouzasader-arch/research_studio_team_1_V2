/* Roofscapes (Re)Powered website. Reads data/site_data.json (written by
   pipeline/step10_publish_report/export_site_data.py) and draws every section.
   No modelling happens here except the guest-discount slider, which uses the same
   formula as step 09 (owner_total_at_discount). Charts are plain SVG. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const $ = (id) => document.getElementById(id);
  const fmt = (v, d = 0) => (v == null || Number.isNaN(v) ? "–" : Number(v).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const pct = (v) => fmt(v * 100) + "%";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function el(tag, attrs = {}, parent) {
    const svg = ["svg", "g", "line", "rect", "path", "text", "circle", "polyline"].includes(tag);
    const e = svg ? document.createElementNS(NS, tag) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "text") e.textContent = v;
      else if (k === "style") e.setAttribute("style", v);
      else e.setAttribute(k, v);
    }
    if (parent) parent.appendChild(e);
    return e;
  }

  function chip(f) {
    const c = el("span", { class: "chip", "data-kind": f.kind, title: f.note || "" });
    c.textContent = f.kind + " · " + f.src;
    return c;
  }

  // ---- tooltip -------------------------------------------------------------
  const tip = $("tip");
  function showTip(evt, title, rows) {
    tip.replaceChildren();
    el("div", { class: "t", text: title }, tip);
    for (const r of rows) {
      const row = el("div", { class: "r" }, tip);
      if (r.color) el("i", { style: "background:" + r.color }, row);
      el("b", { text: r.value }, row);
      el("span", { text: r.label }, row);
    }
    tip.hidden = false;
    const x = Math.min(evt.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const y = Math.min(evt.clientY + 14, window.innerHeight - tip.offsetHeight - 8);
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  const hideTip = () => { tip.hidden = true; };

  // ---- chart helpers ---------------------------------------------------------
  function frame(host, w, h, m) {
    host.replaceChildren();
    const svg = el("svg", { class: "chart", viewBox: `0 0 ${w} ${h}`, role: "img" }, host);
    return { svg, w, h, m, iw: w - m.l - m.r, ih: h - m.t - m.b };
  }
  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const s of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (s * p >= v) return s * p;
    return 10 * p;
  }
  function yAxis(f, max, ticks, fmtTick, label) {
    // pick a tick count that gives round steps (e.g. 15 -> 3 ticks of 5)
    const round = (x) => { const p = Math.pow(10, Math.floor(Math.log10(x))); return [1, 2, 2.5, 5, 10].some((m) => Math.abs(x / p - m) < 1e-9); };
    ticks = [ticks, 5, 4, 3, 6, 2].find((t) => round(max / t)) || ticks;
    const g = el("g", { class: "grid" }, f.svg);
    for (let i = 0; i <= ticks; i++) {
      const v = (max / ticks) * i;
      const y = f.m.t + f.ih - (v / max) * f.ih;
      el("line", { x1: f.m.l, x2: f.m.l + f.iw, y1: y, y2: y }, g);
      el("text", { x: f.m.l - 6, y: y + 4, "text-anchor": "end", text: fmtTick(v) }, f.svg);
    }
    if (label) el("text", { x: f.m.l, y: f.m.t - 10, text: label }, f.svg);
  }
  function hourAxis(f, n) {
    const step = n > 24 ? 6 : 3;
    for (let h = 0; h <= n; h += step) {
      const x = f.m.l + (h / n) * f.iw;
      el("text", { x, y: f.h - 8, "text-anchor": "middle", text: String(h % 24).padStart(2, "0") + ":00" }, f.svg);
    }
  }
  function linePath(vals, f, max, n) {
    return vals.map((v, i) => `${i ? "L" : "M"}${(f.m.l + ((i + 0.5) / n) * f.iw).toFixed(1)},${(f.m.t + f.ih - (v / max) * f.ih).toFixed(1)}`).join("");
  }
  function legend(host, items) {
    host.replaceChildren();
    for (const it of items) {
      const s = el("span", {}, host);
      el("i", { class: it.line ? "line" : "", style: "background:" + it.color }, s);
      s.appendChild(document.createTextNode(it.label));
    }
  }
  // crosshair hover for hourly line/area charts
  function crosshair(f, n, title, rowsAt) {
    const hair = el("line", { y1: f.m.t, y2: f.m.t + f.ih, stroke: css("--ink-3"), "stroke-width": 1, opacity: 0 }, f.svg);
    const hit = el("rect", { x: f.m.l, y: f.m.t, width: f.iw, height: f.ih, fill: "transparent" }, f.svg);
    const move = (evt) => {
      const r = f.svg.getBoundingClientRect();
      const x = ((evt.clientX - r.left) / r.width) * f.w;
      const i = Math.max(0, Math.min(n - 1, Math.floor(((x - f.m.l) / f.iw) * n)));
      const cx = f.m.l + ((i + 0.5) / n) * f.iw;
      hair.setAttribute("x1", cx); hair.setAttribute("x2", cx); hair.setAttribute("opacity", 0.6);
      showTip(evt, title(i), rowsAt(i));
    };
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerleave", () => { hideTip(); hair.setAttribute("opacity", 0); });
  }

  // ---- sections ---------------------------------------------------------------
  function overview(D) {
    const F = D.facts;
    if (D.meta.demo) { $("demo-banner").hidden = false; $("demo-note").textContent = D.meta.note; }
    const stats = [
      ["Solar a year", F.solar_kwh, fmt(F.solar_kwh.v), "kWh"],
      ["Used by the host alone", F.host_self_share, pct(F.host_self_share.v), ""],
      ["Used with neighbours", F.shared_used_share, pct(F.shared_used_share.v), ""],
      ["Battery the agent picks", F.battery_chosen_kwh, F.battery_chosen_kwh.v > 0 ? fmt(F.battery_chosen_kwh.v) : "None", F.battery_chosen_kwh.v > 0 ? "kWh" : ""],
    ];
    const host = $("hero-stats");
    for (const [label, f, value, unit] of stats) {
      const s = el("div", { class: "stat" }, host);
      el("span", { class: "label", text: label }, s);
      const v = el("span", { class: "value", text: value }, s);
      if (unit) el("small", { text: unit }, v);
      s.appendChild(chip(f));
    }
  }

  function roof(D) {
    const F = D.facts;
    const addr = D.roof.address || D.meta.address, usable = D.roof.usable_m2 != null ? D.roof.usable_m2 : F.usable_m2.v;
    $("roof-lede").textContent = `${addr}: ${fmt(usable)} m² of usable roof, read from ICGC LiDAR, with the sun from a PVGIS typical year. Pick how many panels to install: fill the whole roof, or only neat blocks of the best panels, as real installers do.` +
      (D.roof.separate ? ` This section shows a real roof; the sections below still use the demo roof (${D.meta.address}) until this one has been run through steps 04-09.` : "");
    const V = D.roof.variants && D.roof.variants.length ? D.roof.variants : [{
      option: "max", name: "Fill the roof", panel_wp: 420, rule: "every panel that fits and loses at most 40% of its sun to shade",
      panels: F.panels.v, kwp: F.kwp.v, yearly_kwh: F.solar_kwh.v, kwh_per_kwp: F.kwh_per_kwp.v,
      mean_shade_loss: D.roof.mean_shade_loss, monthly_kwh: D.roof.monthly_kwh,
      panel_list: D.roof.panels.map((p) => ({ x: p.x, y: p.y, k: p.kwh })) }];
    const chosen = D.roof.chosen || { panel_wp: 420, option: "max" };
    const opts = [...new Map(V.map((v) => [v.option, v.name])).entries()];
    const wps = [...new Set(V.map((v) => v.panel_wp))].sort((a, b) => a - b);
    const state = { option: chosen.option, wp: chosen.panel_wp };
    const pick = () => V.find((v) => v.option === state.option && v.panel_wp === state.wp) || V[0];

    function segButtons(host, items, key) {
      host.replaceChildren();
      for (const [val, label] of items) {
        const b = el("button", { type: "button", "aria-pressed": String(state[key] === val), text: label }, host);
        b.addEventListener("click", () => {
          state[key] = val;
          for (const x of host.children) x.setAttribute("aria-pressed", String(x === b));
          draw();
        });
      }
      host.hidden = items.length < 2;
    }
    segButtons($("layoutpick"), opts, "option");
    segButtons($("wppick"), wps.map((w) => [w, w + " W panels"]), "wp");

    // table of every layout
    const t = $("layout-table");
    t.replaceChildren();
    const hr = el("tr", {}, el("thead", {}, t));
    for (const h of ["Layout", "Panel", "Panels", "kWp", "kWh a year", "kWh per kWp"]) el("th", { text: h }, hr);
    const tb = el("tbody", {}, t);
    const rows = V.map((v) => {
      const r = el("tr", {}, tb);
      el("td", { text: v.name }, r);
      el("td", { text: v.panel_wp + " W" }, r);
      el("td", { class: "n", text: fmt(v.panels) }, r);
      el("td", { class: "n", text: fmt(v.kwp, 1) }, r);
      el("td", { class: "n", text: fmt(v.yearly_kwh) }, r);
      el("td", { class: "n", text: fmt(v.kwh_per_kwp) }, r);
      return [v, r];
    });
    const usedV = V.find((v) => v.option === chosen.option && v.panel_wp === chosen.panel_wp);
    $("layout-used").textContent = D.roof.separate ? `The sections below use the demo roof, not this one, until this roof goes through steps 04-10. Block sizes and the share of the best panel are our assumptions (step 03, options.py); 540 W panel size is a typical catalogue panel.` : `The rest of this page (spare power, neighbours, battery and money) uses ${usedV ? usedV.name.toLowerCase() + " with " + usedV.panel_wp + " W panels" : "the pipeline's layout"}. To use another layout there, rerun step 03 with --layout and --panel-wp, then steps 04-10. Block sizes and the share of the best panel are our assumptions (step 03, options.py); 540 W panel size is a typical catalogue panel.`;

    function draw() {
      const v = pick();
      if (!v) return;
      for (const [rv, r] of rows) r.classList.toggle("pick", rv === v);
      $("layout-rule").textContent = `${v.name}: ${v.rule}.` + (v.blocks ? ` ${v.blocks} blocks.` : "");
      const st = $("layout-stats");
      st.replaceChildren();
      for (const [label, val, unit] of [["Panels", fmt(v.panels), ""], ["Peak power", fmt(v.kwp, 1), "kWp"],
        ["Solar a year", fmt(v.yearly_kwh), "kWh"], ["Per kWp", fmt(v.kwh_per_kwp), "kWh/kWp"]]) {
        const s = el("div", { class: "stat" }, st);
        el("span", { class: "label", text: label }, s);
        const vv = el("span", { class: "value", text: val }, s);
        if (unit) el("small", { text: unit }, vv);
        s.appendChild(chip({ kind: "modelled", src: "step 03", note: "ICGC LiDAR + PVGIS typical year" }));
      }
      // monthly bars
      // one y-axis for every layout, so switching layouts compares like with like
      const m = v.monthly_kwh || D.roof.monthly_kwh;
      const f = frame($("monthly"), 560, 240, { l: 48, r: 8, t: 22, b: 26 });
      const max = niceMax(Math.max(...V.flatMap((x) => x.monthly_kwh || m)));
      const full = (V.find((x) => x.option === "max" && x.panel_wp === v.panel_wp) || {}).monthly_kwh;
      yAxis(f, max, 4, (x) => fmt(x), "kWh");
      const bw = f.iw / 12;
      m.forEach((val, i) => {
        const h = (val / max) * f.ih;
        const x = f.m.l + i * bw + 3;
        if (full && v.option !== "max") {   // faint outline: what filling the roof would give
          const fh = (full[i] / max) * f.ih;
          el("rect", { x, y: f.m.t + f.ih - fh, width: bw - 6, height: fh, rx: 3, fill: "none", stroke: css("--solar"), "stroke-dasharray": "3 3", "stroke-width": 1 }, f.svg);
        }
        const r = el("rect", { x, y: f.m.t + f.ih - h, width: bw - 6, height: h, rx: 3, fill: css("--solar"), tabindex: 0 }, f.svg);
        el("text", { x: x + (bw - 6) / 2, y: f.h - 8, "text-anchor": "middle", text: MONTHS[i] }, f.svg);
        const show = (evt) => showTip(evt, MONTHS[i], [{ value: fmt(val) + " kWh", label: "solar", color: css("--solar") }]);
        r.addEventListener("pointermove", show); r.addEventListener("focus", (e) => show({ clientX: e.target.getBoundingClientRect().x, clientY: e.target.getBoundingClientRect().y }));
        r.addEventListener("pointerleave", hideTip); r.addEventListener("blur", hideTip);
      });
      // panel drawing: same frame for every layout, same colours for every layout of one panel model
      const all = V.flatMap((x) => x.panel_list);
      const pts = all.flatMap((p) => p.c || [[p.x, p.y]]);
      const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
      const ks = V.filter((x) => x.panel_wp === v.panel_wp).flatMap((x) => x.panel_list.map((p) => p.k));
      const x0 = Math.min(...xs) - 2, x1 = Math.max(...xs) + 2, y0 = Math.min(...ys) - 2, y1 = Math.max(...ys) + 2;
      const scale = 300 / Math.max(x1 - x0, y1 - y0);
      const w = (x1 - x0) * scale, hh = (y1 - y0) * scale;
      const g = frame($("panels"), w + 20, hh + 20, { l: 10, r: 10, t: 10, b: 10 });
      const kmin = Math.min(...ks), kmax = Math.max(...ks);
      const seq = ["--seq-2", "--seq-3", "--seq-4", "--seq-5"].map(css);
      const X = (x) => 10 + (x - x0) * scale, Y = (y) => 10 + (y1 - y) * scale;
      for (const p of v.panel_list) {
        const tt = kmax > kmin ? (p.k - kmin) / (kmax - kmin) : 1;
        const c = seq[Math.min(3, Math.floor(tt * 4))];
        let r;
        if (p.c) r = el("path", { d: "M" + p.c.map((q) => X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1)).join("L") + "Z", fill: c, stroke: css("--panel"), "stroke-width": 0.6 }, g.svg);
        else r = el("rect", { x: X(p.x) - scale / 2, y: Y(p.y) - scale / 2, width: scale, height: scale, rx: 2, fill: c }, g.svg);
        r.addEventListener("pointermove", (evt) => showTip(evt, "Panel", [{ value: fmt(p.k) + " kWh/yr", label: "" }]));
        r.addEventListener("pointerleave", hideTip);
      }
      const vk = v.panel_list.map((p) => p.k);
      $("panel-note").textContent = v.panels ? `${fmt(Math.min(...vk))} to ${fmt(Math.max(...vk))} kWh a year per panel. Tilt ${fmt(D.roof.tilt_deg)}°, mean shade loss ${pct(v.mean_shade_loss)}.` : "No block on this roof is big enough for this layout.";
    }
    draw();
  }

  function surplus(D) {
    const F = D.facts;
    $("surplus-lede").textContent = `The host (a ${fmt(F.host_use_kwh.v)} kWh-a-year office) uses ${pct(F.host_self_share.v)} of the solar itself. The other ${fmt(F.surplus_kwh.v)} kWh a year is spare, and ${fmt(F.surplus_weekend_kwh.v)} kWh of it comes at weekends, when the office is closed.`;
    const map = D.host.surplus_map;
    const host = $("heatmap");
    host.replaceChildren();
    const W = 730, H = 24 * 7 + 40, m = { l: 44, t: 8, b: 26 };
    const f = frame(host, W, H, { l: m.l, r: 6, t: m.t, b: m.b });
    const cw = (W - m.l - 6) / 365, ch = (H - m.t - m.b) / 24;
    const max = Math.max(...map.flat());
    const steps = ["--seq-0", "--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5"].map(css);
    const bins = [0, 0.25, 1, 2, 4, Infinity].map((x) => x * (max / 8));
    const colorOf = (v) => (v <= 0.01 ? steps[0] : steps[Math.min(5, 1 + bins.findIndex((b, i) => v <= bins[i + 1]))]);
    const g = el("g", {}, f.svg);
    map.forEach((day, d) => day.forEach((v, h) => {
      el("rect", { x: m.l + d * cw, y: m.t + h * ch, width: cw + 0.3, height: ch + 0.3, fill: colorOf(v) }, g);
    }));
    for (let h = 0; h < 24; h += 6) el("text", { x: m.l - 6, y: m.t + h * ch + ch, "text-anchor": "end", text: String(h).padStart(2, "0") + ":00" }, f.svg);
    const start = new Date(D.host.first_day + "T00:00:00Z");
    for (let mo = 0; mo < 12; mo++) {
      const d = Math.round((Date.UTC(start.getUTCFullYear(), mo, 1) - start) / 864e5);
      el("text", { x: m.l + d * cw + 2, y: H - 8, text: MONTHS[mo] }, f.svg);
    }
    const hit = el("rect", { x: m.l, y: m.t, width: 365 * cw, height: 24 * ch, fill: "transparent" }, f.svg);
    hit.addEventListener("pointermove", (evt) => {
      const r = f.svg.getBoundingClientRect();
      const d = Math.max(0, Math.min(364, Math.floor((((evt.clientX - r.left) / r.width) * W - m.l) / cw)));
      const h = Math.max(0, Math.min(23, Math.floor((((evt.clientY - r.top) / r.height) * H - m.t) / ch)));
      const date = new Date(start.getTime() + d * 864e5);
      showTip(evt, date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) + " · " + String(h).padStart(2, "0") + ":00", [{ value: fmt(map[d][h], 1) + " kWh", label: "spare solar" }]);
    });
    hit.addEventListener("pointerleave", hideTip);
    const lg = $("heat-legend");
    lg.replaceChildren();
    const labels = ["none", "a little", "", "", "", "most"];
    steps.forEach((c, i) => { if (labels[i] !== "") { const s = el("span", {}, lg); el("i", { style: "background:" + c }, s); s.appendChild(document.createTextNode(labels[i])); } });
    el("span", { class: "small", text: "Rows: local hour. Columns: days of the typical year. Weekends show as darker stripes." }, lg);
  }

  const BCOL = ["--s1", "--s2", "--s3", "--s7"];
  function neighbours(D) {
    const B = D.buildings;
    const colors = B.map((_, i) => css(BCOL[i] || "--ink-3"));
    let daytype = "weekday";
    const sun = D.roof.solar_day_by_month;
    const solar = Array.from({ length: 24 }, (_, h) => (sun[5][h] + sun[6][h] + sun[7][h]) / 3);
    function draw() {
      const f = frame($("profiles"), 720, 280, { l: 44, r: 10, t: 24, b: 26 });
      const all = [solar, ...B.map((b) => b.profile[daytype])];
      const max = niceMax(Math.max(...all.flat()));
      yAxis(f, max, 4, (v) => fmt(v, max < 5 ? 1 : 0), "kWh per hour");
      hourAxis(f, 24);
      const area = linePath(solar, f, max, 24) + `L${f.m.l + (23.5 / 24) * f.iw},${f.m.t + f.ih}L${f.m.l + (0.5 / 24) * f.iw},${f.m.t + f.ih}Z`;
      el("path", { d: area, fill: css("--solar-soft"), stroke: css("--solar"), "stroke-width": 2 }, f.svg);
      B.forEach((b, i) => el("path", { d: linePath(b.profile[daytype], f, max, 24), fill: "none", stroke: colors[i], "stroke-width": 2 }, f.svg));
      crosshair(f, 24, (i) => String(i).padStart(2, "0") + ":00 · " + daytype,
        (i) => [{ value: fmt(solar[i], 1) + " kWh", label: "solar (summer)", color: css("--solar") },
          ...B.map((b, k) => ({ value: fmt(b.profile[daytype][i], 1) + " kWh", label: b.label, color: colors[k] }))]);
    }
    legend($("profiles-legend"), [{ label: "Solar, summer average", color: css("--solar") }, ...B.map((b, i) => ({ label: b.label, color: colors[i], line: true }))]);
    $("daytype").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      daytype = b.dataset.v;
      for (const x of $("daytype").children) x.setAttribute("aria-pressed", String(x === b));
      draw();
    });
    draw();
    // list
    const list = $("blist");
    B.forEach((b, i) => {
      const r = el("div", { class: "brow" }, list);
      el("span", { class: "dot", style: "background:" + colors[i] }, r);
      const t = el("div", {}, r);
      el("div", { text: b.label }, t);
      el("div", { class: "meta", text: (b.id === "host" ? "Host · " : b.distance_m + " m away · ") + b.kind + " · " + (b.source.startsWith("proxy") ? "estimated use" : b.source) }, t);
      el("div", { class: "num", text: fmt(b.yearly_kwh) + " kWh/yr" }, r);
    });
    // map
    const H0 = D.host_latlon;
    const C = D.candidates;
    const toXY = (lat, lon) => [(lon - H0[1]) * 111320 * Math.cos((H0[0] * Math.PI) / 180), (lat - H0[0]) * 110540];
    const all = C.map((c) => ({ ...c, xy: toXY(c.lat, c.lon) }));
    const pts = all.filter((p) => p.distance_m <= D.max_distance_m * 2.5);       // far ones are listed below instead
    const far = all.filter((p) => p.distance_m > D.max_distance_m * 2.5);
    const reach = Math.max(D.max_distance_m * 1.15, ...pts.map((p) => Math.hypot(...p.xy))) + 20;
    const S = 300, k = S / 2 / reach;
    const f = frame($("map"), S, S, { l: 0, r: 0, t: 0, b: 0 });
    el("circle", { cx: S / 2, cy: S / 2, r: D.max_distance_m * k, fill: css("--accent-soft"), stroke: css("--accent"), "stroke-dasharray": "4 4" }, f.svg);
    el("text", { x: S / 2 + D.max_distance_m * k * 0.71 + 4, y: S / 2 - D.max_distance_m * k * 0.71, text: D.max_distance_m + " m" }, f.svg);
    const joined = B.map((b) => b.id);
    for (const p of pts) {
      const x = S / 2 + p.xy[0] * k, y = S / 2 - p.xy[1] * k;
      const i = joined.indexOf(p.building_id);
      const c = i >= 0 ? colors[i] : css("--grid-ink");
      el("line", { x1: S / 2, y1: S / 2, x2: x, y2: y, stroke: c, "stroke-width": 1, opacity: i >= 0 ? 0.8 : 0.4 }, f.svg);
      const dot = el("circle", { cx: x, cy: y, r: 7, fill: c, stroke: css("--panel"), "stroke-width": 2 }, f.svg);
      if (i >= 0) el("text", { x: x + 10, y: y + 4, text: p.building_id.replace(/_/g, " ") }, f.svg);
      dot.addEventListener("pointermove", (evt) => showTip(evt, p.building_id.replace(/_/g, " "), [{ value: p.distance_m + " m", label: p.use_type + " · " + (i >= 0 ? "joins" : "too far") }]));
      dot.addEventListener("pointerleave", hideTip);
    }
    el("rect", { x: S / 2 - 8, y: S / 2 - 8, width: 16, height: 16, rx: 3, fill: colors[0], stroke: css("--panel"), "stroke-width": 2 }, f.svg);
    el("text", { x: S / 2 + 12, y: S / 2 + 18, text: "host" }, f.svg);
    const out = all.filter((p) => p.distance_m > D.max_distance_m);
    $("map-note").textContent = "Distances between building centres. Hover a dot for details. " +
      (out.length ? "Too far (grey" + (far.length ? ", or off the plan" : "") + "): " + out.map((p) => p.building_id.replace(/_/g, " ") + " " + p.distance_m + " m").join(", ") + "." : "");
  }

  function prices(D) {
    const P = D.prices.by_local_hour, F = D.facts;
    const years = ["2023", "2024", "2025"].filter((y) => P[y]);
    const cols = { "2023": css("--s1"), "2024": css("--s2"), "2025": css("--s3") };
    const f = frame($("pricechart"), 560, 260, { l: 44, r: 10, t: 24, b: 26 });
    const max = niceMax(Math.max(...years.flatMap((y) => P[y])));
    yAxis(f, max, 4, (v) => fmt(v, 2), "€/kWh");
    hourAxis(f, 24);
    years.forEach((y) => el("path", { d: linePath(P[y], f, max, 24), fill: "none", stroke: cols[y], "stroke-width": 2 }, f.svg));
    crosshair(f, 24, (i) => String(i).padStart(2, "0") + ":00 local", (i) => years.map((y) => ({ value: "€" + fmt(P[y][i], 3), label: y + " average", color: cols[y] })));
    legend($("price-legend"), years.map((y) => ({ label: y + " average", color: cols[y], line: true })));
    const t = P.typical;
    const lo = t.indexOf(Math.min(...t)), hi = t.indexOf(Math.max(...t));
    $("prices-lede").textContent = `On an average day the regulated price is lowest around ${String(lo).padStart(2, "0")}:00 (€${fmt(t[lo], 3)}/kWh) and highest around ${String(hi).padStart(2, "0")}:00 (€${fmt(t[hi], 3)}/kWh). In 2025 the evening was dearer than midday on ${F.evening_days.v} of 365 days. That gap is what a battery can earn from.`;
    const tb = $("forecast-table");
    tb.replaceChildren();
    const hr = el("tr", {}, el("thead", {}, tb));
    for (const h of ["Days ahead", "Model", "Same hour last week", "Typical year"]) el("th", { text: h }, hr);
    const body = el("tbody", {}, tb);
    for (const [k, r] of Object.entries(D.prices.model.horizons)) {
      const tr = el("tr", {}, body);
      el("td", { text: k.replace("_days", "") }, tr);
      const best = Math.min(r.model.mae, r.same_hour_last_week.mae, r.typical_year.mae);
      for (const v of [r.model.mae, r.same_hour_last_week.mae, r.typical_year.mae]) {
        const td = el("td", { class: "n", text: fmt(v, 4) }, tr);
        if (v === best) td.style.fontWeight = "600";
      }
    }
  }

  function battery(D) {
    const F = D.facts, B = D.battery;
    const chosen = B.chosen_with_guests;
    $("battery-answer").textContent = chosen > 0
      ? `Yes: with the guests, a ${fmt(chosen)} kWh battery pays for itself.`
      : `Not at today's prices. At an assumed €${fmt(F.lfp_price.v)} per kWh, no battery size pays for itself here. For the office alone, a 5 kWh LFP battery would only break even at about €${fmt(F.lfp5_break_even.v)} per kWh. With the two guests, almost all the solar is already used.`;
    const sel = $("btype");
    for (const t of B.types) el("option", { value: t.id, text: t.label }, sel);
    function draw() {
      const type = B.types.find((t) => t.id === sel.value);
      const rows = B.sizing_host.filter((r) => r.battery_type === type.id && r.battery_kwh > 0);
      const f = frame($("sizing"), 720, 260, { l: 52, r: 10, t: 24, b: 30 });
      const max = niceMax(Math.max(...rows.flatMap((r) => [r.yearly_gain_eur, r.yearly_cost_eur])));
      yAxis(f, max, 4, (v) => "€" + fmt(v), "€ per year");
      const gw = f.iw / rows.length, bw = Math.min(26, (gw - 10) / 2);
      const cg = css("--s1"), cc = css("--s2");
      rows.forEach((r, i) => {
        const x = f.m.l + i * gw + gw / 2;
        for (const [j, v, c, lab] of [[-1, r.yearly_gain_eur, cg, "gain"], [1, r.yearly_cost_eur, cc, "cost"]]) {
          const h = (v / max) * f.ih;
          const rect = el("rect", { x: x + (j < 0 ? -bw - 1 : 1), y: f.m.t + f.ih - h, width: bw, height: Math.max(h, 0.5), rx: 3, fill: c }, f.svg);
          rect.addEventListener("pointermove", (evt) => showTip(evt, `${fmt(r.battery_kwh)} kWh ${type.id}`, [
            { value: "€" + fmt(r.yearly_gain_eur), label: "gain a year", color: cg },
            { value: "€" + fmt(r.yearly_cost_eur), label: "cost a year", color: cc },
            { value: "€" + fmt(r.break_even_eur_per_kwh), label: "break-even price per kWh" },
            { value: fmt(r.cycles_per_year), label: "cycles a year" }]));
          rect.addEventListener("pointerleave", hideTip);
        }
        el("text", { x, y: f.h - 10, "text-anchor": "middle", text: fmt(r.battery_kwh) + " kWh" }, f.svg);
      });
      legend($("sizing-legend"), [{ label: "Owner's yearly gain from the battery", color: cg }, { label: "Battery's yearly cost (price ÷ life + upkeep)", color: cc }]);
      $("type-note").textContent = `${type.label}: €${fmt(type.capex_eur_per_kwh)}/kWh installed, ${pct(type.round_trip)} round trip, ${fmt(type.cycle_life)} cycles, ${type.calendar_years} years. ${type.notes}`;
    }
    sel.addEventListener("change", draw);
    draw();

    // example days
    const names = { summer_weekday: "Summer weekday", summer_sunday: "Summer Sunday + Monday", winter_weekday: "Winter weekday" };
    const pick = $("daypick");
    let key = "summer_sunday";
    for (const k of Object.keys(D.days)) {
      const b = el("button", { type: "button", "aria-pressed": String(k === key), "data-v": k, text: names[k] || k }, pick);
    }
    pick.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      key = b.dataset.v;
      for (const x of pick.children) x.setAttribute("aria-pressed", String(x === b));
      drawDay();
    });
    $("day-note").textContent = (B.shown_is_illustration
      ? `The agent picks no battery here, so this shows what a ${fmt(B.shown_kwh)} kWh LFP battery would do, as an illustration.`
      : `The chosen ${fmt(B.shown_kwh)} kWh battery.`) +
      " Each hour the solar goes to the host first, then the guests, then the battery, and only the rest leaves the site. The battery never charges from the grid. Typical-year prices.";
    function drawDay() {
      const d = D.days[key];
      const n = d.solar.length;
      const series = [
        { k: "to_host", label: "Solar → host", color: css("--s1") },
        { k: "to_guests", label: "Solar → guests", color: css("--s2") },
        { k: "charge", label: "Solar → battery", color: css("--s7") },
        { k: "export", label: "Solar → grid (wasted)", color: css("--grid-ink") },
      ];
      const f = frame($("daychart"), 720, 250, { l: 44, r: 10, t: 24, b: 26 });
      const tot = d.solar.map((_, i) => series.reduce((s, x) => s + d[x.k][i], 0) + d.battery_out[i]);
      const max = niceMax(Math.max(...tot, 1));
      yAxis(f, max, 4, (v) => fmt(v, max < 5 ? 1 : 0), "kWh per hour");
      hourAxis(f, n);
      const bw = f.iw / n;
      for (let i = 0; i < n; i++) {
        let y = f.m.t + f.ih;
        const stack = [...series, { k: "battery_out", label: "Battery → buildings", color: css("--s3") }];
        for (const s of stack) {
          const v = d[s.k][i]; if (v <= 0.001) continue;
          const h = (v / max) * f.ih;
          y -= h;
          el("rect", { x: f.m.l + i * bw + 1, y: y + 1, width: Math.max(bw - 2, 1), height: Math.max(h - 1, 0.5), fill: s.color, rx: 1.5 }, f.svg);
        }
      }
      crosshair(f, n, (i) => (n > 24 ? (i < 24 ? "Sunday " : "Monday ") : "") + String(i % 24).padStart(2, "0") + ":00 · €" + fmt(d.price[i], 3) + "/kWh",
        (i) => [...series, { k: "battery_out", label: "Battery → buildings", color: css("--s3") }].map((s) => ({ value: fmt(d[s.k][i], 1) + " kWh", label: s.label, color: s.color })));
      legend($("day-legend"), [...series, { label: "Battery → buildings", color: css("--s3") }]);
      const g = frame($("levelchart"), 720, 110, { l: 44, r: 10, t: 22, b: 22 });
      const lmax = niceMax(Math.max(B.shown_kwh, ...d.level));
      yAxis(g, lmax, 2, (v) => fmt(v), "Battery level, kWh");
      el("path", { d: linePath(d.level, g, lmax, n), fill: "none", stroke: css("--s7"), "stroke-width": 2 }, g.svg);
      crosshair(g, n, (i) => String(i % 24).padStart(2, "0") + ":00", (i) => [{ value: fmt(d.level[i], 1) + " kWh", label: "in the battery", color: css("--s7") }]);
    }
    drawDay();
  }

  function money(D) {
    const M = D.money;
    const sel = $("pyear");
    const years = Object.keys(M.slider).sort((a, b) => (a === "typical" ? -1 : b === "typical" ? 1 : a.localeCompare(b)));
    for (const y of years) el("option", { value: y, text: y === "typical" ? "Typical (2023-25 average)" : y }, sel);
    sel.value = years[0];
    const slider = $("discount");
    slider.value = Math.round(M.default_discount * 100);
    const scen = D.battery.chosen_with_guests > 0 ? "with_battery" : "without_battery";
    const capex = M.capex[scen === "with_battery" ? "direct_with_battery" : "direct_no_battery"];
    const om = M.om[scen === "with_battery" ? "direct_with_battery" : "direct_no_battery"];
    function draw() {
      const d = slider.value / 100;
      $("discount-out").textContent = slider.value + "%";
      const b = M.slider[sel.value][scen];
      // same formula as step 09 owner_total_at_discount()
      const owner = b.host_saving + (1 - d) * b.guests_value + b.export;
      const guests = d * b.guests_value;
      const net = owner - om;
      const host = $("money-stats");
      host.replaceChildren();
      const items = [
        ["Owner's value a year", "€" + fmt(owner), "modelled", "host savings + sales + export"],
        ["Neighbours save a year", "€" + fmt(guests), "modelled", "all guests together"],
        ["Panels installed", "€" + fmt(capex), "assumption", "€1,400 per kWp"],
        ["Simple payback", net > 0 ? fmt(capex / net, 1) + " years" : "never", "modelled", "after €" + fmt(om) + " upkeep a year"],
      ];
      for (const [label, value, kind, src] of items) {
        const s = el("div", { class: "stat" }, host);
        el("span", { class: "label", text: label }, s);
        el("span", { class: "value", text: value }, s);
        s.appendChild(chip({ kind, src }));
      }
      $("money-note").textContent = `Host savings €${fmt(b.host_saving)}, sales to guests €${fmt((1 - d) * b.guests_value)}, export €${fmt(b.export)}. Grid prices are the real hourly PVPC of the chosen year; export earns the wholesale price (assumption). ${scen === "with_battery" ? "Includes the battery." : "No battery, as the agent chose."}`;
    }
    slider.addEventListener("input", draw);
    sel.addEventListener("change", draw);
    draw();
  }

  function sources(D) {
    const host = $("sources-body");
    for (const s of D.sources) {
      const sec = el("section", {}, host);
      el("h3", { text: s.title.replace(/`/g, "") }, sec);
      for (const p of s.intro) { const e = el("p", { class: "note" }, sec); e.innerHTML = p; }   // from our own SOURCES.md, escaped by the export
      if (s.rows.length) {
        const wrap = el("div", { class: "table-wrap" }, sec);
        const t = el("table", {}, wrap);
        const hr = el("tr", {}, el("thead", {}, t));
        for (const h of s.header) el("th", { text: h.replace(/\*\*/g, "") }, hr);
        const tb = el("tbody", {}, t);
        for (const r of s.rows) { const tr = el("tr", {}, tb); for (const c of r) { const td = el("td", {}, tr); td.innerHTML = c; } }
      }
    }
  }

  // highlight the step in view
  function trackSteps() {
    const links = [...document.querySelectorAll("#steps a")];
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) {
        for (const a of links) a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id);
      }
    }, { rootMargin: "-40% 0px -55% 0px" });
    document.querySelectorAll("main section[id]").forEach((s) => io.observe(s));
  }

  function start(D) {
    for (const fn of [overview, roof, surplus, neighbours, prices, battery, money, sources]) {
      try { fn(D); } catch (err) { console.error(fn.name, err); }
    }
    trackSteps();
  }

  if (window.SITE_DATA) start(window.SITE_DATA);
  else fetch("data/site_data.json").then((r) => r.json()).then(start).catch((e) => {
    document.querySelector(".wrap").prepend(Object.assign(document.createElement("p"), { className: "banner", textContent: "Could not load data/site_data.json. Run python -m step10_publish_report.export_site_data from the pipeline folder." }));
    console.error(e);
  });
})();
