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
  const POP_WIDTH = 480;
  const POP_MIN_WIDTH = 320;
  const RESORT_DELAY = 400;
  const ORDER_KEY = "ti-calibration-count-order";
  const STATUS_POLL = 2000;
  const STATUS_GRACE = 20000;
  const SLIDER_STEP = 0.01;
  const CHART_HEIGHT = 270;
  const CHART_MARGIN = { top: 22, right: 12, bottom: 26, left: 40 };
  const BIN = 0.1;

  // --- Small helpers -----------------------------------------------------------------------------------------

  const $ = (id) => document.getElementById(id);

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
    resortTimer: null,
    hashTimer: null,
    frame: 0,
    dragging: false,
    chartWidth: 600,
    chartModel: null,
    chartCursor: -1,
    countsLayout: "",
    countRows: new Map(),
    countExtras: [],
    countStatic: [],
    countOrder: "events",

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
      for (const [direction, label] of [["rise", "rose"], ["drop", "dropped"]]) {
        $("flow-keys").append(el("span", { class: "level-key-item" }, el("i", { class: `flow-key ${direction}` }), label));
      }

      try {
        if (window.localStorage.getItem(ORDER_KEY) === "moves") this.countOrder = "moves";
      } catch (error) {
        // Storage can be closed to a page opened from disk; the order then lasts for this visit only.
      }
      for (const button of document.querySelectorAll("#count-order .order-option")) {
        button.setAttribute("aria-pressed", String(button.dataset.order === this.countOrder));
        button.addEventListener("click", () => this.setCountOrder(button.dataset.order));
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
      Inspector.init();
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
      this.tideView = [0, 1].map(() => ({ items: [], hover: null, focus: null }));
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
          list.append(el("li", { class: row === 5 ? "tide-cut" : "event event-compact event-blank" }));
        }
        const readout = el("p", { class: "tide-readout" });
        tide.append(list, readout);
        // The readout follows the row under the pointer and keeps it while the pointer stays in the tide, so its
        // type can be reached; leaving the tide falls back to the focused row, then to the tide's type mix.
        const rowOf = (target) => {
          const row = target instanceof Element ? target.closest(".tide-rows > li") : null;
          return row && list.contains(row) ? [...list.children].indexOf(row) : null;
        };
        list.addEventListener("pointerover", (event) => {
          const at = rowOf(event.target);
          if (at === null || at === 5 || at === this.tideView[slot].hover) return;
          this.tideView[slot].hover = at;
          this.renderReadout(slot);
        });
        tide.addEventListener("pointerleave", () => {
          this.tideView[slot].hover = null;
          this.renderReadout(slot);
        });
        list.addEventListener("focusin", (event) => {
          this.tideView[slot].focus = rowOf(event.target);
          this.tideView[slot].hover = null;
          this.renderReadout(slot);
        });
        list.addEventListener("focusout", (event) => {
          if (list.contains(event.relatedTarget)) return;
          this.tideView[slot].focus = null;
          this.renderReadout(slot);
        });
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
      this.renderCounts({ resort: true });
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
      if (options.from === "slider") this.writeHashSoon();
      else this.writeHash();
      Pop.refresh();
      Inspector.refresh();
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
        rows.forEach((row, i) => (i === 5 ? row.replaceChildren() : this.fillEventRow(row, null, { compact: true })));
        tide.classList.add("tide-empty");
        this.tideView[slot].items = [];
        this.renderReadout(slot);
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
      const items = new Array(11).fill(null);
      for (let i = 0; i < 5; i += 1) {
        const top = above[i - (Math.min(5, neighbours) - above.length)];
        items[i] = top ? this.tideItem(top) : null;
        items[6 + i] = below[i] ? this.tideItem(below[i]) : null;
      }
      items.forEach((item, i) => i === 5 || this.fillEventRow(rows[i], item, { compact: true }));
      rows[5].replaceChildren(el("span", { class: "tide-cut-label", text: `${cutoff.above.length} above · ${cutoff.below.length} below shown` }));
      this.tideView[slot].items = items;
      this.renderReadout(slot);
    },

    // The line under a tide: the type of the row in hand, or the types of all its rows, most common first.
    renderReadout(slot) {
      const view = this.tideView[slot];
      const tide = $(`tide-${slot}`);
      const readout = tide.querySelector(".tide-readout");
      const rows = tide.querySelectorAll(".tide-rows > li");
      const at = view.hover !== null ? view.hover : view.focus;
      const item = at !== null ? view.items[at] : null;
      rows.forEach((row, i) => row.classList.toggle("event-current", item !== null && i === at));
      if (item) {
        const date = typeof item.row.date === "string" ? item.row.date.slice(0, 10) : "";
        readout.removeAttribute("title");
        readout.replaceChildren(
          this.typeButton(item.row.type),
          el("span", { class: "readout-meta", text: [`score ${item.score}`, `${item.campaign} ${date}`.trim()].join(" · ") }),
        );
        return;
      }
      const counts = new Map();
      for (const entry of view.items) if (entry) counts.set(entry.row.type, (counts.get(entry.row.type) || 0) + 1);
      const types = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      if (!types.length) {
        readout.removeAttribute("title");
        readout.replaceChildren();
        return;
      }
      readout.title = types.map(([type, count]) => `${type} ×${count}`).join("\n");
      const parts = types.map(([type, count]) =>
        el("span", { class: "readout-type" }, this.typeButton(type), el("span", { class: "readout-count num", text: `×${count}` })),
      );
      readout.replaceChildren(...parts);
      // Keep whole entries only; what does not fit is counted at the end and listed in the line's tooltip.
      let shown = parts.length;
      while (shown > 1 && readout.scrollWidth > readout.clientWidth) {
        shown -= 1;
        readout.replaceChildren(...parts.slice(0, shown), el("span", { class: "readout-more", text: `+${plural(parts.length - shown, "type")}` }));
      }
    },

    // A type that filters the page when clicked, and shows when it is the filter.
    typeButton(type) {
      const only = this.state.types.length === 1 && this.state.types[0] === type;
      return el("button", {
        type: "button",
        class: "event-type",
        text: type,
        title: only ? "Show every type" : `Filter by ${type}`,
        "aria-pressed": String(only),
        onclick: (event) => {
          event.stopPropagation();
          this.setType(type);
        },
      });
    },

    // A cut-off neighbour as the shared row reads it.
    tideItem(neighbour) {
      const position = this.positions[neighbour.campaign].get(neighbour.id);
      const row = this.tables[neighbour.campaign][position] || {
        id: neighbour.id, type: neighbour.type, label: neighbour.id, level: neighbour.oracle_level, date: null, stakes: [],
      };
      return {
        campaign: neighbour.campaign,
        row,
        level: neighbour.level,
        decidedBy: neighbour.decided_by,
        share: neighbour.share,
        measure: this.focus,
        score: neighbour.score,
      };
    },

    citedBadge(campaign, row, decidedBy) {
      const decider = this.tables[campaign][this.positions[campaign].get(decidedBy)];
      const label = decider ? labelOf(decider) : decidedBy;
      const stake = decider && decider.stakes.length ? `${decider.stakes[0].measure} stake` : "base level";
      const text = `Set by the cited ${label} (${stake}), not by this event's own stake.`;
      return el("span", { class: "badge", title: text, "aria-label": text, text: "cited" });
    },

    // --- Level counts -----------------------------------------------------------------------------------------
    //
    // One row per event type: the levels its events hold now, a band under the stretch that rose or dropped into
    // each level, and the exact changes beside it. Staked types come first, by their staked events or, if chosen,
    // by how many of their events change level; types that move without a stake on the focused measure follow.
    // Rows only change place when the reference settles, never while it slides.

    setCountOrder(order) {
      if (order === this.countOrder) return;
      this.countOrder = order;
      try {
        window.localStorage.setItem(ORDER_KEY, order);
      } catch (error) {
        // See build(): without storage the choice is kept for this visit.
      }
      for (const button of document.querySelectorAll("#count-order .order-option")) {
        button.setAttribute("aria-pressed", String(button.dataset.order === order));
      }
      Pop.close();
      this.renderCounts({ resort: true });
    },

    // Put the staked rows in the chosen order; rows that change place glide from where they were.
    orderCounts(moves) {
      const moved = (type) => (moves.get(type) || []).reduce((sum, move) => sum + move.count, 0);
      const place = new Map(this.countStatic.map((type, i) => [type, i]));
      const types = [...this.countStatic];
      if (this.countOrder === "moves") types.sort((a, b) => moved(b) - moved(a) || place.get(a) - place.get(b));
      const rows = types.map((type) => this.countRows.get(type).row);
      const list = $("counts");
      if (rows.every((row, i) => list.children[i] === row)) return;
      const glide = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const before = glide ? rows.map((row) => row.getBoundingClientRect().top) : [];
      const focused = list.contains(document.activeElement) ? document.activeElement : null;
      list.prepend(...rows);
      if (focused) focused.focus({ preventScroll: true });
      rows.forEach((row, i) => {
        const delta = glide ? before[i] - row.getBoundingClientRect().top : 0;
        if (Math.abs(delta) < 1) return;
        row.animate([{ transform: `translateY(${delta}px)` }, { transform: "translateY(0)" }], {
          duration: 220,
          easing: "cubic-bezier(0.16, 1, 0.3, 1)",
        });
      });
    },

    renderCounts({ resort } = {}) {
      const focus = this.focus;
      const list = $("counts");
      const staked = this.stakedTypes[focus];
      if (this.countsLayout !== focus) {
        this.countsLayout = focus;
        this.countRows.clear();
        this.countExtras = [];
        // The static order: by the type's staked rows in the whole table, which the reference never changes.
        const types = [...staked.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
        this.countStatic = types.map(([type]) => type);
        list.replaceChildren(...types.map(([type]) => this.countRow(type)));
        if (types.length === 0) list.append(el("p", { class: "empty", text: "No event type carries this stake." }));
        resort = true;
      }

      const moves = new Map();
      for (const move of this.full.moves) moves.set(move.type, [...(moves.get(move.type) || []), move]);
      if (resort) this.orderCounts(moves);
      const unstaked = [...moves.keys()].filter((type) => !staked.has(type)).sort();
      const extras = resort ? unstaked : [...this.countExtras, ...unstaked.filter((type) => !this.countExtras.includes(type))];
      if (extras.join("|") !== this.countExtras.join("|")) {
        for (const type of this.countExtras) {
          if (extras.includes(type)) continue;
          this.countRows.get(type).row.remove();
          this.countRows.delete(type);
        }
        this.countExtras = extras;
        for (const stale of list.querySelectorAll(".count-divider")) stale.remove();
        if (extras.length) list.append(el("p", { class: "count-divider", text: `Moving without a ${focus} stake` }));
        for (const type of extras) list.append(this.countRows.has(type) ? this.countRows.get(type).row : this.countRow(type));
      }

      const counts = this.levelCounts(this.full);
      for (const [type, parts] of this.countRows) {
        const entry = counts.get(type);
        const replay = entry ? entry.replay : {};
        const baseline = entry ? entry.baseline : {};
        const total = this.levels.reduce((sum, level) => sum + (replay[level] || 0), 0);
        const typeMoves = moves.get(type) || [];
        let before = 0;
        this.levels.forEach((level, i) => {
          const n = replay[level] || 0;
          const segment = parts.segments[i];
          segment.style.flexBasis = total ? `${(n / total) * 100}%` : "0%";
          segment.hidden = n === 0;
          segment.setAttribute("aria-label", `${type}: ${n} ${levelName(level)} (code: ${baseline[level] || 0})`);
          segment.textContent = n / Math.max(1, total) > 0.12 ? String(n) : "";
          // Risers came from the left of this level, so their band sits at its left edge; droppers at its right.
          const arrived = { rise: 0, drop: 0 };
          for (const move of typeMoves) {
            if (move.to_level === level) arrived[this.levels.indexOf(move.from_level) < i ? "rise" : "drop"] += move.count;
          }
          const [rise, drop] = parts.flows[i];
          rise.hidden = arrived.rise === 0;
          rise.style.left = `${total ? (before / total) * 100 : 0}%`;
          rise.style.width = `${total ? (arrived.rise / total) * 100 : 0}%`;
          drop.hidden = arrived.drop === 0;
          drop.style.right = `${total ? (1 - (before + n) / total) * 100 : 0}%`;
          drop.style.width = `${total ? (arrived.drop / total) * 100 : 0}%`;
          before += n;
        });
        const dimmed = (this.state.types.length > 0 && !this.state.types.includes(type)) || (total === 0 && typeMoves.length === 0);
        parts.row.classList.toggle("dim", dimmed);
        parts.row.classList.toggle("count-row-chosen", this.state.types.includes(type));
        parts.total.textContent = String(total);
        this.fillChanges(type, parts, typeMoves);
      }

      const shown = this.result.moves;
      const via = shown.reduce((sum, move) => sum + move.via_cited, 0);
      $("counts-note").textContent = shown.length
        ? `${plural(shown.length, "change")} · ${plural(this.result.totals.events_moved, "event")}${via ? `, ${via} via a cited event` : ""}`
        : "Nothing moves at these references";
    },

    countRow(type) {
      const digest = (make) => ({
        onclick: (event) => Pop.pin(event.currentTarget, () => make(true)),
        onmouseenter: (event) => Pop.hover(event.currentTarget, () => make(false)),
        onmouseleave: () => Pop.leave(),
      });
      const segments = this.levels.map((level) => {
        const make = (full) => this.countList(type, level, full);
        const segment = el("button", Object.assign({ type: "button", class: `segment lv-${level}` }, digest(make)));
        segment.addEventListener("focus", () => Pop.hover(segment, () => make(false)));
        segment.addEventListener("blur", () => Pop.leave());
        return segment;
      });
      const flows = this.levels.map((level) =>
        ["rise", "drop"].map((direction) =>
          el("i", Object.assign({ class: `flow ${direction}`, hidden: true }, digest((full) => this.arrivalList(type, level, direction, full)))),
        ),
      );
      const total = el("span", { class: "count-total num" });
      const changes = el("span", { class: "count-changes" });
      const row = el(
        "div",
        { class: "count-row" },
        el("button", { type: "button", class: "type-button", text: type, title: `Filter by ${type}`, onclick: () => this.setType(type) }),
        el("div", { class: "count-bars" }, el("div", { class: "count-bar" }, ...segments), el("div", { class: "count-flow", "aria-hidden": "true" }, ...flows.flat())),
        total,
        changes,
      );
      const parts = { row, segments, flows, total, changes, chips: new Map() };
      this.countRows.set(type, parts);
      return row;
    },

    // The exact changes of one type, in the order their bands sit in the bar.
    fillChanges(type, parts, typeMoves) {
      const rank = (move) => this.levels.indexOf(move.to_level) * this.levels.length + this.levels.indexOf(move.from_level);
      const current = new Map(typeMoves.map((move) => [`${move.from_level}|${move.to_level}`, move]));
      let added = false;
      for (const [key, move] of current) {
        if (parts.chips.has(key)) continue;
        const make = (full) => this.moveList(type, move.from_level, move.to_level, full);
        const chip = el(
          "button",
          {
            type: "button",
            class: `change ${this.levels.indexOf(move.to_level) > this.levels.indexOf(move.from_level) ? "rise" : "drop"}`,
            "data-rank": rank(move),
            title: `${levelName(move.from_level)} → ${levelName(move.to_level)}`,
            onclick: (event) => Pop.pin(event.currentTarget, () => make(true)),
            onmouseenter: (event) => Pop.hover(event.currentTarget, () => make(false)),
            onmouseleave: () => Pop.leave(),
            onfocus: (event) => Pop.hover(event.currentTarget, () => make(false)),
            onblur: () => Pop.leave(),
          },
          el("span", { class: "change-path", text: `${levelShort(move.from_level)}→${levelShort(move.to_level)}` }),
          el("span", { class: "change-count" }),
          el("span", { class: "change-via" }),
        );
        parts.chips.set(key, chip);
        added = true;
      }
      if (added) parts.changes.replaceChildren(...[...parts.chips.values()].sort((a, b) => a.dataset.rank - b.dataset.rank));
      for (const [key, chip] of parts.chips) {
        const move = current.get(key);
        chip.hidden = !move;
        if (!move) continue;
        const [from, to] = key.split("|");
        chip.querySelector(".change-count").textContent = String(move.count);
        chip.querySelector(".change-via").textContent = move.via_cited ? `${move.via_cited} cited` : "";
        chip.setAttribute(
          "aria-label",
          `${type}, ${levelName(from)} to ${levelName(to)}: ${plural(move.count, "event")}${move.via_cited ? `, ${move.via_cited} via a cited event` : ""}`,
        );
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

    // The events of one type the replay leaves standing that pass the test, largest share first.
    typeEvents(type, test) {
      const items = [];
      for (const name of this.full.state.campaigns) {
        const fallen = this.fallen(this.full, name);
        this.full.campaigns[name].events.forEach((event, position) => {
          const row = this.tables[name][position];
          if (row.type === type && !fallen.has(event.id) && test(row.level, event.level)) items.push(this.eventItem(name, position, this.full));
        });
      }
      return items.sort(byShare);
    },

    countList(type, level, full) {
      const items = this.typeEvents(type, (from, to) => to === level);
      return { type, title: `${type} · ${levelName(level)}`, note: plural(items.length, "event"), items, full };
    },

    moveList(type, from, to, full) {
      const items = this.typeEvents(type, (was, now) => was === from && now === to);
      return { type, title: `${type} · ${levelName(from)} → ${levelName(to)}`, note: plural(items.length, "event"), items, full };
    },

    arrivalList(type, level, direction, full) {
      const at = this.levels.indexOf(level);
      const rose = direction === "rise";
      const items = this.typeEvents(type, (was, now) => now === level && was !== level && this.levels.indexOf(was) < at === rose);
      return { type, title: `${type} · ${rose ? "rose" : "dropped"} to ${levelName(level)}`, note: plural(items.length, "event"), items, full };
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
        score: event ? event.score : row.score,
      };
    },

    // One event row, wherever the page lists events: the share (or —), the level dot, the label, the cited badge,
    // the level change, campaign and date, then the type ID and any note. A list row sets the type under the label,
    // unless the list is of one type. A compact row keeps to one line for the tide tables and leaves its type to the
    // readout under the tide, so clicking anywhere on it opens the event: the inspector's hook (#490).
    eventRow(item, options) {
      return this.fillEventRow(el("li"), item, options);
    },

    fillEventRow(node, item, { compact = false, showType = true } = {}) {
      node.onclick = null;
      node.onkeydown = null;
      if (!item) {
        node.className = `event${compact ? " event-compact" : ""} event-blank`;
        node.replaceChildren();
        for (const name of ["title", "tabindex", "data-type", "data-id", "data-campaign"]) node.removeAttribute(name);
        return node;
      }
      const { row, level } = item;
      const label = labelOf(row);
      const moved = level !== row.level;
      const dimmed = this.state.types.length > 0 && !this.state.types.includes(row.type);
      const type = compact ? null : this.typeButton(row.type);
      if (type && !showType) type.hidden = true;
      const sub = compact ? [] : [showType ? type : null, item.note ? el("span", { class: "event-note", text: item.note }) : null].filter(Boolean);
      node.className = `event${compact ? " event-compact" : ""}${dimmed ? " dim" : ""}${Inspector.shows(item.campaign, row.id) ? " event-open" : ""}`;
      node.tabIndex = 0;
      node.dataset.type = row.type;
      node.dataset.id = row.id;
      node.dataset.campaign = item.campaign;
      node.title = [
        label,
        `${row.type} · share ${item.share === null ? "—" : item.share}${item.score === undefined ? "" : ` · score ${item.score}`} · ${levelName(level)} (code: ${levelName(row.level)})`,
        `${item.campaign} ${typeof row.date === "string" ? row.date.slice(0, 10) : ""}`.trim(),
        row.id,
      ].join("\n");
      node.onclick = () => this.openEvent(node, item);
      node.onkeydown = (event) => {
        if (event.target !== node || (event.key !== "Enter" && event.key !== " ")) return;
        event.preventDefault();
        this.openEvent(node, item);
      };
      node.replaceChildren(
        ...[
          el("span", { class: "event-share num", text: item.share === null ? "—" : fmt(item.share), title: item.measure && item.share !== null ? `${item.measure} share ${item.share}` : "No stake of its own" }),
          levelDot(level),
          el("span", { class: "event-main" }, el("span", { class: "event-label", text: label }), showType ? null : type),
          item.decidedBy !== row.id ? this.citedBadge(item.campaign, row, item.decidedBy) : null,
          el("span", { class: `event-change${moved ? " moved" : ""}`, text: moved ? `${levelShort(row.level)}→${levelShort(level)}` : levelShort(level) }),
          el("span", { class: "event-meta", text: `${compact ? item.campaign.slice(0, 4) : item.campaign} ${shortDate(row.date)}` }),
          sub.length ? el("span", { class: "event-sub" }, ...sub) : null,
        ].filter(Boolean),
      );
      return node;
    },

    // Every event row opens the inspector; a row inside the inspector swaps it to that event.
    openEvent(node, item) {
      Inspector.open(node, item.campaign, item.row.id);
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
    // A list of one type names it in the title, so its rows leave the type out.
    const options = { showType: !list.type };
    const items = el("ol", { class: `events${list.full ? " events-full" : ""}` }, ...shown.map((item) => App.eventRow(item, options)));
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
      this.place();
    },

    // Beside its anchor, and clear of an open inspector so a pinned list stays usable next to it; when the drawer
    // leaves too little room (it takes the whole screen at phone width), the list closes instead.
    place() {
      const pop = $("pop");
      if (pop.hidden || !this.anchor) return;
      const drawer = $("inspector");
      const edge = drawer.hidden ? window.innerWidth : drawer.getBoundingClientRect().left;
      const room = edge - 24;
      if (!drawer.hidden && room < POP_MIN_WIDTH) {
        this.close();
        return;
      }
      pop.style.width = drawer.hidden ? "" : `${Math.min(POP_WIDTH, room)}px`;
      const box = this.anchor.getBoundingClientRect();
      const width = pop.offsetWidth;
      const height = pop.offsetHeight;
      const left = Math.min(edge - width - 12, Math.max(12, box.left));
      let top = box.bottom + 6;
      if (top + height > window.innerHeight - 12) top = Math.max(12, box.top - height - 6);
      pop.style.left = `${left}px`;
      pop.style.top = `${top}px`;
    },
  };

  // --- The event inspector: one drawer for the event a row opened. -------------------------------------------
  //
  // Page state only, never in the hash. The parts that the reference cannot change are built once per event; level,
  // score, decided-by and the cited rows are refilled in place on every render, so focus inside the drawer survives
  // the slider. Cited and decided-by rows swap the drawer to that event, and Back walks the chain.

  const Inspector = {
    chain: [],
    returnTo: null,
    parts: null,

    get current() {
      return this.chain[this.chain.length - 1] || null;
    },

    shows(campaign, id) {
      const current = this.current;
      return current !== null && current.campaign === campaign && current.id === id;
    },

    init() {
      $("inspector-close").addEventListener("click", () => this.close());
      $("inspector-back").addEventListener("click", () => this.back());
      const place = () => this.place();
      window.addEventListener("scroll", place, { passive: true });
      window.addEventListener("resize", () => {
        this.place();
        Pop.place();
      });
    },

    open(node, campaign, id) {
      const panel = $("inspector");
      if (panel.contains(node)) {
        this.go(campaign, id);
        return;
      }
      // A pinned list stays open beside the drawer, so the next event is one click away. Its rows are rebuilt as the
      // page renders, so focus returns to the row by its event, or to what opened the list.
      if ($("pop").contains(node)) {
        this.returnTo = { campaign, id, anchor: Pop.anchor instanceof Element ? Pop.anchor : $("chart") };
      } else {
        this.returnTo = node;
      }
      this.chain = [{ campaign, id }];
      this.show();
      Pop.place();
    },

    go(campaign, id) {
      if (!this.shows(campaign, id)) this.chain.push({ campaign, id });
      this.show();
    },

    back() {
      if (this.chain.length < 2) return;
      this.chain.pop();
      this.show();
    },

    close() {
      const panel = $("inspector");
      if (panel.hidden) return;
      panel.hidden = true;
      this.chain = [];
      this.parts = null;
      $("inspector-body").replaceChildren();
      this.mark();
      let restore = this.returnTo;
      this.returnTo = null;
      if (restore && !(restore instanceof Element)) {
        const row = [...$("pop").querySelectorAll(".event[data-id]")].find(
          (node) => node.dataset.id === restore.id && node.dataset.campaign === restore.campaign,
        );
        restore = row || restore.anchor;
      }
      if (restore && document.contains(restore)) restore.focus({ preventScroll: true });
    },

    place() {
      const panel = $("inspector");
      if (panel.hidden) return;
      // Under the header bar; at phone width the bar wraps tall, so the drawer takes the whole screen.
      const below = Math.round(document.querySelector(".bar").getBoundingClientRect().bottom);
      panel.style.top = `${window.innerWidth <= 720 ? 0 : Math.max(0, below)}px`;
    },

    show() {
      const panel = $("inspector");
      panel.hidden = false;
      this.place();
      this.build();
      this.refresh();
      this.mark();
      $("inspector-body").scrollTop = 0;
      $("inspector-title").focus({ preventScroll: true });
    },

    // Flag the row of the inspected event wherever a list shows it.
    mark() {
      for (const node of document.querySelectorAll(".event[data-id]")) {
        node.classList.toggle("event-open", this.shows(node.dataset.campaign, node.dataset.id));
      }
    },

    rowOf(campaign, id) {
      const positions = App.positions[campaign];
      const position = positions ? positions.get(id) : undefined;
      return position === undefined ? null : { position, row: App.tables[campaign][position] };
    },

    build() {
      const { campaign, id } = this.current;
      const body = $("inspector-body");
      const back = $("inspector-back");
      back.hidden = this.chain.length < 2;
      if (this.chain.length > 1) {
        const previous = this.chain[this.chain.length - 2];
        const found = this.rowOf(previous.campaign, previous.id);
        back.title = `Back to ${found ? labelOf(found.row) : previous.id}`;
      }
      const found = this.rowOf(campaign, id);
      if (!found) {
        this.parts = null;
        body.replaceChildren(
          el("h2", { class: "inspector-title", id: "inspector-title", tabindex: "-1", text: id }),
          el("p", { class: "ins-empty", text: `This event is not in the ${campaign} table.` }),
        );
        return;
      }
      const { position, row } = found;
      const date = typeof row.date === "string" ? row.date.slice(0, 10) : "no date";
      const interval = typeof row.interval === "string" ? row.interval.slice(0, 10) : null;

      const figure = (label) => {
        const value = el("span", { class: "ins-value" });
        const note = el("span", { class: "ins-note" });
        return { node: el("div", { class: "ins-figure" }, el("dt", { text: label }), el("dd", {}, value, note)), value, note };
      };
      const level = figure("Level now");
      level.value.classList.add("ins-level");
      const score = figure("Score");
      const base = figure("Base");
      base.value.textContent = String(row.base);
      base.note.textContent = "before stakes";

      const decided = el("li");
      const decidedSection = el(
        "section",
        { class: "ins-section", "aria-labelledby": "ins-decided" },
        el("h3", { class: "ins-head", id: "ins-decided", text: "Level set by" }),
        el("p", { class: "ins-lead", text: "A cited event sets this event's level, not its own stake." }),
        el("ol", { class: "events" }, decided),
      );

      const stakeRows = row.stakes.map((stake) => {
        const spec = App.index.measures[stake.measure];
        const compare = el("span", { class: "ins-compare" });
        const tr = el(
          "tr",
          {},
          el("th", { scope: "row" }, el("span", { class: "ins-measure", text: spec ? spec.label : stake.measure }), compare),
          el("td", { class: "num", text: fmt(stake.share), title: String(stake.share) }),
        );
        return { tr, compare, measure: stake.measure, share: Number(stake.share) };
      });

      const entities = (row.entities || []).map((entity) => {
        // Until entities carry a name of their own (#491), the label is "Name (domain:key)"; show the name once.
        const label = entity.name || entity.label || entity.id;
        const suffix = ` (${entity.id})`;
        const name = !entity.name && label.endsWith(suffix) ? label.slice(0, -suffix.length) : label;
        return el("tr", {}, el("th", { scope: "row" }, name, el("span", { class: "ins-entity-id", text: entity.id })));
      });

      const cited = (row.cited || []).map((citedId) => ({ id: citedId, node: el("li"), found: this.rowOf(campaign, citedId) }));

      const off = el("p", { class: "ins-off" });
      body.replaceChildren(...[
        el("h2", { class: "inspector-title", id: "inspector-title", tabindex: "-1", text: labelOf(row) }),
        el(
          "p",
          { class: "ins-meta" },
          App.typeButton(row.type),
          el("span", { class: "ins-tier", text: row.tier }),
          el("span", { text: campaign }),
          el("span", { text: date, title: typeof row.date === "string" ? row.date : "" }),
          interval ? el("span", { text: `interval to ${interval}`, title: `The interval keyed by its later save, ${row.interval}` }) : null,
        ),
        el("p", { class: "ins-id", text: row.id, title: "Event ID" }),
        off,
        el("dl", { class: "ins-figures" }, level.node, score.node, base.node),
        decidedSection,
        el(
          "section",
          { class: "ins-section", "aria-labelledby": "ins-stakes" },
          el("h3", { class: "ins-head", id: "ins-stakes" }, "Stakes", el("span", { class: "ins-count", text: String(row.stakes.length) })),
          stakeRows.length
            ? el("table", { class: "ins-table" }, el("tbody", {}, ...stakeRows.map((item) => item.tr)))
            : el("p", { class: "ins-empty", text: "No stakes: the base sets the score." }),
        ),
        el(
          "section",
          { class: "ins-section", "aria-labelledby": "ins-entities" },
          el("h3", { class: "ins-head", id: "ins-entities" }, "Entities", el("span", { class: "ins-count", text: String(entities.length) })),
          entities.length
            ? el("table", { class: "ins-table ins-entities" }, el("tbody", {}, ...entities))
            : el("p", { class: "ins-empty", text: "No entities." }),
        ),
        row.tier === "narrative" || cited.length
          ? el(
              "section",
              { class: "ins-section", "aria-labelledby": "ins-cited" },
              el("h3", { class: "ins-head", id: "ins-cited" }, "Cited constituents", el("span", { class: "ins-count", text: String(cited.length) })),
              cited.length
                ? el("ol", { class: "events" }, ...cited.map((item) => item.node))
                : el("p", { class: "ins-empty", text: "Cites no events." }),
            )
          : null,
      ].filter(Boolean));
      this.parts = { campaign, id, position, row, level, score, decided, decidedSection, stakeRows, cited, off };
    },

    // The focused stake against the current reference, written as the tide captions write a cut-off, and which side
    // of the window around the reference the share falls on.
    compareText(share) {
      if (!(share > 0)) return "no share";
      const reference = App.state.references[App.focus];
      const ratio = share / reference;
      const [low, high] = App.windowEdges();
      const side = share < reference * Math.pow(10, low) ? "below the window" : share > reference * Math.pow(10, high) ? "above the window" : "in the window";
      const factor = fmt(ratio >= 1 ? ratio : 1 / ratio);
      return `${factor === "1" ? "at the reference" : `reference ${ratio >= 1 ? "×" : "÷"} ${factor}`} · ${side}`;
    },

    // The values the replay decides, from the current result; a campaign switched off falls back to the code's.
    refresh() {
      const parts = this.parts;
      if (!parts || $("inspector").hidden) return;
      const { campaign, position, row } = parts;
      const result = App.result;
      const replayed = result.campaigns[campaign] ? result.campaigns[campaign].events[position] : null;
      parts.off.hidden = replayed !== null;
      parts.off.textContent = `${campaign} is switched off, so these are the code's values.`;
      const level = replayed ? replayed.level : row.level;
      const score = replayed ? replayed.score : row.score;
      const decidedBy = replayed ? replayed.decided_by : row.id;

      parts.level.value.replaceChildren(levelDot(level), levelName(level));
      const rank = (name) => App.levels.indexOf(name);
      const moved = level !== row.level;
      parts.level.note.className = `ins-note${moved ? (rank(level) > rank(row.level) ? " rise" : " drop") : ""}`;
      parts.level.note.textContent = moved ? `${rank(level) > rank(row.level) ? "rose" : "dropped"} from ${levelName(row.level)}` : "as the code's";
      parts.score.value.textContent = String(score);
      parts.score.note.textContent = score === row.score ? "as the code's" : `code's ${row.score}`;

      const decider = decidedBy !== row.id ? this.rowOf(campaign, decidedBy) : null;
      parts.decidedSection.hidden = decidedBy === row.id;
      if (decider) App.fillEventRow(parts.decided, App.eventItem(campaign, decider.position, result), {});
      else if (decidedBy !== row.id) parts.decided.replaceChildren(el("span", { class: "ins-entity-id", text: decidedBy }));

      for (const item of parts.stakeRows) {
        const focused = item.measure === App.focus;
        item.tr.classList.toggle("focused", focused);
        item.compare.hidden = !focused;
        if (focused) item.compare.textContent = this.compareText(item.share);
      }
      for (const item of parts.cited) {
        if (item.found) App.fillEventRow(item.node, App.eventItem(campaign, item.found.position, result), {});
        else item.node.replaceChildren(el("span", { class: "ins-entity-id", text: `${item.id} (not in the table)` }));
      }
      // Keep the inspector's own type button in step with the filter, in place so it keeps focus.
      const type = document.querySelector("#inspector-body .ins-meta .event-type");
      if (type) {
        const only = App.state.types.length === 1 && App.state.types[0] === row.type;
        type.setAttribute("aria-pressed", String(only));
        type.title = only ? "Show every type" : `Filter by ${row.type}`;
      }
    },
  };

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    // Escape closes what holds focus first: the inspector, then a list beside it.
    const target = event.target;
    if (!$("inspector").hidden && target instanceof Element && $("inspector").contains(target)) {
      Inspector.close();
      return;
    }
    if (!$("pop").hidden) {
      Pop.close(true);
      return;
    }
    // A text field or a select keeps Escape for itself.
    if (target instanceof Element && target.matches("input:not([type=range]), select, textarea")) return;
    if (!$("inspector").hidden) Inspector.close();
  });
  document.addEventListener("pointerdown", (event) => {
    // Working in the inspector keeps the list it was opened from.
    if (Pop.pinned && !$("pop").contains(event.target) && !$("inspector").contains(event.target)) Pop.close();
  });
  window.addEventListener("scroll", () => Pop.pinned || $("pop").hidden || Pop.close(), { passive: true });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
