/* Roofscapes (Re)Powered website. Reads data/site_data.json (written by
   pipeline/step09_publish_report/export_site_data.py) and draws every section.
   No modelling happens here except the guest-discount slider, which uses the same
   formula as step 08 (owner_total_at_discount). Charts are plain SVG. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const $ = (id) => document.getElementById(id);
  const fmt = (v, d = 0) => (v == null || Number.isNaN(v) ? "–" : Number(v).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const pct = (v) => fmt(v * 100) + "%";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function el(tag, attrs = {}, parent) {
    const svg = ["svg", "g", "line", "rect", "path", "text", "circle", "polyline", "image", "defs", "pattern", "clipPath"].includes(tag);
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
    // every warning says what is wrong AND what we need to look at or change
    const wbox = $("warnings");
    for (const w of D.warnings || []) {
      const b = el("div", { class: "banner" }, wbox);
      el("b", { text: "Check" }, b);
      const t = el("span", {}, b);
      t.appendChild(document.createTextNode(w.text + " "));
      if (w.next) el("em", { class: "next", text: "Next: " + w.next }, t);
    }
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

  function norm(t) { return String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim(); }
  const USE = { "4_3_publicServices": "Public services", "4_1_office": "Office", "1_residential": "Residential", "3_industrial": "Industrial", "4_2_retail": "Retail" };

  function property(D) {
    const S = D.step01 || { properties: [], gaps: [] };
    const known = S.properties;
    const dl = $("known-props"), kb = $("known-buttons"), msg = $("search-msg"), card = $("prop-card");
    for (const r of known) {
      el("option", { value: r.query }, dl);
      const b = el("button", { type: "button", class: "pill", text: (r.query || r.catastro_address).replace(/, Barcelona$/, "") }, kb);
      b.addEventListener("click", () => { $("addr").value = r.query; show(r); });
    }
    function field(dlist, k, v, src) {
      const box = el("div", {}, dlist);
      el("dt", { text: k }, box);
      const dd = el("dd", {}, box);
      dd.appendChild(document.createTextNode(v == null || v === "" ? "–" : v));
      if (src) el("small", { text: src }, dd);
    }
    function show(r) {
      card.hidden = false;
      $("prop-title").textContent = r.query + " · " + (r.analysed ? "analysed in steps 02-10" : "step 01 only");
      const f = $("prop-facts");
      f.replaceChildren();
      const rf = r.roof || {};
      field(f, "Address in Catastro", r.catastro_address, "Catastro");
      field(f, "Cadastral reference", r.refcat, "Catastro");
      field(f, "Coordinates", r.lat != null ? `${r.lat.toFixed(5)}, ${r.lon.toFixed(5)}` : null, r.geocoder ? "geocoder: " + r.geocoder : "");
      field(f, "Year built", r.year_built, "Catastro");
      field(f, "Current use", USE[r.current_use] || r.current_use, "Catastro");
      field(f, "Dwellings", r.dwellings, "Catastro");
      field(f, "Height", r.building_height_m != null ? fmt(r.building_height_m, 1) + " m" : null, r.height_source ? "from " + r.height_source.replace("lidar", "LiDAR") : "");
      field(f, "Footprint", r.footprint_area_m2 != null ? fmt(r.footprint_area_m2, 0) + " m²" : null, r.footprint_source === "lidar" ? "traced from LiDAR (no building in Catastro)" : "Catastro");
      field(f, "LiDAR sheets", (r.lidar_tiles || []).map((t) => (t.match(/1km(\d+)/) || [, t])[1]).join(", "), "ICGC Territorial LiDAR");
      field(f, "Flat roof", r.flat_roof == null ? null : (r.flat_roof ? "yes" : "no") + (rf.flat_share != null ? `: ${pct(rf.flat_share)} of cells under 5°, median slope ${fmt(rf.median_slope_deg, 1)}°` : ""), "modelled from LiDAR");
      field(f, "Roof height range", rf.roof_height_min != null ? `${fmt(rf.roof_height_min, 1)} to ${fmt(rf.roof_height_max, 1)} m` : null, "LiDAR");
      field(f, "Heritage protected", r.heritage_protected == null ? "unknown, not checked yet" : (r.heritage_protected ? "yes" : "no"), "see gaps below");
      const w = $("prop-warn");
      w.replaceChildren();
      for (const t of r.warnings || []) {
        const b = el("div", { class: "banner" }, w);
        el("b", { text: "Check" }, b);
        const sp = el("span", {}, b);
        sp.appendChild(document.createTextNode(t + " "));
        el("em", { class: "next", text: "Next: decide whether to relax the flat-roof limit or lay panels on the flat parts only (see gaps)." }, sp);
      }
      if (!r.analysed) {
        const b = el("div", { class: "banner" }, w);
        el("b", { text: "Check" }, b);
        const sp = el("span", {}, b);
        sp.appendChild(document.createTextNode("Only step 01 has been run for this property. "));
        el("em", { class: "next", text: "Next: run steps 02-10 for it (commands in pipeline/README.md); the rest of this page shows " + D.meta.case + "." }, sp);
      }
      if (r.about) el("p", { class: "small", text: r.about }, w);
    }
    $("search").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = norm($("addr").value);
      if (!q) { msg.textContent = "Type an address or a cadastral reference."; return; }
      const hit = known.find((r) => [r.query, r.catastro_address, r.refcat].some((t) => norm(t).includes(q) || q.includes(norm(t))))
        || known.find((r) => q.split(" ").filter((w) => w.length > 2).every((w) => norm(r.query + " " + r.catastro_address).includes(w)));
      if (hit) { msg.textContent = ""; show(hit); return; }
      card.hidden = true;
      msg.textContent = `We have not run "${$("addr").value}" yet. This page cannot call Catastro or ICGC itself, so run step 01 on a laptop: ${S.run_command}. Then add the building.json with export_site_data --property.`;
    });
    const g = $("gaps-table");
    const hr = el("tr", {}, el("thead", {}, g));
    for (const h of ["Gap", "Where it stands", "What to do next"]) el("th", { text: h }, hr);
    const tb = el("tbody", {}, g);
    for (const x of S.gaps) {
      const r = el("tr", {}, tb);
      el("td", { text: x.gap }, r); el("td", { text: x.status }, r); el("td", { text: x.next }, r);
    }
    const first = known.find((r) => r.analysed) || known[0];
    if (first) { $("addr").value = first.query; show(first); }
  }

  // Step 01: where the host and participant buildings are, on a street map
  function siteMap(D) {
    const cases = (D.step01 && D.step01.cases) || [];
    if (!cases.length || !window.L) return;
    $("s1-map-card").hidden = false;
    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const dark = matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light"
      || document.documentElement.dataset.theme === "dark";
    const map = L.map("s1-map", { scrollWheelZoom: false });
    L.tileLayer("https://geoserveis.icgc.cat/servei/catalunya/mapa-base/wmts/topografic-gris/MON3857NW/{z}/{x}/{y}.png", {
      maxZoom: 20, maxNativeZoom: 19,
      attribution: 'Base map &copy; <a href="https://www.icgc.cat/">Institut Cartogràfic i Geològic de Catalunya</a> (CC BY 4.0)',
    }).addTo(map);
    if (dark) $("s1-map").classList.add("dark-tiles");
    const layer = L.layerGroup().addTo(map);
    const short = (n) => n.replace(/\s*\(.*\)\s*/, "").replace(/^Oficines /, "");
    const pick = $("s1-casepick");
    const buttons = cases.map((c) => {
      const b = el("button", { type: "button", text: c.case.toUpperCase() + " · " + c.role.replace(/ (end-to-end )?(test )?case$/, "") }, pick);
      b.addEventListener("click", () => draw(c));
      return b;
    });

    function draw(c) {
      buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(cases[i] === c)));
      layer.clearLayers();
      const host = css("--s1"), guest = css("--s2");
      const ring = L.circle([c.host.lat, c.host.lon], { radius: 100, color: css("--ink-3"), weight: 1.5, dashArray: "4 4", fill: false, interactive: false }).addTo(layer);
      for (const f of c.map.features) {
        const p = f.properties, col = p.role === "host" ? host : guest;
        const traced = p.footprint_source === "lidar";
        const tip = `${p.name}<br>${p.refcat || "no cadastral ref"} · footprint: ${p.footprint_source === "lidar" ? "LiDAR trace" : p.footprint_source}`;
        const shape = f.geometry.type === "Point"
          ? L.circleMarker([p.lat, p.lon], { radius: 7, color: col, weight: 2, fillOpacity: 0.5 })
          : L.geoJSON(f, { style: { color: col, weight: 2, fillColor: col, fillOpacity: 0.35, dashArray: traced ? "5 4" : null } });
        shape.bindPopup(tip).addTo(layer);
        const at = f.geometry.type === "Point" ? [p.lat, p.lon] : shape.getBounds().getCenter();  // label on the building, not the input point
        L.marker(at, { opacity: 0, interactive: false, keyboard: false })
          .bindTooltip(short(p.name), { permanent: true, direction: "top", className: "map-label", offset: [0, -4] }).addTo(layer);
      }
      const bounds = L.featureGroup(layer.getLayers().filter((l) => l !== ring)).getBounds()
        .extend(L.latLng(c.host.lat, c.host.lon).toBounds(220));  // the 100 m ring, plus a margin
      map.fitBounds(bounds, { padding: [24, 24] });

      const lg = $("s1-map-legend");
      lg.replaceChildren();
      for (const [cls, k, t] of [["", host, "host roof"], ["", guest, "participant (Catastro footprint)"], ["dash", guest, "participant (footprint traced from LiDAR)"], ["ring", "", "100 m: the tool's default wiring reach"]]) {
        const s = el("span", {}, lg);
        const i = el("i", { class: cls }, s);
        i.style.setProperty("--k", k); if (k) i.style.background = k;
        s.appendChild(document.createTextNode(t));
      }
      $("s1-map-note").textContent = c.name + ". Click a building for its cadastral reference." +
        (c.unlocated.length ? ` Not on the map (no address yet): ${c.unlocated.join(", ")}.` : "");

      const t = $("s1-case-table");
      t.replaceChildren();
      const hr = el("tr", {}, el("thead", {}, t));
      for (const h of ["Participant", "Role", "Address", "Cadastral ref", "Distance", "Footprint"]) el("th", { text: h }, hr);
      const tb = el("tbody", {}, t);
      for (const p of c.participants) {
        const r = el("tr", {}, tb);
        for (const v of [p.name, p.role, p.address || "unknown", p.refcat || "unknown",
          p.distance_m != null ? fmt(p.distance_m, 0) + " m" : "–", p.footprint_m2 != null ? fmt(p.footprint_m2, 0) + " m²" : "–"]) el("td", { text: v }, r);
      }
    }
    draw(cases[0].case === "cep9" ? cases[0] : cases.find((c) => c.case === "cep9") || cases[0]);
  }

  function match(D) {
    const M = D.match || {};
    const modes = Object.keys(M);
    if (!modes.length) return;
    $("match-card").hidden = false;
    const label = { wired: "Wired directly (any city)", legal: "Spanish legal: fixed shares, no cable" };
    const state = { mode: modes.includes("wired") ? "wired" : modes[0] };
    const seg = $("matchmode");
    seg.replaceChildren();
    for (const m of modes) {
      const b = el("button", { type: "button", "aria-pressed": String(m === state.mode), text: label[m] || m }, seg);
      b.addEventListener("click", () => { state.mode = m; for (const x of seg.children) x.setAttribute("aria-pressed", String(x === b)); draw(); });
    }
    function draw() {
      const R = M[state.mode], b = R.best, a = R.host_alone;
      $("match-what").textContent = `${R.what[0].toUpperCase() + R.what.slice(1)}. Reach used here: ${fmt(R.reach_m)} m. ${fmt(R.candidates.length)} buildings were in reach; ${fmt(R.tried)} groups of them were tried${R.exhaustive ? " (every possible group)" : " (local search)"}. The winner wastes the least solar, then earns the owner the most. A building only counts if it adds at least ${fmt(R.min_gain_kwh)} kWh a year, and a group has at most ${R.max_guests} guests.`;
      const st = $("match-stats");
      st.replaceChildren();
      for (const [l, v, u] of [["Solar used, host alone", pct(a.used_share), ""], ["Solar used, best group", pct(b.used_share), ""],
        ["Sent to the grid, best group", fmt(b.to_grid_kwh), "kWh"], ["Owner earns, best group", "€" + fmt(b.owner_eur), "a year"]]) {
        const s2 = el("div", { class: "stat" }, st);
        el("span", { class: "label", text: l }, s2);
        const vv = el("span", { class: "value", text: v }, s2);
        if (u) el("small", { text: u }, vv);
        s2.appendChild(chip({ kind: "modelled", src: "steps 07-08", note: "optimise.py" }));
      }
      const t = $("match-table");
      t.replaceChildren();
      const hr = el("tr", {}, el("thead", {}, t));
      ["Group", "Used", "To the grid", "Owner €/yr", "Guests save €/yr"].forEach((h, i) => el("th", { text: h, class: i ? "n" : "" }, hr));
      const tb = el("tbody", {}, t);
      const nm = (id) => { const c = R.candidates.find((x) => x.building_id === id); return (c && (c.name || c.building_id)) || id; };
      const rows = [{ buildings: [], ...a, used_share: a.used_share }, ...R.top.slice(0, 6)];
      rows.forEach((g, i) => {
        const r = el("tr", { class: i === 1 ? "pick" : "" }, tb);
        el("td", { text: i === 0 ? "Host alone" : g.buildings.map(nm).join(" + ") }, r);
        el("td", { class: "n", text: pct(g.used_share) }, r);
        el("td", { class: "n", text: fmt(g.to_grid_kwh) + " kWh" }, r);
        el("td", { class: "n", text: "€" + fmt(g.owner_eur) }, r);
        el("td", { class: "n", text: i === 0 ? "–" : "€" + fmt(g.guests_save_eur) }, r);
      });
      $("match-note").textContent = "Each building in the best group adds: " + b.marginal.map((m) => `${nm(m.building)} ${fmt(m.adds_kwh)} kWh`).join(", ") + " a year. Building use is an estimate, not meters. " +
        (state.mode === "legal" ? "Fixed shares are our simple rule (use in sunny hours); CEP9's real shares are not published." : "");
    }
    draw();
  }

  function roof(D) {
    const F = D.facts;
    const addr = D.roof.address || D.meta.address, usable = D.roof.usable_m2 != null ? D.roof.usable_m2 : F.usable_m2.v;
    $("roof-lede").textContent = `${addr}: ${fmt(usable)} m² of usable roof, read from ICGC LiDAR, with the sun from a PVGIS typical year. Pick how many panels to install: fill the whole roof, or only neat blocks of the best panels, as real installers do.` +
      (D.roof.separate ? " " + (D.roof.below_note || `This section shows another roof than the sections below (${D.meta.address}).`) : "");
    if (D.compare && D.compare.file) {
      $("compare-card").hidden = false;
      $("compare-img").src = /^(data:|https?:)/.test(D.compare.file) ? D.compare.file : "data/" + D.compare.file;
      $("compare-caption").textContent = D.compare.caption;
    }
    const V = D.roof.variants && D.roof.variants.length ? D.roof.variants : [{
      option: "max", name: "Fill the roof", panel_wp: 420, rule: "every panel that fits and loses at most 40% of its sun to shade",
      panels: F.panels.v, kwp: F.kwp.v, yearly_kwh: F.solar_kwh.v, kwh_per_kwp: F.kwh_per_kwp.v,
      mean_shade_loss: D.roof.mean_shade_loss, monthly_kwh: D.roof.monthly_kwh,
      panel_list: D.roof.panels.map((p) => ({ x: p.x, y: p.y, k: p.kwh })) }];
    const chosen = D.roof.chosen || { panel_wp: 420, option: "max" };
    // one tab per layout: Actual first, then each panel size with "fill the roof" before "neat blocks"
    const keyOf = (v) => (v.actual ? "actual" : v.panel_wp + "_" + v.option);
    const order = { max: 0, neat: 1, best: 2 };
    const tabs = [...V].sort((a, b) => (a.actual ? -1 : b.actual ? 1 : a.panel_wp - b.panel_wp || order[a.option] - order[b.option]));
    const state = { key: chosen.option === "actual" ? "actual" : chosen.panel_wp + "_" + chosen.option };
    if (!tabs.some((v) => keyOf(v) === state.key)) state.key = keyOf(tabs[0]);
    const pick = () => tabs.find((v) => keyOf(v) === state.key) || tabs[0];
    const actualV = tabs.find((v) => v.actual);
    const tabHost = $("layoutpick");
    tabHost.replaceChildren();
    for (const v of tabs) {
      const b = el("button", { type: "button", "aria-pressed": String(keyOf(v) === state.key), text: v.actual ? "Actual" : `${v.panel_wp} W · ${v.name}` }, tabHost);
      b.addEventListener("click", () => {
        state.key = keyOf(v);
        for (const x of tabHost.children) x.setAttribute("aria-pressed", String(x === b));
        draw();
      });
    }
    validation(tabs);

    // table of every layout
    const t = $("layout-table");
    t.replaceChildren();
    const hr = el("tr", {}, el("thead", {}, t));
    for (const h of ["Layout", "Panel", "Panels", "kWp", "kWh a year", "kWh per kWp"]) el("th", { text: h, class: ["Layout", "Panel"].includes(h) ? "" : "n" }, hr);
    const tb = el("tbody", {}, t);
    const rows = V.map((v) => {
      const r = el("tr", {}, tb);
      el("td", { text: v.name }, r);
      el("td", { text: v.panel_wp + " W" }, r);
      el("td", { class: "n", text: fmt(v.panels) }, r);
      el("td", { class: "n", text: fmt(v.kwp, v.actual ? 2 : 1) }, r);
      el("td", { class: "n", text: fmt(v.yearly_kwh) }, r);
      el("td", { class: "n", text: fmt(v.kwh_per_kwp) }, r);
      return [v, r];
    });
    const usedV = V.find((v) => v.option === chosen.option && v.panel_wp === chosen.panel_wp);
    $("layout-used").textContent = (D.roof.separate ? (D.roof.below_note || `The sections below use another roof (${D.meta.address}).`) : `The rest of this page (spare power, neighbours, battery and money) uses ${usedV ? usedV.name.toLowerCase() + " with " + usedV.panel_wp + " W panels" : "the pipeline's layout"}.`) + ` Block sizes and the share of the best panel are our assumptions (step 03, options.py); 540 W panel size is a typical catalogue panel. Next: to see the money for another layout, run steps 03-10 with --layout and --panel-wp for it.`;

    function draw() {
      const v = pick();
      if (!v) return;
      for (const [rv, r] of rows) r.classList.toggle("pick", rv === v);
      $("monthly-chip").dataset.kind = v.actual ? "reported" : "modelled";
      $("monthly-chip").textContent = v.actual ? "reported total · our monthly shape" : "modelled · step 03";
      $("layout-rule").textContent = v.actual
        ? `The system that is really on the two roofs: ${fmt(v.panels)} panels, ${fmt(v.kwp, 2)} kWp and about ${fmt(v.yearly_kwh)} kWh a year [${v.source}]. ${v.panel_wp_note}. The CEP9 source gives no monthly figures and no panel plan, so the months follow our model's shape and the panel areas are the ones step 02 finds on the roof photo. For this check the model treats both roofs as empty and lays its own panels, to see how close it gets to the real system.` + (v.by_roof ? ` By roof: ${v.by_roof.map((r) => `${r.roof} ${r.panels} panels`).join(", ")} [${v.by_roof_source}].` : "")
        : `${v.name}: ${v.rule}.` + (v.blocks ? ` ${v.blocks} blocks.` : "") + (v.roofs ? ` By roof: ${v.roofs.map((r) => `${r.roof} ${r.panels} panels`).join(", ")}.` : "");
      const st = $("layout-stats");
      st.replaceChildren();
      for (const [label, val, unit] of [["Panels", fmt(v.panels), ""], ["Peak power", fmt(v.kwp, v.actual ? 2 : 1), "kWp"],
        ["Solar a year", fmt(v.yearly_kwh), "kWh"], ["Per kWp", fmt(v.kwh_per_kwp), "kWh/kWp"]]) {
        const s = el("div", { class: "stat" }, st);
        el("span", { class: "label", text: label }, s);
        const vv = el("span", { class: "value", text: val }, s);
        if (unit) el("small", { text: unit }, vv);
        s.appendChild(v.actual
          ? chip(label === "Per kWp" ? { kind: "reported", src: "our division", note: "reported kWh ÷ reported kWp" } : { kind: "reported", src: v.source, note: v.source_url || "" })
          : chip({ kind: "modelled", src: "step 03", note: "ICGC LiDAR + PVGIS typical year" }));
      }
      // monthly bars
      // one y-axis for every layout, so switching layouts compares like with like
      const m = v.monthly_kwh || D.roof.monthly_kwh;
      const f = frame($("monthly"), 560, 240, { l: 48, r: 8, t: 22, b: 26 });
      const max = niceMax(Math.max(...V.flatMap((x) => x.monthly_kwh || m)));
      const full = (V.find((x) => x.option === "max" && x.panel_wp === v.panel_wp) || {}).monthly_kwh;
      yAxis(f, max, 4, (x) => fmt(x), "kWh");
      const bw = f.iw / 12;
      const defs = el("defs", {}, f.svg);
      if (v.actual) {
        const pat = el("pattern", { id: "hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
        el("rect", { width: 6, height: 6, fill: css("--solar-soft") }, pat);
        el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: css("--solar"), "stroke-width": 2.5 }, pat);
      }
      // the real system's months, laid over every other layout so they can be compared tab by tab
      const real = !v.actual && actualV && actualV.monthly_kwh ? actualV.monthly_kwh : null;
      if (real) {
        const pat = el("pattern", { id: "hatch-actual", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(-45)" }, defs);
        el("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: css("--actual"), "stroke-width": 1.6 }, pat);
      }
      $("monthly-note").textContent = v.actual
        ? "Hatched: the reported yearly total spread over the months with our model's shape (CEP9 publishes no monthly figures). Same scale as the other layouts."
        : "Same scale for every layout. The dashed outline is \"Fill the roof\" with the same panels." +
          (real ? ` Pink hatched bars: the real system (${fmt(actualV.yearly_kwh)} kWh a year reported, spread over the months with our model's shape), shown on every layout for comparison.` : "");
      m.forEach((val, i) => {
        const h = (val / max) * f.ih;
        const x = f.m.l + i * bw + 3;
        if (full && v.option !== "max" && !v.actual) {   // faint outline: what filling the roof would give
          const fh = (full[i] / max) * f.ih;
          el("rect", { x, y: f.m.t + f.ih - fh, width: bw - 6, height: fh, rx: 3, fill: "none", stroke: css("--solar"), "stroke-dasharray": "3 3", "stroke-width": 1 }, f.svg);
        }
        const r = el("rect", { x, y: f.m.t + f.ih - h, width: bw - 6, height: h, rx: 3, fill: v.actual ? "url(#hatch)" : css("--solar"), stroke: v.actual ? css("--solar") : "none", tabindex: 0 }, f.svg);
        el("text", { x: x + (bw - 6) / 2, y: f.h - 8, "text-anchor": "middle", text: MONTHS[i] }, f.svg);
        if (real) {
          const ah = (real[i] / max) * f.ih;
          el("rect", { x: x + 0.75, y: f.m.t + f.ih - ah, width: bw - 7.5, height: ah, rx: 3, fill: "url(#hatch-actual)", stroke: css("--actual"), "stroke-width": 1.5, "pointer-events": "none" }, f.svg);
        }
        const show = (evt) => showTip(evt, MONTHS[i], [{ value: fmt(val) + " kWh", label: v.actual ? "reported total, our monthly shape" : "solar, this layout", color: css("--solar") },
          ...(real ? [{ value: fmt(real[i]) + " kWh", label: "real system (reported, our shape)", color: css("--actual") }] : [])]);
        r.addEventListener("pointermove", show); r.addEventListener("focus", (e) => show({ clientX: e.target.getBoundingClientRect().x, clientY: e.target.getBoundingClientRect().y }));
        r.addEventListener("pointerleave", hideTip); r.addEventListener("blur", hideTip);
      });
      $("panels-key").textContent = v.actual ? "outlined = real panel blocks" : (actualV && actualV.traced ? "pink outline = real panels; " : "") + "darker = produces more; grey = left out; cream = usable roof";
      $("how-card").hidden = !!v.actual;
      if (v.actual) { drawActual(v); return; }
      // panel drawing: same frame for every layout, same colours for every layout of one panel model
      const all = V.flatMap((x) => x.panel_list);
      const outlines = D.roof.outlines || [], usableA = D.roof.usable_areas || [], reservedA = D.roof.reserved_areas || [];
      const pts = [...all.flatMap((p) => p.c || [[p.x, p.y]]), ...V.flatMap((x) => (x.left_out || []).flatMap((p) => p.c)),
        ...outlines.flatMap((o) => o.c)];
      const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
      const ks = V.filter((x) => x.panel_wp === v.panel_wp).flatMap((x) => x.panel_list.map((p) => p.k));
      const x0 = Math.min(...xs) - 2, x1 = Math.max(...xs) + 2, y0 = Math.min(...ys) - 2, y1 = Math.max(...ys) + 2;
      const scale = 300 / Math.max(x1 - x0, y1 - y0);
      const w = (x1 - x0) * scale, hh = (y1 - y0) * scale;
      const g = frame($("panels"), w + 20, hh + 20, { l: 10, r: 10, t: 10, b: 10 });
      const kmin = Math.min(...ks), kmax = Math.max(...ks);
      const seq = ["--seq-2", "--seq-3", "--seq-4", "--seq-5"].map(css);
      const X = (x) => 10 + (x - x0) * scale, Y = (y) => 10 + (y1 - y) * scale;
      // the buildings under the panels: roof outline, usable roof (step 02), areas kept free
      const ring = (c) => "M" + c.map((q) => X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1)).join("L") + "Z";
      for (const o of outlines) el("path", { d: ring(o.c), fill: css("--paper-2"), stroke: css("--ink-3"), "stroke-width": 1.2, "stroke-linejoin": "round" }, g.svg);
      for (const u of usableA) el("path", { d: ring(u.c), fill: css("--solar-soft"), stroke: "none" }, g.svg);
      for (const r of reservedA) {
        const rp = el("path", { d: ring(r.c), fill: "none", stroke: css("--ink-3"), "stroke-width": 1, "stroke-dasharray": "4 3" }, g.svg);
        rp.addEventListener("pointermove", (evt) => showTip(evt, "Left out", [{ value: r.name || "reserved", label: "kept free (assumption)" }]));
        rp.addEventListener("pointerleave", hideTip);
      }
      for (const o of outlines) {
        const c = o.c.reduce((a, q) => [a[0] + q[0] / o.c.length, a[1] + q[1] / o.c.length], [0, 0]);
        const t = el("text", { x: X(c[0]), y: Y(Math.max(...o.c.map((q) => q[1]))) - 4, "text-anchor": "middle", class: "roof-label", text: o.name }, g.svg);
      }
      // panels this layout drops, with the reason, drawn first so the kept ones sit on top
      for (const p of v.left_out || []) {
        const weak = p.why === "weak";
        const r = el("path", { d: "M" + p.c.map((q) => X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1)).join("L") + "Z", fill: weak ? css("--off-weak") : css("--off-loose"), stroke: css("--panel"), "stroke-width": 0.6 }, g.svg);
        r.addEventListener("pointermove", (evt) => showTip(evt, "Left out", [{ value: weak ? "weak" : "loose", label: weak ? "below this layout's cut-off" : "good, but in no big enough block" }]));
        r.addEventListener("pointerleave", hideTip);
      }
      for (const p of v.panel_list) {
        const tt = kmax > kmin ? (p.k - kmin) / (kmax - kmin) : 1;
        const c = seq[Math.min(3, Math.floor(tt * 4))];
        let r;
        if (p.c) r = el("path", { d: "M" + p.c.map((q) => X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1)).join("L") + "Z", fill: c, stroke: css("--panel"), "stroke-width": 0.6 }, g.svg);
        else r = el("rect", { x: X(p.x) - scale / 2, y: Y(p.y) - scale / 2, width: scale, height: scale, rx: 2, fill: c }, g.svg);
        r.addEventListener("pointermove", (evt) => showTip(evt, "Panel", [{ value: fmt(p.k) + " kWh/yr", label: "" }]));
        r.addEventListener("pointerleave", hideTip);
      }
      // where the real panels are (step 02 on the photo), outlined on top for comparison
      for (const t of (actualV && actualV.traced) || []) {
        el("path", { d: ring(t.c), fill: "none", stroke: css("--panel"), "stroke-width": 3, "stroke-linejoin": "round", "pointer-events": "none" }, g.svg);
        el("path", { d: ring(t.c), fill: "none", stroke: css("--actual"), "stroke-width": 1.4, "stroke-linejoin": "round", "pointer-events": "none" }, g.svg);
      }
      drawFunnel(v);
      const vk = v.panel_list.map((p) => p.k);
      $("panel-note").textContent = v.panels ? `${fmt(Math.min(...vk))} to ${fmt(Math.max(...vk))} kWh a year per panel. Tilt ${fmt(D.roof.tilt_deg)}°, mean shade loss ${pct(v.mean_shade_loss)}.` : "No block on this roof is big enough for this layout. Next: try the other panel size, or check whether the block rules in options.py are too strict for this roof.";
    }
    function validation(tabs) {
      const act = tabs.find((v) => v.actual);
      const roofs = D.roof.roofs || [];
      if (!act || !act.by_roof || roofs.length < 2) return;
      $("validation-card").hidden = false;
      const lay = tabs.filter((v) => !v.actual);
      const name = (r) => (act.by_roof.find((b) => b.roof.toLowerCase().includes(r)) || { roof: r }).roof;
      const actualOn = (r) => (act.by_roof.find((b) => b.roof.toLowerCase().includes(r)) || {}).panels;
      const t = $("validation-table");
      t.replaceChildren();
      const hr = el("tr", {}, el("thead", {}, t));
      el("th", { text: "Roof" }, hr);
      el("th", { text: "Actual", class: "n" }, hr);
      for (const v of lay) el("th", { text: `${v.panel_wp} W ${v.name.toLowerCase()}`, class: "n" }, hr);
      const tb = el("tbody", {}, t);
      const near = (a, b) => (a && b ? Math.abs(b / a - 1) <= 0.1 : false);
      for (const r of roofs) {
        const tr = el("tr", {}, tb);
        el("td", { text: name(r) + " · panels" }, tr);
        const a = actualOn(r);
        el("td", { class: "n", text: fmt(a) }, tr);
        for (const v of lay) {
          const n = ((v.roofs || []).find((x) => x.roof === r) || {}).panels;
          el("td", { class: "n" + (near(a, n) ? " close" : ""), text: fmt(n) }, tr);
        }
      }
      for (const [label, k, d] of [["Both roofs · panels", "panels", 0], ["Both roofs · kWp", "kwp", 1], ["Both roofs · kWh a year", "yearly_kwh", 0]]) {
        const tr = el("tr", {}, tb);
        el("td", { text: label }, tr);
        el("td", { class: "n", text: fmt(act[k], k === "kwp" ? 2 : d) }, tr);
        for (const v of lay) el("td", { class: "n" + (near(act[k], v[k]) ? " close" : ""), text: fmt(v[k], d) }, tr);
      }
      const n540 = lay.find((v) => v.panel_wp === act.panel_wp && v.option === "neat");
      $("validation-note").textContent = "Both roofs are treated as empty, so our tool lays its own panels and we compare them with what CEP9 really installed. The target is the 540 W neat-blocks layout (the real panels are 540 W)." +
        (n540 ? ` Today it gives ${fmt(n540.panels)} panels against ${fmt(act.panels)} real ones (${n540.panels >= act.panels ? "+" : ""}${pct(n540.panels / act.panels - 1)}) and ${fmt(n540.yearly_kwh)} kWh against ${fmt(act.yearly_kwh)} reported (${n540.yearly_kwh >= act.yearly_kwh ? "+" : ""}${pct(n540.yearly_kwh / act.yearly_kwh - 1)}).` : "") +
        " Bold green: within 10% of the real value.";
      const det = act.detected;
      $("validation-detected").textContent = `Real panel counts by roof: ${act.by_roof_source}.` +
        (det ? ` For comparison, step 02 finds ${Object.entries(det).map(([r, x]) => `${fmt(x.existing_panels_m2)} m² of panel-like surface on the ${r} roof (about ${fmt(x.existing_panels_estimate)} panels of 540 W)`).join(" and ")}; the rows on the red roof are mostly panels (Breno).` : "") +
        (act.check_notes && act.check_notes.length ? " " + act.check_notes.map((t) => t[0].toUpperCase() + t.slice(1) + ".").join(" ") : "");
    }

    function drawFunnel(v) {
      const host = $("funnel"), lg = $("funnel-legend");
      host.replaceChildren(); lg.replaceChildren();
      const fn = v.funnel;
      if (!fn) {
        host.textContent = "The step-by-step numbers for this layout are not in the data yet. Next: rerun step 03 (shade_yield) and step 09 so every layout carries its panel counts and the reasons panels were dropped.";
        host.className = "note";
        return;
      }
      host.className = "";
      const rows = [["Fit on the roof", fn.fit, "--solar"], ["Dropped: too shaded", -fn.shaded_out, "--grid-ink"],
        ["Dropped: weak (below cut-off)", -fn.weak, "--off-weak"], ["Dropped: loose (in no big enough block)", -fn.loose, "--off-loose"], ["Kept", fn.kept, "--st-3"]];
      const max = Math.max(1, fn.fit);
      for (const [label, n, col] of rows) {
        const r = el("div", { class: "frow" }, host);
        el("span", { class: "flabel", text: label }, r);
        const bar = el("span", { class: "fbar" }, r);
        const i = el("i", {}, bar);
        i.style.width = (Math.abs(n) / max * 100) + "%"; i.style.background = css(col);
        el("b", { class: "num", text: (n > 0 ? "" : n < 0 ? "−" : "") + fmt(Math.abs(n)) }, r);
      }
      for (const [col, t] of [["--off-weak", "weak: below the cut-off"], ["--off-loose", "loose: good, but in no big enough block"]]) {
        const sp = el("span", {}, lg);
        const sw = el("i", {}, sp); sw.style.background = css(col);
        sp.appendChild(document.createTextNode(t));
      }
    }

    function drawActual(v) {
      const host = $("panels");
      const ph = v.photo, b = ph ? ph.bounds_25831 : null;
      const pts = v.traced.flatMap((t) => t.c);
      const [x0, y0, x1, y1] = b || [Math.min(...pts.map((q) => q[0])) - 5, Math.min(...pts.map((q) => q[1])) - 5,
        Math.max(...pts.map((q) => q[0])) + 5, Math.max(...pts.map((q) => q[1])) + 5];
      const scale = 300 / Math.max(x1 - x0, y1 - y0);
      const g = frame(host, (x1 - x0) * scale, (y1 - y0) * scale, { l: 0, r: 0, t: 0, b: 0 });
      g.svg.setAttribute("aria-label", "Roof photo with the real panel blocks outlined");
      if (ph) el("image", { href: /^(data:|https?:)/.test(ph.file) ? ph.file : "data/" + ph.file, x: 0, y: 0, width: (x1 - x0) * scale, height: (y1 - y0) * scale, preserveAspectRatio: "none" }, g.svg);
      const X = (x) => (x - x0) * scale, Y = (y) => (y1 - y) * scale;
      for (const t of v.traced) {
        const d = "M" + t.c.map((q) => X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1)).join("L") + "Z";
        el("path", { d, fill: "none", stroke: "#fff", "stroke-width": 4, "stroke-linejoin": "round" }, g.svg);
        const r = el("path", { d, fill: "rgb(224 122 95 / 0.18)", stroke: css("--actual"), "stroke-width": 2, "stroke-linejoin": "round", tabindex: 0 }, g.svg);
        r.addEventListener("pointermove", (evt) => showTip(evt, "Real panel block", [{ value: fmt(t.area_m2) + " m²", label: t.name }]));
        r.addEventListener("pointerleave", hideTip);
      }
      const area = v.traced.reduce((a, t) => a + t.area_m2, 0);
      const diff = v.model_kwh_per_kwp ? (v.model_kwh_per_kwp / v.kwh_per_kwp - 1) : null;
      $("panel-note").textContent = `Outlined: ${v.traced.length} panel areas (${fmt(area)} m²) found by ${v.traced_by}. Not checked against an installer plan. ` +
        (v.model_kwh_per_kwp ? `On these spots our model gives ${fmt(v.model_kwh_per_kwp)} kWh per kWp, against ${fmt(v.kwh_per_kwp)} reported (${diff >= 0 ? "+" : ""}${pct(diff)}), from the ${v.model_panels_on_blocks} model panels inside the blocks.` : "") +
        (ph ? ` Photo: ${ph.source}.` : "");
    }

    draw();
  }

  function surplus(D) {
    const F = D.facts;
    const kind = D.meta.host_kind || "building", hl = D.meta.host_label || "The host";
    $("surplus-lede").textContent = `${hl} (a ${kind} using about ${fmt(F.host_use_kwh.v)} kWh a year) uses ${pct(F.host_self_share.v)} of the solar itself. The other ${fmt(F.surplus_kwh.v)} kWh a year is spare, and ${fmt(F.surplus_weekend_kwh.v)} kWh of it comes at weekends, when the ${kind} is closed.`;
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
    $("nb-eyebrow").textContent = `Steps 05-08 · buildings within ${fmt(D.max_distance_m)} m`;
    $("nb-lede").textContent = D.meta.reach_note || `Guests are wired directly to the host, so the tool only looks within ${fmt(D.max_distance_m)} m and takes the closest buildings that can use some of the spare solar.`;
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
    for (const h of ["Days ahead", "Model", "Same hour last week", "Typical year"]) el("th", { text: h, class: h === "Days ahead" ? "" : "n" }, hr);
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
      : `Not at today's prices. At an assumed €${fmt(F.lfp_price.v)} per kWh, no battery size pays for itself here. For the ${D.meta.host_kind || "host"} alone, a 5 kWh LFP battery would only break even at about €${fmt(F.lfp5_break_even.v)} per kWh. With ${D.buildings.length - 1} guests, ${pct(F.shared_used_share.v)} of the solar is already used without one.`;
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
      // same formula as step 08 owner_total_at_discount()
      const owner = b.host_saving + (1 - d) * b.guests_value + b.export;
      const guests = d * b.guests_value;
      const net = owner - om;
      const host = $("money-stats");
      host.replaceChildren();
      const items = [
        ["Owner's value a year", "€" + fmt(owner), "modelled", "host savings + sales + export"],
        ["Neighbours save a year", "€" + fmt(guests), "modelled", "all guests together"],
        ["Panels installed", "€" + fmt(capex), "assumption", "€1,061 per kWp, Marblanc Solar quotes"],
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

  function agreed(D) {
    const A = D.agreed;
    if (!A) return;
    $("agreed-card").hidden = false;
    const ours = D.sharing.typical.without.per_building || {};
    $("agreed-intro").textContent = `Our tool: every hour the agent sends the solar where it is needed, and guests pay the grid price minus ${pct(D.money.default_discount)}. CEP9: each member gets a fixed share of every hour's output, for free${A.per_building.host ? `, and the school keeps ${pct(A.per_building.host.share)}` : ""}. A share a member can't use that hour goes to the grid. Typical-year PVPC, without taxes.`;
    const t = $("agreed-table");
    t.replaceChildren();
    const hr = el("tr", {}, el("thead", {}, t));
    for (const h of ["Building", "Our tool: kWh from roof", "Our tool: saves €/yr", "CEP9: share", "CEP9: kWh used", "CEP9: saves €/yr"]) el("th", { text: h, class: h === "Building" ? "" : "n" }, hr);
    const tb = el("tbody", {}, t);
    const label = (id) => (D.buildings.find((b) => b.id === id) || { label: id }).label;
    for (const [id, r] of Object.entries(A.per_building)) {
      const o = ours[id] || {};
      const tr = el("tr", {}, tb);
      el("td", { text: label(id) + (r.dwellings ? ` (per home: ${fmt(r.per_dwelling_used_kwh)} kWh, €${fmt(r.per_dwelling_saving_eur)}; €${fmt(r.per_dwelling_saving_with_taxes_eur)} with taxes)` : "") }, tr);
      el("td", { class: "n", text: fmt(o.from_roof_kwh) }, tr);
      el("td", { class: "n", text: fmt(o.saving_eur) }, tr);
      el("td", { class: "n", text: pct(r.share) }, tr);
      el("td", { class: "n", text: fmt(r.used_kwh) }, tr);
      el("td", { class: "n", text: fmt(r.saving_eur) }, tr);
    }
    const tot = D.sharing.typical.without;
    $("agreed-note").textContent = `Solar used: our tool ${pct(tot.used_share)}, CEP9 terms ${pct(A.used_share)} (${fmt(A.to_grid_kwh)} kWh a year goes to the grid because a share isn't always needed). ` + (D.compare_note || "");
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
    for (const fn of [overview, property, siteMap, roof, surplus, neighbours, match, prices, battery, money, agreed, sources]) {
      try { fn(D); } catch (err) { console.error(fn.name, err); }
    }
    trackSteps();
  }

  if (window.SITE_DATA) start(window.SITE_DATA);
  else fetch("data/site_data.json").then((r) => r.json()).then(start).catch((e) => {
    document.querySelector(".wrap").prepend(Object.assign(document.createElement("p"), { className: "banner", textContent: "Could not load data/site_data.json. Run python -m step09_publish_report.export_site_data from the pipeline folder." }));
    console.error(e);
  });
})();
