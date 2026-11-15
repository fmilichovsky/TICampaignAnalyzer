// The calibration page: replays the calibration table for the state in the URL hash and lays out what changes.
//
// A classic script, opened from file:// with no network. index.js, status.js, replay.js and readout.js are loaded
// by index.html; the campaign tables are injected here. The layout is built once and then updated in place, so the
// slider keeps its focus and nothing in the left column changes size while a reference slides.
(function () {
  "use strict";

  const DATA = window.TI_CALIBRATION || { campaigns: {} };
  const Replay = window.TICalibrationReplay;
  const Readout = window.TICalibrationReadout;
  const SVG = "http://www.w3.org/2000/svg";

  const LEVEL_NAMES = { trivial: "trivial", minor: "minor", major: "major", campaign_defining: "campaign defining" };
  const LEVEL_SHORT = { trivial: "T", minor: "Mi", major: "M", campaign_defining: "CD" };
  const VERDICTS = [
    ["keeps_members", "Keeps members", "Groups whose members all stay admitted."],
    ["loses_members", "Loses members", "Groups that lose members but keep enough distinct ones to stand."],
    ["falls_apart", "Falls apart", "Groups left with too few distinct members; they leave the package."],
    ["could_become_member", "Could join", "Events that would now be admitted as members; the rule is not re-run."],
  ];
  const DIGEST_ROWS = 6;
  const RESORT_DELAY = 400;
  const STATUS_POLL = 2000;
  const STATUS_GRACE = 20000;
  const SLIDER_STEP = 0.01;
  const CHART_HEIGHT = 270;
  const CHART_MARGIN = { top: 22, right: 12, bottom: 26, left: 40 };
  const BIN = 0.1;

  // --- Small helpers -----------------------------------------------------------------------------------------

  const $ = (id) => document.getElementById(id);
  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(tag, attributes, ...children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (name === "class") node.className = value;
      else if (name === "text") node.textContent = value;
      else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
      else node.setAttribute(name, value === true ? "" : String(value));
    }
    for (const child of children) if (child !== null && child !== undefined) node.append(child);
    return node;
  }

  function svg(tag, attributes, text) {
    const node = document.createElementNS(SVG, tag);
    for (const [name, value] of Object.entries(attributes || {})) node.setAttribute(name, String(value));
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // A share or reference for reading: three significant figures, written as JavaScript writes the number.
  function fmt(value) {
    if (!Number.isFinite(value)) return "—";
    return String(Number(value.toPrecision(3)));
  }

  const plural = (count, one, many) => `${count} ${count === 1 ? one : many || `${one}s`}`;
  const signed = (number) => (number > 0 ? `+${number}` : number < 0 ? `−${-number}` : "±0");
  // Some save strings keep JSON escapes such as \u00e3; show the character they stand for.
  const labelOf = (row) => row.label.replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => String.fromCharCode(parseInt(code, 16)));
  const levelName = (level) => LEVEL_NAMES[level] || level.replace(/_/g, " ");
  const levelShort = (level) => LEVEL_SHORT[level] || level;
  const shortDate = (date) => (typeof date === "string" ? date.slice(0, 7) : "");

  function levelDot(level) {
    return el("i", { class: `dot lv-${level}`, title: levelName(level), "aria-hidden": "true" });
  }

  // --- Boot --------------------------------------------------------------------------------------------------

  function fatal(title, text) {
    $("layout").hidden = true;
    $("fatal").hidden = false;
    $("fatal-title").textContent = title;
    $("fatal-text").textContent = text;
    document.querySelector(".bar").classList.add("bar-empty");
  }

  function loadTables(names) {
    return Promise.all(
      names.map(
        (name) =>
          new Promise((resolve, reject) => {
            if (DATA.campaigns[name]) {
              resolve();
              return;
            }
            const script = document.createElement("script");
            script.src = `tables/${encodeURIComponent(name)}.js`;
            script.onload = () =>
              DATA.campaigns[name] ? resolve() : reject(new Error(`tables/${name}.js does not hold the ${name} table.`));
            script.onerror = () => reject(new Error(`tables/${name}.js could not be loaded.`));
            document.head.append(script);
          }),
      ),
    );
  }

  function boot() {
    const index = DATA.index;
    if (!Replay || !Readout) {
      fatal("The page is incomplete.", "replay.js or readout.js is missing beside index.html. Run tinarrative benchmark calibrate open again.");
      return;
    }
    if (!index) {
      fatal("No calibration table here.", "index.js is missing beside this page. Run tinarrative benchmark calibrate open to build it.");
      return;
    }
    if (index.schema_version !== Replay.SCHEMA_VERSION) {
      fatal(
        "This table is from another version.",
        `index.js has schema ${index.schema_version}; this page reads schema ${Replay.SCHEMA_VERSION}. Run tinarrative benchmark calibrate open --rebuild.`,
      );
      return;
    }
    Status.start(index);
    $("layout").setAttribute("aria-busy", "true");
    $("table-key").textContent = `Loading ${index.campaigns.join(", ")}…`;
    loadTables(index.campaigns)
      .then(() => {
        const tables = {};
        for (const name of index.campaigns) tables[name] = DATA.campaigns[name].events;
        App.init(index, tables);
      })
      .catch((error) => fatal("The table could not be read.", `${error.message} Run tinarrative benchmark calibrate open --rebuild.`));
  }

  // --- Status banner -----------------------------------------------------------------------------------------

  const Status = {
    index: null,
    timer: null,
    started: 0,

    start(index) {
      this.index = index;
      this.started = Date.now();
      $("banner-action").addEventListener("click", () => window.location.reload());
      this.show();
      this.schedule();
    },

    show() {
      const status = DATA.status;
      const banner = $("banner");
      const action = $("banner-action");
      let text = "";
      let tone = "info";
      action.hidden = true;
      if (status && status.state === "rebuilding") {
        text = "The calibration table is being rebuilt for the current code. This page shows the previous table until it is done.";
      } else if (status && status.state === "failed") {
        tone = "error";
        text = `The rebuild failed, so this page shows the previous table. ${status.message || ""}`.trim();
      } else if (status && status.state === "fresh" && status.key !== this.index.key) {
        text = "A newer calibration table is ready.";
        action.hidden = false;
      }
      if (text === "" && banner.dataset.tone === "link" && !banner.hidden) return;
      banner.hidden = text === "";
      banner.dataset.tone = tone;
      $("banner-text").textContent = text;
    },

    schedule() {
      clearTimeout(this.timer);
      const status = DATA.status;
      const rebuilding = status && status.state === "rebuilding";
      if (!rebuilding && Date.now() - this.started > STATUS_GRACE) return;
      this.timer = setTimeout(() => this.poll(), STATUS_POLL);
    },

    // Re-inject status.js: a file:// page cannot fetch, but a script tag reloads the file the CLI rewrites.
    poll() {
      for (const old of document.querySelectorAll("script[data-status]")) old.remove();
      const script = document.createElement("script");
      script.src = `status.js?poll=${Date.now()}`;
      script.dataset.status = "";
      const next = () => {
        this.show();
        this.schedule();
      };
      script.onload = next;
      script.onerror = next;
      document.head.append(script);
    },
  };

  // --- The page ----------------------------------------------------------------------------------------------

  const App = {
    index: null,
    tables: null,
    measures: [],
    levels: [],
    positions: {},
    stakedTypes: {},
    allTypes: [],
    domains: {},
    state: null,
    result: null,
    full: null,
    chosenCuts: {},
    moveOrder: [],
    moveRows: new Map(),
    expandedMove: null,
    resortTimer: null,
    hashTimer: null,
    frame: 0,
    dragging: false,
    chartWidth: 600,
    chartModel: null,
    chartCursor: -1,
    countsLayout: "",
    countRows: new Map(),

    init(index, tables) {
      this.index = index;
      this.tables = tables;
      this.measures = Object.keys(index.measures);
      this.levels = Object.keys(index.constants.level_bands);
      this.prepare();
      this.state = this.readHash(window.location.hash);
      this.build();
      this.compute();
      this.render({ resort: true });
      $("layout").setAttribute("aria-busy", "false");
      window.addEventListener("hashchange", () => {
        if (window.location.hash.slice(1) === Replay.encodeState(this.state, this.index)) return;
        this.state = this.readHash(window.location.hash);
        this.update({ resort: true, layout: true });
      });
    },

    // Everything the reference does not change: row positions, the types each measure stakes, the chart domains.
    prepare() {
      const types = new Set();
      const shares = {};
      for (const measure of this.measures) {
        this.stakedTypes[measure] = new Map();
        shares[measure] = [];
      }
      for (const [name, rows] of Object.entries(this.tables)) {
        const positions = new Map();
        rows.forEach((row, position) => {
          positions.set(row.id, position);
          types.add(row.type);
          for (const stake of row.stakes) {
            const counts = this.stakedTypes[stake.measure];
            if (!counts) continue;
            counts.set(row.type, (counts.get(row.type) || 0) + 1);
            if (stake.share > 0) shares[stake.measure].push(stake.share);
          }
        });
        this.positions[name] = positions;
      }
      this.allTypes = [...types].sort();
      for (const measure of this.measures) {
        const code = Math.log10(this.index.measures[measure].reference);
        let low = code - 1.75;
        let high = code + 1.75;
        for (const share of shares[measure]) {
          const value = Math.log10(share);
          if (value < low) low = value;
          if (value > high) high = value;
        }
        this.domains[measure] = { low: Math.floor(low), high: Math.ceil(high) };
      }
    },

    readHash(hash) {
      try {
        const state = Replay.decodeState(hash || "", this.index);
        Replay.replay(this.index, this.tables, state);
        this.hashError = "";
        return state;
      } catch (error) {
        if (!(error instanceof Replay.ReplayError)) throw error;
        this.hashError = `The link's state could not be read (${error.message}), so the page shows the code's references.`;
        return Replay.defaultState(this.index);
      }
    },

    get focus() {
      return this.state.focus || this.measures[0];
    },

    // --- Building the fixed layout ------------------------------------------------------------------------

    build() {
      const campaigns = $("campaigns");
      for (const name of this.index.campaigns) {
        campaigns.append(
          el("button", {
            type: "button",
            class: "toggle",
            "data-campaign": name,
            "aria-pressed": "true",
            text: name,
            onclick: () => {
              const on = this.state.campaigns.includes(name);
              const next = on ? this.state.campaigns.filter((item) => item !== name) : [...this.state.campaigns, name];
              this.state.campaigns = this.index.campaigns.filter((item) => next.includes(item));
              this.update({ resort: true, layout: true });
            },
          }),
        );
      }
      const constants = this.index.constants;
      $("clamp").title =
        `Clamp the stake's scale. On, a stake moves a score between ${constants.scale_min} and +${constants.scale_max} points, ` +
        "so an event moves one level at most. Off, the scale is unbounded and more cut-offs appear.";
      $("clamp").addEventListener("click", () => {
        this.state.clamp = !this.state.clamp;
        this.update({ resort: true, layout: true });
      });
      $("reset").addEventListener("click", () => {
        const fresh = Replay.defaultState(this.index);
        fresh.focus = this.state.focus;
        this.state = fresh;
        this.update({ resort: true, layout: true });
      });
      $("copy").addEventListener("click", () => this.copy());

      const chips = $("chips");
      for (const measure of this.measures) {
        const spec = this.index.measures[measure];
        chips.append(
          el(
            "button",
            {
              type: "button",
              class: "chip",
              "data-measure": measure,
              title: spec.description,
              onclick: () => this.setFocus(measure),
            },
            el("span", { class: "chip-name", text: spec.label }),
            el("span", { class: "chip-value" }),
          ),
        );
      }

      const slider = $("ref-slider");
      slider.step = String(SLIDER_STEP);
      slider.addEventListener("pointerdown", () => {
        this.dragging = true;
      });
      const release = () => {
        if (!this.dragging) return;
        this.dragging = false;
        this.settle();
      };
      window.addEventListener("pointerup", release);
      window.addEventListener("pointercancel", release);
      slider.addEventListener("input", () => {
        this.setReference(this.sliderReference(Number(slider.value)), { from: "slider" });
      });
      slider.addEventListener("keydown", () => {
        this.dragging = false;
      });
      slider.addEventListener("change", () => {
        if (!this.dragging) this.settleSoon();
      });

      const value = $("ref-value");
      const commit = () => {
        const text = value.value.trim();
        const number = /^(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/.test(text) ? Number(text) : NaN;
        if (!Number.isFinite(number) || number <= 0) {
          value.setAttribute("aria-invalid", "true");
          $("ref-error").textContent = `Enter a positive share, such as ${fmt(this.index.measures[this.focus].reference)}.`;
          return;
        }
        value.removeAttribute("aria-invalid");
        $("ref-error").textContent = "";
        this.setReference(number, { from: "field" });
        this.settle();
      };
      value.addEventListener("change", commit);
      value.addEventListener("keydown", (event) => {
        if (event.key === "Enter") commit();
        if (event.key === "Escape") {
          value.value = String(this.state.references[this.focus]);
          value.removeAttribute("aria-invalid");
          $("ref-error").textContent = "";
        }
      });
      $("ref-code").addEventListener("click", () => {
        this.setReference(this.index.measures[this.focus].reference, { from: "code" });
        this.settle();
      });

      $("type-filter").addEventListener("change", (event) => {
        const type = event.target.value;
        if (type === "__several") return;
        this.state.types = type ? [type] : [];
        this.update({ resort: true, layout: true });
      });

      const levelKey = $("level-key");
      for (const level of this.levels) {
        levelKey.append(el("span", { class: "level-key-item" }, levelDot(level), levelName(level)));
      }

      const verdicts = $("verdicts");
      for (const [verdict, label, help] of VERDICTS) {
        verdicts.append(
          el(
            "button",
            {
              type: "button",
              class: `verdict verdict-${verdict}`,
              "data-verdict": verdict,
              title: help,
              onclick: (event) => Pop.pin(event.currentTarget, () => this.verdictList(verdict, true)),
              onmouseenter: (event) => Pop.hover(event.currentTarget, () => this.verdictList(verdict, false)),
              onmouseleave: () => Pop.leave(),
              onfocus: (event) => Pop.hover(event.currentTarget, () => this.verdictList(verdict, false)),
              onblur: () => Pop.leave(),
            },
            el("span", { class: "verdict-count" }),
            el("span", { class: "verdict-label", text: label }),
          ),
        );
      }

      this.buildChart();
      this.buildTides();
      this.buildReferences();
    },

    buildChart() {
      const figure = $("chart-figure");
      const chart = $("chart");
      const resize = () => {
        const width = Math.max(320, Math.round(figure.clientWidth));
        if (width === this.chartWidth && this.chartModel) return;
        this.chartWidth = width;
        this.alignSlider();
        if (this.result) this.renderChart();
      };
      new ResizeObserver(resize).observe(figure);
      this.chartWidth = Math.max(320, Math.round(figure.clientWidth));
      this.alignSlider();
      chart.addEventListener("pointermove", (event) => this.chartPointer(event));
      chart.addEventListener("pointerleave", () => {
        this.chartHover = null;
        $("chart-readout").textContent = "";
        this.renderChart();
        Pop.leave();
      });
      chart.addEventListener("click", (event) => {
        const bin = this.binAt(event);
        if (bin >= 0 && this.chartModel.bins[bin].items.length > 0) {
          Pop.pin(this.binAnchor(bin), () => this.binList(bin, true));
        }
      });
      chart.addEventListener("keydown", (event) => this.chartKey(event));
      chart.addEventListener("blur", () => {
        this.chartCursor = -1;
        this.renderChart();
        Pop.leave();
      });
    },

    alignSlider() {
      const track = document.querySelector(".slider-track");
      track.style.paddingLeft = `${CHART_MARGIN.left - 7}px`;
      track.style.paddingRight = `${CHART_MARGIN.right - 7}px`;
    },

    buildTides() {
      for (const slot of [0, 1]) {
        const tide = $(`tide-${slot}`);
        tide.append(
          el(
            "header",
            { class: "tide-head" },
            el("span", { class: "tide-figure" }),
            el("span", { class: "tide-caption" }),
          ),
        );
        const list = el("ol", { class: "tide-rows" });
        for (let row = 0; row < 11; row += 1) {
          list.append(el("li", { class: row === 5 ? "tide-cut" : "tide-row" }));
        }
        tide.append(list);
      }
    },

    buildReferences() {
      const body = $("references");
      for (const measure of this.measures) {
        const spec = this.index.measures[measure];
        const staked = [...this.stakedTypes[measure].values()].reduce((sum, count) => sum + count, 0);
        body.append(
          el(
            "tr",
            { "data-measure": measure },
            el(
              "th",
              { scope: "row" },
              el("button", { type: "button", class: "link-button", text: spec.label, title: spec.description, onclick: () => this.setFocus(measure) }),
            ),
            el("td", { class: "num ref-current" }),
            el("td", { class: "num", text: fmt(spec.reference), title: String(spec.reference) }),
            el("td", { class: "num", text: String(staked) }),
          ),
        );
      }
      const drafts = this.index.drafts || [];
      $("drafts").textContent =
        drafts.length === 0 ? "No draft stakes are declared in this table." : `${plural(drafts.length, "draft stake")} declared.`;
    },

    // --- State changes ------------------------------------------------------------------------------------

    sliderReference(position) {
      const code = this.index.measures[this.focus].reference;
      if (Math.abs(position - Math.log10(code)) < SLIDER_STEP / 2) return code;
      return Number(Math.pow(10, position).toPrecision(3));
    },

    setReference(value, { from }) {
      this.state.references = Object.assign({}, this.state.references, { [this.focus]: value });
      this.update({ resort: from !== "slider", from });
    },

    setFocus(measure) {
      this.state.focus = measure === this.measures[0] ? null : measure;
      $("ref-error").textContent = "";
      $("ref-value").removeAttribute("aria-invalid");
      this.update({ resort: true, layout: true });
    },

    setType(type) {
      const only = this.state.types.length === 1 && this.state.types[0] === type;
      this.state.types = only ? [] : [type];
      this.update({ resort: true, layout: true });
    },

    settleSoon() {
      clearTimeout(this.resortTimer);
      this.resortTimer = setTimeout(() => this.settle(), RESORT_DELAY);
    },

    settle() {
      clearTimeout(this.resortTimer);
      this.renderMoves({ resort: true });
      this.writeHash();
    },

    update(options) {
      this.pending = Object.assign(this.pending || {}, options);
      if (this.frame) return;
      this.frame = window.requestAnimationFrame(() => {
        this.frame = 0;
        const pending = this.pending;
        this.pending = null;
        this.compute();
        this.render(pending);
      });
    },

    compute() {
      this.result = Replay.replay(this.index, this.tables, this.state);
      this.full =
        this.state.types.length === 0
          ? this.result
          : Replay.replay(this.index, this.tables, Object.assign({}, this.state, { types: [] }));
      this.lookup = null;
    },

    writeHash() {
      clearTimeout(this.hashTimer);
      const hash = Replay.encodeState(this.state, this.index);
      const url = `${window.location.pathname}${window.location.search}${hash ? `#${hash}` : ""}`;
      if (window.location.hash.slice(1) !== hash) window.history.replaceState(null, "", url);
    },

    writeHashSoon() {
      clearTimeout(this.hashTimer);
      this.hashTimer = setTimeout(() => this.writeHash(), 250);
    },

    // --- Rendering ----------------------------------------------------------------------------------------

    render(options = {}) {
      this.renderHeader();
      this.renderControl(options);
      this.renderChart();
      this.renderTides();
      this.renderCounts(options);
      this.renderReferences();
      this.renderTotals();
      this.renderMembers();
      this.renderMoves(options);
      if (options.from === "slider") this.writeHashSoon();
      else this.writeHash();
      Pop.refresh();
    },

    renderHeader() {
      for (const button of document.querySelectorAll("#campaigns .toggle")) {
        button.setAttribute("aria-pressed", String(this.state.campaigns.includes(button.dataset.campaign)));
      }
      $("clamp").setAttribute("aria-checked", String(this.state.clamp));
      $("clamp-state").textContent = this.state.clamp ? "on" : "off";
      const atCode = Replay.encodeState(Object.assign({}, this.state, { focus: null }), this.index) === "";
      $("reset").disabled = atCode;
      $("table-key").textContent = `Table ${this.index.key.slice(0, 8)} · ${this.index.extracted_at.slice(0, 16).replace("T", " ")}`;
      $("table-key").title = `Cache key ${this.index.key}, extracted ${this.index.extracted_at}`;
      if (this.hashError) {
        const banner = $("banner");
        if (banner.hidden) {
          banner.hidden = false;
          banner.dataset.tone = "link";
          $("banner-text").textContent = this.hashError;
        }
        this.hashError = "";
      }
    },

    renderControl(options) {
      const focus = this.focus;
      for (const chip of document.querySelectorAll("#chips .chip")) {
        const measure = chip.dataset.measure;
        const value = this.state.references[measure];
        const changed = value !== this.index.measures[measure].reference;
        chip.setAttribute("aria-pressed", String(measure === focus));
        chip.classList.toggle("chip-changed", changed);
        chip.querySelector(".chip-value").textContent = fmt(value);
      }
      const reference = this.state.references[focus];
      const code = this.index.measures[focus].reference;
      const domain = this.domains[focus];
      const slider = $("ref-slider");
      slider.min = String(domain.low);
      slider.max = String(domain.high);
      if (options.from !== "slider") slider.value = String(Math.log10(reference));
      slider.setAttribute("aria-valuetext", `${fmt(reference)} (code's ${fmt(code)})`);
      const field = $("ref-value");
      if (options.from !== "field" && document.activeElement !== field) field.value = String(reference);
      else if (options.from === "field") field.value = String(reference);
      $("ref-code").disabled = reference === code;
      $("ref-code").title = `Set ${this.index.measures[focus].label} back to the code's ${code}`;
      const [low, high] = this.windowEdges();
      $("ref-window").textContent = `window ${fmt(reference * Math.pow(10, low))} – ${fmt(reference * Math.pow(10, high))}`;
      if (options.layout || !this.typeOptions) this.renderTypeFilter();
    },

    renderTypeFilter() {
      const select = $("type-filter");
      const focus = this.focus;
      const staked = [...this.stakedTypes[focus].keys()].sort();
      const stakedSet = new Set(staked);
      const others = this.allTypes.filter((type) => !stakedSet.has(type));
      select.replaceChildren(el("option", { value: "", text: "All types" }));
      if (this.state.types.length > 1) {
        select.append(el("option", { value: "__several", text: `${this.state.types.length} types (from the link)` }));
      }
      if (staked.length > 0) {
        select.append(el("optgroup", { label: `Staked by ${this.index.measures[focus].label}` }, ...staked.map((type) => el("option", { value: type, text: type }))));
      }
      select.append(el("optgroup", { label: "Other types" }, ...others.map((type) => el("option", { value: type, text: type }))));
      select.value = this.state.types.length > 1 ? "__several" : this.state.types[0] || "";
      select.classList.toggle("type-filter-on", this.state.types.length > 0);
      this.typeOptions = true;
    },

    windowEdges() {
      const offsets = Replay.cutoffOffsets(this.index.constants, true);
      const below = offsets.filter((offset) => offset < 0);
      const above = offsets.filter((offset) => offset > 0);
      return [below.length ? Math.max(...below) : 0, above.length ? Math.min(...above) : 0];
    },

    // --- The window chart -----------------------------------------------------------------------------------

    chartData() {
      const focus = this.focus;
      const key = `${focus}|${this.state.campaigns.join(",")}|${this.state.types.join(",")}`;
      if (this.chartModel && this.chartModel.key === key) return this.chartModel;
      const domain = this.domains[focus];
      const count = Math.round((domain.high - domain.low) / BIN);
      const bins = Array.from({ length: count }, (_, i) => ({ low: domain.low + i * BIN, items: [] }));
      const types = new Set(this.state.types);
      let unshared = 0;
      for (const name of this.state.campaigns) {
        this.tables[name].forEach((row, position) => {
          const stake = row.stakes.find((item) => item.measure === focus);
          if (!stake) return;
          if (!(stake.share > 0)) {
            unshared += 1;
            return;
          }
          const place = Math.floor((Math.log10(stake.share) - domain.low) / BIN + 1e-9);
          const bin = bins[Math.max(0, Math.min(count - 1, place))];
          bin.items.push({ campaign: name, position, share: stake.share, chosen: types.size === 0 || types.has(row.type) });
        });
      }
      let max = 0;
      for (const bin of bins) {
        bin.items.sort((a, b) => b.share - a.share);
        max = Math.max(max, bin.items.length);
      }
      this.chartModel = { key, domain, bins, max, unshared };
      return this.chartModel;
    },

    renderChart() {
      const model = this.chartData();
      const chart = $("chart");
      const width = this.chartWidth;
      const height = CHART_HEIGHT;
      const plotLeft = CHART_MARGIN.left;
      const plotRight = width - CHART_MARGIN.right;
      const plotTop = CHART_MARGIN.top;
      const plotBottom = height - CHART_MARGIN.bottom;
      const span = model.domain.high - model.domain.low;
      const x = (log) => plotLeft + ((log - model.domain.low) / span) * (plotRight - plotLeft);
      const yMax = niceMax(model.max);
      const y = (count) => plotBottom - (count / yMax) * (plotBottom - plotTop);
      const reference = this.state.references[this.focus];
      const code = this.index.measures[this.focus].reference;
      const [low, high] = this.windowEdges();
      const lowCut = reference * Math.pow(10, low);
      const highCut = reference * Math.pow(10, high);
      const filtered = this.state.types.length > 0;

      chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
      chart.setAttribute("width", String(width));
      chart.setAttribute("height", String(height));
      const nodes = [];

      // The window band, clipped to the plot.
      const bandLeft = Math.max(plotLeft, x(Math.log10(lowCut)));
      const bandRight = Math.min(plotRight, x(Math.log10(highCut)));
      if (bandRight > bandLeft) {
        nodes.push(svg("rect", { class: "band", x: bandLeft, y: plotTop, width: bandRight - bandLeft, height: plotBottom - plotTop }));
      }

      // Gridlines and the count axis.
      for (const tick of countTicks(yMax)) {
        nodes.push(svg("line", { class: "grid", x1: plotLeft, x2: plotRight, y1: y(tick), y2: y(tick) }));
        nodes.push(svg("text", { class: "axis-text", x: plotLeft - 6, y: y(tick) + 3.5, "text-anchor": "end" }, String(tick)));
      }

      // Bars: each bin stacks drop, keep and rise; with a type filter the other types sit lighter on top.
      const binWidth = (plotRight - plotLeft) / model.bins.length;
      model.bins.forEach((bin, i) => {
        if (bin.items.length === 0) return;
        const counts = { drop: [0, 0], keep: [0, 0], rise: [0, 0] };
        for (const item of bin.items) {
          const side = item.share < lowCut ? "drop" : item.share > highCut ? "rise" : "keep";
          counts[side][item.chosen ? 0 : 1] += 1;
        }
        let stacked = 0;
        const left = plotLeft + i * binWidth + 0.5;
        const barWidth = Math.max(1, binWidth - 1);
        for (const layer of [0, 1]) {
          for (const side of ["drop", "keep", "rise"]) {
            const n = counts[side][layer];
            if (n === 0) continue;
            const top = y(stacked + n);
            nodes.push(
              svg("rect", {
                class: `bar bar-${side}${layer === 1 && filtered ? " bar-other" : ""}`,
                x: left,
                y: top,
                width: barWidth,
                height: Math.max(0.5, y(stacked) - top),
              }),
            );
            stacked += n;
          }
        }
        if (i === this.chartCursor || (this.chartHover && this.chartHover.bin === i)) {
          nodes.push(svg("rect", { class: "bar-focus", x: left - 0.5, y: y(stacked) - 0.5, width: barWidth + 1, height: plotBottom - y(stacked) + 1 }));
        }
      });

      // The share axis: one tick per decade.
      nodes.push(svg("line", { class: "axis", x1: plotLeft, x2: plotRight, y1: plotBottom + 0.5, y2: plotBottom + 0.5 }));
      for (let decade = model.domain.low; decade <= model.domain.high; decade += 1) {
        const at = x(decade);
        nodes.push(svg("line", { class: "axis", x1: at, x2: at, y1: plotBottom, y2: plotBottom + 4 }));
        const label = svg("text", { class: "axis-text", x: at, y: plotBottom + 17, "text-anchor": "middle" });
        appendDecade(label, decade);
        nodes.push(label);
      }

      // The cut-offs of the current state: the window's two, and with the clamp off any further ones.
      for (const cutoff of this.result.cutoffs[this.focus] || []) {
        const at = x(Math.log10(cutoff.share));
        if (at < plotLeft || at > plotRight) continue;
        nodes.push(svg("line", { class: "cut", x1: at, x2: at, y1: plotTop - 4, y2: plotBottom }));
      }

      // The code's reference and the current one.
      const codeAt = x(Math.log10(code));
      if (codeAt >= plotLeft && codeAt <= plotRight && code !== reference) {
        nodes.push(svg("line", { class: "code-line", x1: codeAt, x2: codeAt, y1: plotTop, y2: plotBottom }));
        nodes.push(svg("text", { class: "code-text", x: codeAt + 4, y: plotTop + 10, "text-anchor": "start" }, "code's"));
      }
      const refAt = x(Math.log10(reference));
      if (refAt >= plotLeft && refAt <= plotRight) {
        nodes.push(svg("line", { class: "ref-line", x1: refAt, x2: refAt, y1: plotTop - 4, y2: plotBottom }));
        const anchor = refAt < plotLeft + 40 ? "start" : refAt > plotRight - 40 ? "end" : "middle";
        nodes.push(svg("text", { class: "ref-text", x: refAt, y: plotTop - 8, "text-anchor": anchor }, fmt(reference)));
      }

      // The pointer's share.
      if (this.chartHover) {
        const at = this.chartHover.x;
        nodes.push(svg("line", { class: "pointer-line", x1: at, x2: at, y1: plotTop, y2: plotBottom }));
      }
      chart.replaceChildren(...nodes);
      chart.setAttribute(
        "aria-label",
        `Share distribution of ${this.index.measures[this.focus].label}: ${plural(
          model.bins.reduce((sum, bin) => sum + bin.items.length, 0),
          "staked event",
        )}, reference ${fmt(reference)}, window ${fmt(lowCut)} to ${fmt(highCut)}. Arrow keys step through the bars.`,
      );
      this.chartGeometry = { plotLeft, plotRight, binWidth, x, y, span };
    },

    binAt(event) {
      const geometry = this.chartGeometry;
      const box = $("chart").getBoundingClientRect();
      const px = ((event.clientX - box.left) / box.width) * this.chartWidth;
      if (px < geometry.plotLeft || px > geometry.plotRight) return -1;
      return Math.min(this.chartModel.bins.length - 1, Math.floor((px - geometry.plotLeft) / geometry.binWidth));
    },

    binAnchor(bin) {
      const box = $("chart").getBoundingClientRect();
      const geometry = this.chartGeometry;
      const scale = box.width / this.chartWidth;
      const left = box.left + (geometry.plotLeft + bin * geometry.binWidth) * scale;
      return { getBoundingClientRect: () => ({ left, right: left + geometry.binWidth * scale, top: box.top + CHART_MARGIN.top, bottom: box.bottom - CHART_MARGIN.bottom }) };
    },

    chartPointer(event) {
      const geometry = this.chartGeometry;
      if (!geometry) return;
      const box = $("chart").getBoundingClientRect();
      const px = ((event.clientX - box.left) / box.width) * this.chartWidth;
      if (px < geometry.plotLeft || px > geometry.plotRight) {
        this.chartHover = null;
        $("chart-readout").textContent = "";
        this.renderChart();
        Pop.leave();
        return;
      }
      const share = Math.pow(10, this.chartModel.domain.low + ((px - geometry.plotLeft) / (geometry.plotRight - geometry.plotLeft)) * geometry.span);
      const bin = this.binAt(event);
      const count = bin >= 0 ? this.chartModel.bins[bin].items.length : 0;
      const changed = !this.chartHover || this.chartHover.bin !== bin;
      this.chartHover = { x: px, bin };
      $("chart-readout").textContent = `share ${fmt(share)} · ${plural(count, "event")} in this bar`;
      this.renderChart();
      if (changed) {
        if (count > 0) Pop.hover(this.binAnchor(bin), () => this.binList(bin, false));
        else Pop.leave();
      }
    },

    chartKey(event) {
      const bins = this.chartModel.bins;
      const filled = bins.map((bin, i) => (bin.items.length > 0 ? i : -1)).filter((i) => i >= 0);
      if (filled.length === 0) return;
      let next = this.chartCursor;
      if (event.key === "ArrowRight") next = filled.find((i) => i > this.chartCursor) ?? filled[filled.length - 1];
      else if (event.key === "ArrowLeft") next = [...filled].reverse().find((i) => i < this.chartCursor) ?? filled[0];
      else if (event.key === "Home") next = filled[0];
      else if (event.key === "End") next = filled[filled.length - 1];
      else if ((event.key === "Enter" || event.key === " ") && this.chartCursor >= 0) {
        event.preventDefault();
        Pop.pin(this.binAnchor(this.chartCursor), () => this.binList(this.chartCursor, true));
        return;
      } else return;
      event.preventDefault();
      this.chartCursor = next;
      this.renderChart();
      Pop.hover(this.binAnchor(next), () => this.binList(next, false));
    },

    binList(bin, full) {
      const model = this.chartModel;
      const items = model.bins[bin].items.map((item) => this.eventItem(item.campaign, item.position, this.full));
      const low = Math.pow(10, model.domain.low + bin * BIN);
      return { title: `Shares ${fmt(low)} – ${fmt(low * Math.pow(10, BIN))}`, note: plural(items.length, "event"), items, full };
    },

    // --- Cut-offs as a tide table -------------------------------------------------------------------------

    shownCutoffs() {
      const cutoffs = this.result.cutoffs[this.focus] || [];
      if (cutoffs.length <= 2) return cutoffs;
      const chosen = this.chosenCuts[this.focus];
      if (chosen) {
        const picked = cutoffs.filter((cutoff) => chosen.includes(cutoff.offset));
        if (picked.length === 2) return picked;
      }
      const [low, high] = this.windowEdges();
      const inside = cutoffs.filter((cutoff) => cutoff.offset === low || cutoff.offset === high);
      return inside.length === 2 ? inside : cutoffs.slice(0, 2);
    },

    renderTides() {
      const cutoffs = this.result.cutoffs[this.focus] || [];
      const shown = this.shownCutoffs();
      const chips = $("cutoff-chips");
      if (cutoffs.length > 2) {
        chips.replaceChildren(
          ...cutoffs.map((cutoff) =>
            el("button", {
              type: "button",
              class: "chip chip-small",
              "aria-pressed": String(shown.includes(cutoff)),
              title: `Cut-off at ${cutoff.share} (reference × 10^${cutoff.offset})`,
              text: fmt(cutoff.share),
              onclick: () => this.toggleCut(cutoff.offset),
            }),
          ),
        );
      } else {
        chips.replaceChildren(el("span", { class: "section-note", text: "Five events on each side of each cut-off" }));
      }
      [0, 1].forEach((slot) => this.renderTide($(`tide-${slot}`), shown[slot] || null, slot));
    },

    toggleCut(offset) {
      const shown = this.shownCutoffs().map((cutoff) => cutoff.offset);
      if (shown.includes(offset)) return;
      // The clicked cut-off replaces the one picked longest ago.
      const last = this.chosenCuts[this.focus] ? this.chosenCuts[this.focus][1] : shown[1];
      this.chosenCuts[this.focus] = [shown.includes(last) ? last : shown[1], offset];
      this.renderTides();
    },

    renderTide(tide, cutoff, slot) {
      const figure = tide.querySelector(".tide-figure");
      const caption = tide.querySelector(".tide-caption");
      const rows = tide.querySelectorAll(".tide-rows > li");
      if (!cutoff) {
        figure.textContent = "—";
        caption.textContent = slot === 0 ? "No lower cut-off" : "No upper cut-off";
        rows.forEach((row, i) => (i === 5 ? row.replaceChildren() : this.fillTideRow(row, null)));
        tide.classList.add("tide-empty");
        return;
      }
      tide.classList.remove("tide-empty");
      figure.textContent = fmt(cutoff.share);
      figure.title = String(cutoff.share);
      const levels = Math.round((Math.abs(cutoff.offset) + 1.25) / 2.5);
      const direction = cutoff.offset < 0 ? "below drops" : "above rises";
      const amount = levels === 1 ? "a level" : `${["", "", "two", "three"][levels] || levels} levels`;
      caption.textContent = `reference ${cutoff.offset < 0 ? "÷" : "×"} ${fmt(Math.pow(10, Math.abs(cutoff.offset)))} · ${direction} ${amount}`;
      caption.title = `A mid-band base ${direction.replace("below ", "").replace("above ", "")} ${amount} past this share.`;
      // Shares descend down the column, as on a scale: the five above, the cut, the five below.
      const above = [...cutoff.above].sort((a, b) => b.share - a.share);
      const below = [...cutoff.below].sort((a, b) => b.share - a.share);
      const neighbours = this.index.constants.neighbours;
      for (let i = 0; i < 5; i += 1) {
        this.fillTideRow(rows[i], above[i - (Math.min(5, neighbours) - above.length)] || null, cutoff);
        this.fillTideRow(rows[6 + i], below[i] || null, cutoff);
      }
      rows[5].replaceChildren(el("span", { class: "tide-cut-label", text: `${cutoff.above.length} above · ${cutoff.below.length} below shown` }));
    },

    fillTideRow(row, item, cutoff) {
      if (!item) {
        row.className = "tide-row tide-row-blank";
        row.replaceChildren(el("span", { class: "tide-share", text: "" }), el("span", { class: "tide-label", text: " " }));
        row.removeAttribute("title");
        return;
      }
      const table = this.tables[item.campaign];
      const tableRow = table[this.positions[item.campaign].get(item.id)];
      const dimmed = this.state.types.length > 0 && !this.state.types.includes(item.type);
      row.className = `tide-row${dimmed ? " dim" : ""}`;
      const moved = item.level !== item.oracle_level;
      row.replaceChildren(
        ...[
        el("span", { class: "tide-share", text: fmt(item.share) }),
        levelDot(item.level),
        el("span", { class: "tide-label", text: tableRow ? labelOf(tableRow) : item.id }),
        item.decisive ? null : this.citedBadge(item.campaign, tableRow, item.decided_by),
        el("span", { class: `tide-change${moved ? " moved" : ""}`, text: moved ? `${levelShort(item.oracle_level)}→${levelShort(item.level)}` : levelShort(item.level) }),
        el("span", { class: "tide-meta", text: `${item.campaign.slice(0, 4)} ${shortDate(tableRow && tableRow.date)}` }),
        ].filter(Boolean),
      );
      row.title = `${tableRow ? labelOf(tableRow) : item.id}\n${item.type} · share ${item.share} · score ${item.score} · ${levelName(item.level)} (code: ${levelName(item.oracle_level)})\n${item.campaign} ${tableRow && tableRow.date ? tableRow.date.slice(0, 10) : ""}`;
    },

    citedBadge(campaign, row, decidedBy) {
      const decider = this.tables[campaign][this.positions[campaign].get(decidedBy)];
      const label = decider ? labelOf(decider) : decidedBy;
      const stake = decider && decider.stakes.length ? `${decider.stakes[0].measure} stake` : "base level";
      const text = `Set by the cited ${label} (${stake}), not by this event's own stake.`;
      return el("span", { class: "badge", title: text, "aria-label": text, text: "cited" });
    },

    // --- Level counts -----------------------------------------------------------------------------------------

    renderCounts(options) {
      const focus = this.focus;
      const list = $("counts");
      const layout = focus;
      if (this.countsLayout !== layout) {
        this.countsLayout = layout;
        this.countRows.clear();
        // Ordered by the type's staked rows in the whole table: the reference never reorders them.
        const types = [...this.stakedTypes[focus].entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
        const rows = types.map(([type]) => {
          const segments = this.levels.map((level) =>
            el("button", {
              type: "button",
              class: `segment lv-${level}`,
              "data-level": level,
              onclick: (event) => Pop.pin(event.currentTarget, () => this.countList(type, level, true)),
              onmouseenter: (event) => Pop.hover(event.currentTarget, () => this.countList(type, level, false)),
              onmouseleave: () => Pop.leave(),
              onfocus: (event) => Pop.hover(event.currentTarget, () => this.countList(type, level, false)),
              onblur: () => Pop.leave(),
            }),
          );
          const baseline = this.levels.map((level) => el("i", { class: `base lv-${level}` }));
          const row = el(
            "div",
            { class: "count-row" },
            el("button", { type: "button", class: "type-button", text: type, title: `Filter by ${type}`, onclick: () => this.setType(type) }),
            el("div", { class: "count-bars" }, el("div", { class: "count-bar" }, ...segments), el("div", { class: "count-base" }, ...baseline)),
            el("span", { class: "count-total num" }),
            el("span", { class: "count-change num" }),
          );
          this.countRows.set(type, { row, segments, baseline });
          return row;
        });
        list.replaceChildren(...rows);
        if (rows.length === 0) list.append(el("p", { class: "empty", text: "No event type carries this stake." }));
        list.scrollTop = 0;
      }
      const counts = this.levelCounts(this.full);
      for (const [type, parts] of this.countRows) {
        const entry = counts.get(type);
        const replay = entry ? entry.replay : {};
        const baseline = entry ? entry.baseline : {};
        const total = this.levels.reduce((sum, level) => sum + (replay[level] || 0), 0);
        const baseTotal = this.levels.reduce((sum, level) => sum + (baseline[level] || 0), 0);
        let moved = 0;
        this.levels.forEach((level, i) => {
          const n = replay[level] || 0;
          const b = baseline[level] || 0;
          moved += Math.max(0, n - b);
          const segment = parts.segments[i];
          segment.style.flexBasis = total ? `${(n / total) * 100}%` : "0%";
          segment.hidden = n === 0;
          segment.setAttribute("aria-label", `${type}: ${n} ${levelName(level)} (code: ${b})`);
          segment.textContent = n / Math.max(1, total) > 0.12 ? String(n) : "";
          parts.baseline[i].style.flexBasis = baseTotal ? `${(b / baseTotal) * 100}%` : "0%";
        });
        const dimmed = (this.state.types.length > 0 && !this.state.types.includes(type)) || total + baseTotal === 0;
        parts.row.classList.toggle("dim", dimmed);
        parts.row.classList.toggle("count-row-chosen", this.state.types.includes(type));
        parts.row.querySelector(".count-total").textContent = String(total);
        const change = parts.row.querySelector(".count-change");
        change.textContent = moved ? `${moved} moved` : "";
        change.classList.toggle("moved", moved > 0);
      }
    },

    levelCounts(result) {
      const summed = new Map();
      for (const campaign of Object.values(result.campaigns)) {
        for (const [type, counts] of Object.entries(campaign.level_counts)) {
          const entry = summed.get(type) || { replay: {}, baseline: {} };
          for (const level of this.levels) {
            entry.replay[level] = (entry.replay[level] || 0) + counts.replay[level];
            entry.baseline[level] = (entry.baseline[level] || 0) + counts.baseline[level];
          }
          summed.set(type, entry);
        }
      }
      return summed;
    },

    countList(type, level, full) {
      const items = [];
      for (const name of this.full.state.campaigns) {
        const fallen = this.fallen(this.full, name);
        this.full.campaigns[name].events.forEach((event, position) => {
          const row = this.tables[name][position];
          if (row.type === type && event.level === level && !fallen.has(event.id)) items.push(this.eventItem(name, position, this.full));
        });
      }
      items.sort(byShare);
      return { title: `${type} · ${levelName(level)}`, note: plural(items.length, "event"), items, full };
    },

    // --- References and drafts --------------------------------------------------------------------------------

    renderReferences() {
      for (const row of document.querySelectorAll("#references tr")) {
        const measure = row.dataset.measure;
        const value = this.state.references[measure];
        const changed = value !== this.index.measures[measure].reference;
        const cell = row.querySelector(".ref-current");
        cell.textContent = fmt(value);
        cell.title = String(value);
        row.classList.toggle("changed", changed);
        row.classList.toggle("focused", measure === this.focus);
      }
    },

    // --- Totals and members -----------------------------------------------------------------------------------

    renderTotals() {
      const totals = this.result.totals;
      const pkg = totals.package;
      $("total-moved").replaceChildren(el("span", { class: "figure", text: String(totals.events_moved) }));
      $("total-package").replaceChildren(
        el("span", { class: "figure", text: String(pkg.replay) }),
        el("span", { class: `figure-change${pkg.change ? " moved" : ""}`, text: signed(pkg.change) }),
        el("span", { class: "figure-note", text: `from ${pkg.baseline}, ${levelName(this.index.constants.package_level)} or above` }),
      );
      $("total-members").replaceChildren(el("span", { class: "figure", text: String(totals.members_changed) }));
    },

    memberTypes() {
      const types = new Set();
      for (const gate of this.index.member_gates) {
        for (const type of gate.group_types) types.add(type);
        types.add(gate.member_type);
      }
      return types;
    },

    renderMembers() {
      const counts = {};
      for (const campaign of Object.values(this.result.campaigns)) {
        for (const member of campaign.members) counts[member.verdict] = (counts[member.verdict] || 0) + 1;
      }
      const memberTypes = this.memberTypes();
      const outside = this.state.types.length > 0 && !this.state.types.some((type) => memberTypes.has(type));
      for (const button of document.querySelectorAll("#verdicts .verdict")) {
        const n = counts[button.dataset.verdict] || 0;
        button.querySelector(".verdict-count").textContent = outside ? "—" : String(n);
        button.disabled = outside || n === 0;
        button.classList.toggle("verdict-active", !outside && n > 0 && button.dataset.verdict !== "keeps_members");
      }
      $("members-note").textContent = outside
        ? `No member gate for ${this.state.types.join(", ")}`
        : this.index.member_gates.map((gate) => `${gate.group_types.join(", ")}: at least ${gate.minimum} distinct members`).join("; ");
    },

    verdictList(verdict, full) {
      const items = [];
      for (const [name, campaign] of Object.entries(this.result.campaigns)) {
        for (const member of campaign.members) {
          if (member.verdict !== verdict) continue;
          const item = this.eventItem(name, this.positions[name].get(member.id), this.result);
          const detail = verdict === "could_become_member" ? "" : `${member.kept.length} kept, ${member.lost.length} lost, ${member.distinct} distinct of ${member.minimum}`;
          item.note = detail + (member.stale_stake ? " · stale stake" : "");
          items.push(item);
        }
      }
      items.sort(byShare);
      const label = VERDICTS.find(([key]) => key === verdict)[1];
      return { title: label, note: plural(items.length, "event"), items, full };
    },

    // --- What moves -------------------------------------------------------------------------------------------

    moveKey: (move) => `${move.type}|${move.from_level}|${move.to_level}`,

    renderMoves({ resort } = {}) {
      const list = $("moves");
      const moves = this.result.moves;
      const byKey = new Map(moves.map((move) => [this.moveKey(move), move]));
      if (resort || this.moveOrder.length === 0) {
        this.moveOrder = moves.map((move) => this.moveKey(move));
      } else {
        for (const move of moves) {
          const key = this.moveKey(move);
          if (!this.moveOrder.includes(key)) this.moveOrder.push(key);
        }
      }
      const before = resort && !reducedMotion() ? this.rects() : null;
      const maxCount = Math.max(1, ...moves.map((move) => move.count));
      const keep = new Set(this.moveOrder);
      for (const [key, row] of this.moveRows) {
        if (!keep.has(key)) {
          row.remove();
          this.moveRows.delete(key);
        }
      }
      let previous = null;
      for (const key of this.moveOrder) {
        const move = byKey.get(key);
        let row = this.moveRows.get(key);
        if (!row) {
          row = this.moveRow(key);
          this.moveRows.set(key, row);
        }
        this.fillMove(row, key, move, maxCount);
        const place = previous ? previous.nextSibling : list.firstChild;
        if (place !== row) list.insertBefore(row, place);
        previous = row;
      }
      if (this.expandedMove && !this.moveRows.has(this.expandedMove)) this.expandedMove = null;
      $("moves-empty").hidden = moves.length > 0;
      list.hidden = this.moveOrder.length === 0;
      const via = moves.reduce((sum, move) => sum + move.via_cited, 0);
      $("moves-note").textContent = moves.length
        ? `${plural(moves.length, "change")} · ${plural(this.result.totals.events_moved, "event")}${via ? `, ${via} via a cited event` : ""}`
        : "";
      if (before) this.glide(before);
    },

    moveRow(key) {
      const [type] = key.split("|");
      const body = el(
        "button",
        {
          type: "button",
          class: "move-main",
          "aria-expanded": "false",
          onclick: () => this.toggleMove(key),
          onmouseenter: (event) => this.expandedMove !== key && Pop.hover(event.currentTarget, () => this.moveList(key, false)),
          onmouseleave: () => Pop.leave(),
          onfocus: (event) => this.expandedMove !== key && Pop.hover(event.currentTarget, () => this.moveList(key, false)),
          onblur: () => Pop.leave(),
        },
        el("span", { class: "move-change" }),
        el("span", { class: "move-count num" }),
        el("span", { class: "move-via num" }),
        el("span", { class: "move-bar" }, el("i")),
      );
      return el(
        "div",
        { class: "move", "data-key": key },
        el("div", { class: "move-line" }, el("button", { type: "button", class: "type-button", text: type, title: `Filter by ${type}`, onclick: () => this.setType(type) }), body),
        el("div", { class: "move-detail", hidden: true }),
      );
    },

    fillMove(row, key, move, maxCount) {
      const [type, from, to] = key.split("|");
      const count = move ? move.count : 0;
      const rise = this.levels.indexOf(to) > this.levels.indexOf(from);
      row.classList.toggle("move-zero", !move);
      row.classList.toggle("dim", this.state.types.length > 0 && !this.state.types.includes(type));
      const change = row.querySelector(".move-change");
      change.replaceChildren(levelDot(from), el("span", { text: `${levelShort(from)}→${levelShort(to)}` }), levelDot(to));
      change.title = `${levelName(from)} → ${levelName(to)}`;
      row.querySelector(".move-count").textContent = String(count);
      const via = row.querySelector(".move-via");
      via.textContent = move && move.via_cited ? String(move.via_cited) : "";
      via.title = move && move.via_cited ? `${move.via_cited} of these took their level from a cited event` : "";
      const bar = row.querySelector(".move-bar i");
      bar.style.width = `${(count / maxCount) * 100}%`;
      bar.className = rise ? "rise" : "drop";
      row.querySelector(".move-main").setAttribute("aria-label", `${type}, ${levelName(from)} to ${levelName(to)}: ${plural(count, "event")}${move && move.via_cited ? `, ${move.via_cited} via a cited event` : ""}`);
      const detail = row.querySelector(".move-detail");
      const open = this.expandedMove === key && move;
      row.querySelector(".move-main").setAttribute("aria-expanded", String(Boolean(open)));
      row.classList.toggle("move-open", Boolean(open));
      if (open) {
        detail.hidden = false;
        detail.replaceChildren(listBody(this.moveList(key, true), () => this.toggleMove(key)));
      } else if (!detail.hidden) {
        detail.hidden = true;
        detail.replaceChildren();
      }
    },

    toggleMove(key) {
      Pop.close();
      this.expandedMove = this.expandedMove === key ? null : key;
      this.renderMoves({});
    },

    moveList(key, full) {
      const [type, from, to] = key.split("|");
      const items = [];
      for (const name of this.result.state.campaigns) {
        const fallen = this.fallen(this.result, name);
        this.result.campaigns[name].events.forEach((event, position) => {
          const row = this.tables[name][position];
          if (row.type === type && row.level === from && event.level === to && !fallen.has(event.id)) {
            items.push(this.eventItem(name, position, this.result));
          }
        });
      }
      items.sort(byShare);
      return { title: `${type} · ${levelName(from)} → ${levelName(to)}`, note: plural(items.length, "event"), items, full };
    },

    rects() {
      const rects = new Map();
      for (const [key, row] of this.moveRows) rects.set(key, row.getBoundingClientRect().top);
      return rects;
    },

    // FLIP: rows that changed place glide from where they were.
    glide(before) {
      for (const [key, row] of this.moveRows) {
        const was = before.get(key);
        if (was === undefined) continue;
        const delta = was - row.getBoundingClientRect().top;
        if (Math.abs(delta) < 1) continue;
        row.animate([{ transform: `translateY(${delta}px)` }, { transform: "translateY(0)" }], {
          duration: 220,
          easing: "cubic-bezier(0.16, 1, 0.3, 1)",
        });
      }
    },

    // --- Events -----------------------------------------------------------------------------------------------

    fallen(result, name) {
      return new Set(result.campaigns[name].members.filter((member) => member.verdict === "falls_apart").map((member) => member.id));
    },

    eventItem(campaign, position, result) {
      const row = this.tables[campaign][position];
      const event = result.campaigns[campaign] ? result.campaigns[campaign].events[position] : null;
      const stake = row.stakes.find((item) => item.measure === this.focus) || row.stakes[0] || null;
      return {
        campaign,
        row,
        level: event ? event.level : row.level,
        decidedBy: event ? event.decided_by : row.id,
        share: stake ? stake.share : null,
        measure: stake ? stake.measure : null,
      };
    },

    eventLine(item) {
      const moved = item.level !== item.row.level;
      return el(
        "li",
        { class: "event", title: `${labelOf(item.row)}\n${item.row.id}` },
        el("span", { class: "event-share num", text: item.share === null ? "—" : fmt(item.share), title: item.measure ? `${item.measure} share ${item.share}` : "No stake of its own" }),
        levelDot(item.level),
        el("span", { class: "event-label", text: labelOf(item.row) }),
        item.decidedBy !== item.row.id ? this.citedBadge(item.campaign, item.row, item.decidedBy) : null,
        el("span", { class: `event-change${moved ? " moved" : ""}`, text: moved ? `${levelShort(item.row.level)}→${levelShort(item.level)}` : levelShort(item.level) }),
        el("span", { class: "event-meta", text: `${item.campaign} ${shortDate(item.row.date)}` }),
        item.note ? el("span", { class: "event-note", text: item.note }) : null,
      );
    },

    // --- Copy -------------------------------------------------------------------------------------------------

    copy() {
      const hash = Replay.encodeState(this.state, this.index);
      const text = [
        Readout.snippet(this.index, this.result),
        "",
        Readout.sharedParagraph(this.index, this.result),
        "",
        hash ? `State: #${hash}` : "State: the code's (no hash)",
        hash ? `tinarrative benchmark calibrate report --state '${hash}'` : "tinarrative benchmark calibrate report",
        "",
      ].join("\n");
      const done = (ok) => {
        const button = $("copy");
        button.textContent = ok ? "Copied" : "Copy failed";
        $("copy-status").textContent = ok ? "The readout is on the clipboard." : "The browser refused the clipboard.";
        clearTimeout(this.copyTimer);
        this.copyTimer = setTimeout(() => {
          button.textContent = "Copy readout";
          $("copy-status").textContent = "";
        }, 1600);
      };
      const fallback = () => {
        const area = el("textarea", { class: "visually-hidden", readonly: true });
        area.value = text;
        document.body.append(area);
        area.select();
        let ok = false;
        try {
          ok = document.execCommand("copy");
        } catch (error) {
          ok = false;
        }
        area.remove();
        done(ok);
      };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(() => done(true), fallback);
      else fallback();
    },
  };

  const byShare = (a, b) => (b.share ?? -1) - (a.share ?? -1);

  function niceMax(max) {
    if (max <= 4) return 4;
    const power = Math.pow(10, Math.floor(Math.log10(max)));
    for (const step of [1, 2, 2.5, 5, 10]) if (step * power >= max) return step * power;
    return 10 * power;
  }

  function countTicks(max) {
    const ticks = [];
    for (let i = 1; i <= 4; i += 1) ticks.push((max / 4) * i);
    return ticks.filter((tick) => Number.isInteger(tick));
  }

  function appendDecade(text, decade) {
    if (decade >= -2 && decade <= 1) {
      text.textContent = String(Math.pow(10, decade) >= 1 ? Math.round(Math.pow(10, decade)) : Number(Math.pow(10, decade).toPrecision(1)));
      return;
    }
    text.append(svg("tspan", {}, "10"));
    text.append(svg("tspan", { class: "axis-exp", dy: -5 }, decade < 0 ? `−${-decade}` : String(decade)));
  }

  // A list of events: the digest (six by share, then how many more) or the full list.
  function listBody(list, onClose) {
    const shown = list.full ? list.items : list.items.slice(0, DIGEST_ROWS);
    const rest = list.items.length - shown.length;
    const head = el(
      "div",
      { class: "list-head" },
      el("strong", { class: "list-title", text: list.title }),
      el("span", { class: "list-note", text: list.note }),
      list.full && onClose ? el("button", { type: "button", class: "quiet-button list-close", text: "Close", onclick: onClose }) : null,
    );
    const items = el("ol", { class: `events${list.full ? " events-full" : ""}` }, ...shown.map((item) => App.eventLine(item)));
    const footer = rest > 0 ? el("p", { class: "list-more", text: `+${rest} more · click for the full list` }) : null;
    return el("div", { class: "list" }, head, items, footer);
  }

  // --- The digest popover: hover or focus shows six events; a click pins the full list in place. ----------------

  const Pop = {
    anchor: null,
    make: null,
    pinned: false,
    timer: null,

    hover(anchor, make) {
      if (this.pinned) return;
      clearTimeout(this.timer);
      this.anchor = anchor;
      this.make = make;
      this.show();
    },

    leave() {
      if (this.pinned) return;
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.close(), 80);
    },

    pin(anchor, make) {
      clearTimeout(this.timer);
      this.anchor = anchor;
      this.make = make;
      this.pinned = true;
      this.show();
      const close = document.querySelector("#pop .list-close");
      if (close) close.focus();
    },

    close(restoreFocus = false) {
      clearTimeout(this.timer);
      const restore = restoreFocus && this.pinned && this.anchor instanceof Element ? this.anchor : null;
      this.pinned = false;
      this.anchor = null;
      this.make = null;
      $("pop").hidden = true;
      $("pop").replaceChildren();
      if (restore && document.contains(restore)) restore.focus({ preventScroll: true });
    },

    refresh() {
      if (this.anchor && this.make && !$("pop").hidden) {
        if (this.anchor instanceof Element && !document.contains(this.anchor)) this.close();
        else this.show();
      }
    },

    show() {
      const pop = $("pop");
      const list = this.make();
      list.full = this.pinned;
      pop.replaceChildren(listBody(list, this.pinned ? () => this.close(true) : null));
      pop.querySelector(".list-title").id = "pop-title";
      pop.classList.toggle("pop-pinned", this.pinned);
      pop.hidden = false;
      const box = this.anchor.getBoundingClientRect();
      const width = pop.offsetWidth;
      const height = pop.offsetHeight;
      let left = Math.min(window.innerWidth - width - 12, Math.max(12, box.left));
      let top = box.bottom + 6;
      if (top + height > window.innerHeight - 12) top = Math.max(12, box.top - height - 6);
      pop.style.left = `${left}px`;
      pop.style.top = `${top}px`;
    },
  };

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("pop").hidden) Pop.close(true);
  });
  document.addEventListener("pointerdown", (event) => {
    if (Pop.pinned && !$("pop").contains(event.target)) Pop.close();
  });
  window.addEventListener("scroll", () => Pop.pinned || $("pop").hidden || Pop.close(), { passive: true });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
