// The calibration page: draws what `tinarrative benchmark calibrate open` answers for the state in the URL hash.
//
// A classic script served by that command. index.js and status.js are loaded by index.html; the campaign tables are
// injected here. The server replays the table: this page holds no scoring, no state codec and no readout wording,
// and the hash is an opaque string the server gives it (ADR-0022). The layout is built once and then updated in
// place, so the slider keeps its focus and nothing in the left column changes size while a rise share slides. The
// slider sets the rise share of the focus measure's starting scaling; the page holds no other scaling control.
(function () {
  "use strict";

  const DATA = window.TI_CALIBRATION || { campaigns: {} };
  const SERVE = "tinarrative benchmark calibrate open";
  const SVG = "http://www.w3.org/2000/svg";

  const LEVEL_NAMES = { trivial: "trivial", minor: "minor", major: "major", campaign_defining: "campaign defining" };
  const LEVEL_RANKS = ["trivial", "minor", "major", "campaign_defining"];
  const VERDICTS = [
    ["keeps_members", "Keeps members", "Groups whose members all stay admitted."],
    ["loses_members", "Loses members", "Groups that lose members but keep enough distinct ones to stand."],
    ["falls_apart", "Falls apart", "Groups left with too few distinct members; they leave the package."],
    ["could_become_member", "Could join", "Events that would now be admitted as members; the rule is not re-run."],
  ];
  const DIGEST_ROWS = 6;
  const POP_WIDTH = 480;
  const POP_MIN_WIDTH = 320;
  const ORDER_KEY = "ti-calibration-count-order";
  const VIEW_KEY = "ti-calibration-under-chart";
  const STATUS_POLL = 500;
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

  // A share for reading: three significant figures, written as JavaScript writes the number.
  function fmt(value) {
    if (!Number.isFinite(value)) return "—";
    return String(Number(value.toPrecision(3)));
  }

  const plural = (count, one, many) => `${count} ${count === 1 ? one : many || `${one}s`}`;
  const signed = (number) => (number > 0 ? `+${number}` : number < 0 ? `−${-number}` : "±0");
  // Some save strings keep JSON escapes such as \u00e3; show the character they stand for.
  const labelOf = (row) => row.label.replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => String.fromCharCode(parseInt(code, 16)));
  const levelName = (level) => LEVEL_NAMES[level] || level.replace(/_/g, " ");
  const shortDate = (date) => (typeof date === "string" ? date.slice(0, 7) : "");

  // A level drawn as a gauge of four rising bars: as many filled as the level's rank, in the level's colour from
  // the Level counts bars. It reads without a key; the key beside Level counts names each one.
  function levelGauge(level) {
    const rank = LEVEL_RANKS.indexOf(level) + 1;
    const bars = LEVEL_RANKS.map((_, i) => el("b", { class: i < rank ? "on" : null }));
    return el("i", { class: `gauge gauge-${level}`, title: levelName(level), "aria-hidden": "true" }, ...bars);
  }

  // A change of level: the old gauge, an arrow in the rise or drop colour, the new gauge.
  function levelMove(from, to) {
    const direction = LEVEL_RANKS.indexOf(to) > LEVEL_RANKS.indexOf(from) ? "rise" : "drop";
    return [levelGauge(from), el("span", { class: `move-arrow ${direction}`, text: "→" }), levelGauge(to)];
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
    if (window.location.protocol === "file:") {
      fatal("The page needs its server.", `Run ${SERVE} and open the address it prints.`);
      return;
    }
    if (!index) {
      fatal("No calibration table here.", `The server has no index.js yet. Run ${SERVE} to build it.`);
      return;
    }
    Status.start(index);
    $("layout").setAttribute("aria-busy", "true");
    $("table-key").textContent = `Loading ${index.campaigns.join(", ")}…`;
    loadTables(index.campaigns)
      .then(() => {
        const tables = {};
        const drafts = {};
        for (const name of index.campaigns) {
          tables[name] = DATA.campaigns[name].events;
          drafts[name] = DATA.campaigns[name].drafts || [];
        }
        App.init(index, tables, drafts);
      })
      .catch((error) => fatal("The table could not be read.", `${error.message} Run tinarrative benchmark calibrate open --rebuild.`));
  }

  // --- Status banner -----------------------------------------------------------------------------------------

  const Status = {
    index: null,
    timer: null,
    started: 0,
    lost: "",

    start(index) {
      this.index = index;
      this.started = Date.now();
      // The bar glides to each polled share for as long as the next poll takes, so it never waits at rest.
      $("banner-bar").style.setProperty("--glide", `${STATUS_POLL}ms`);
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
      if (this.lost) {
        tone = "error";
        text = this.lost;
      } else if (status && status.state === "rebuilding") {
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
      this.showProgress(!this.lost && status && status.state === "rebuilding" ? status : null);
    },

    // The rebuild's progress, all worded by status.js: the share and time left beside the bar, then every campaign
    // in extraction order, the running ones with their step. A status without progress leaves the bar indeterminate.
    showProgress(status) {
      $("banner-progress").hidden = !status;
      if (!status) return;
      const progress = status.progress;
      const bar = $("banner-bar");
      bar.dataset.indeterminate = progress ? "false" : "true";
      if (progress) {
        bar.setAttribute("aria-valuenow", String(progress.percent));
        bar.style.setProperty("--share", String(progress.percent / 100));
      } else {
        bar.removeAttribute("aria-valuenow");
        bar.style.setProperty("--share", "0");
      }
      bar.setAttribute("aria-valuetext", progress ? progress.text : "Starting");
      $("banner-detail").textContent = progress ? (progress.summary ?? progress.text) : "";
      const list = $("banner-campaigns");
      const campaigns = (progress && progress.campaigns) || [];
      list.hidden = campaigns.length === 0;
      list.replaceChildren(
        ...campaigns.map((campaign) => {
          const running = campaign.phase !== "waiting" && campaign.phase !== "done";
          const step = campaign.step ?? campaign.phase;
          return el(
            "li",
            {
              class: "banner-campaign",
              "data-phase": campaign.phase,
              "data-state": running ? "running" : null,
              title: `${campaign.name}: ${step}`,
            },
            campaign.name,
            running
              ? el("span", { class: "banner-step", text: step })
              : el("span", { class: "visually-hidden", text: `, ${step}` }),
          );
        }),
      );
    },

    schedule() {
      clearTimeout(this.timer);
      const status = DATA.status;
      const rebuilding = status && status.state === "rebuilding";
      if (!rebuilding && Date.now() - this.started > STATUS_GRACE) return;
      this.timer = setTimeout(() => this.poll(), STATUS_POLL);
    },

    // Re-inject status.js: a script tag reloads the file the CLI rewrites.
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
    drafts: null,
    draftView: null,
    draftLayout: "",
    measures: [],
    levels: [],
    positions: {},
    measuredTypes: {},
    allTypes: [],
    domains: {},
    state: null,
    result: null,
    full: null,
    chosenCuts: {},
    hash: "",
    isCode: true,
    meta: null,
    readout: null,
    asked: 0,
    lastAsked: null,
    built: false,
    frame: 0,
    dragging: false,
    dragFlight: false,
    dragStale: false,
    chartWidth: 600,
    chartModel: null,
    chartCursor: -1,
    countsLayout: "",
    countRows: new Map(),
    countExtras: [],
    countStatic: [],
    countOrder: "events",
    view: "cutoffs",
    typeCounts: {},
    baseOrder: [],
    baseRows: new Map(),
    basesShow: "all",
    basesFind: "",

    init(index, tables, drafts) {
      this.index = index;
      this.tables = tables;
      this.drafts = drafts;
      this.measures = Object.keys(index.measures);
      this.levels = Object.keys(index.constants.level_bands);
      this.prepare();
      this.ask({ hash: window.location.hash.slice(1) }, { resort: true, layout: true });
      window.addEventListener("hashchange", () => {
        if (window.location.hash.slice(1) === this.hash) return;
        this.ask({ hash: window.location.hash.slice(1) }, { resort: true, layout: true });
      });
    },

    // --- The server ---------------------------------------------------------------------------------------

    // Ask the server to replay a state hash or the controls' values. Only the latest request's answer is drawn; a
    // request the same as the last one is not sent again. A summary request (options.summary, the drag's) is always
    // sent, and does not count as the last one: the page then shows no full answer.
    ask(body, options) {
      const text = JSON.stringify(body);
      if (options.summary) this.lastAsked = null;
      else if (text === this.lastAsked) return;
      else this.lastAsked = text;
      const asked = ++this.asked;
      window
        .fetch("replay", { method: "POST", headers: { "Content-Type": "application/json" }, body: text })
        .then((response) => response.json().then((answer) => ({ ok: response.ok, answer })))
        .then(({ ok, answer }) => {
          if (asked !== this.asked) return;
          if (!ok) {
            fatal("The table could not be replayed.", `${answer.fatal || "The server refused the request."} Run ${SERVE} --rebuild.`);
            return;
          }
          this.apply(answer, options);
        })
        .catch(() => {
          if (asked !== this.asked) return;
          this.lastAsked = null;
          if (!this.result) {
            fatal("The page needs its server.", `The server is not answering. Run ${SERVE} and reload this page.`);
            return;
          }
          Status.lost = `The server stopped answering, so this page shows the last replay. Run ${SERVE} and reload.`;
          Status.show();
        })
        .finally(() => {
          if (options.finished) options.finished();
        });
    },

    // While the pointer drags the slider: summary answers for the controls' state, one request in flight. When it
    // answers and the slider has moved since, the latest value goes next. Release asks for the full answer instead.
    drag() {
      if (this.dragFlight) {
        this.dragStale = true;
        return;
      }
      this.dragFlight = true;
      this.dragStale = false;
      this.ask(
        { state: this.state, summary: true },
        {
          summary: true,
          finished: () => {
            this.dragFlight = false;
            if (this.dragStale && this.dragging) this.drag();
          },
        },
      );
    },

    apply(answer, options) {
      // A drag answer that comes after the pointer let go is older than the state the controls hold.
      if (options.summary && !this.dragging) return;
      if (answer.key !== this.index.key) {
        // The table was rebuilt under the page: its rows are no longer the ones the answer counts.
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${answer.hash ? `#${answer.hash}` : ""}`);
        window.location.reload();
        return;
      }
      const local = this.state;
      this.state = answer.state;
      if (options.summary && local) {
        // The slider has moved on since the request: its readout keeps the value under the pointer.
        this.state.rises = local.rises;
        if (local.drops) this.state.drops = local.drops;
      }
      this.meta = answer.meta;
      if (!options.summary) {
        this.hash = answer.hash;
        this.isCode = answer.is_code;
        this.readout = { paragraph: answer.paragraph, snippet: answer.snippet };
      }
      if (answer.error) this.hashError = `The link's state could not be read (${answer.error}), so the page shows the code's scalings.`;
      this.result = this.expand(answer.replay);
      this.full = answer.unfiltered ? this.withUnfiltered(this.result, answer.unfiltered) : this.result;
      this.lookup = null;
      if (!this.built) {
        this.built = true;
        this.build();
        $("layout").setAttribute("aria-busy", "false");
      }
      if (options.summary) this.renderDrag();
      else this.render(options);
    },

    // The compact answer's event columns as the per-row results the views read, by row position.
    expand(replay) {
      const campaigns = {};
      for (const [name, campaign] of Object.entries(replay.campaigns)) {
        const rows = this.tables[name];
        const drafts = this.drafts[name] || [];
        const column = (columns, own) =>
          columns.score.map((score, position) => ({
            id: own[position].id,
            score,
            level: this.levels[columns.level[position]],
            decided_by: columns.decided[position] === null ? own[position].id : rows[columns.decided[position]].id,
          }));
        // A summary answer has no row columns; the lists that read them are not drawn until the full answer.
        const events = campaign.events ? column(campaign.events, rows) : [];
        campaigns[name] = Object.assign({}, campaign, { events, drafts: campaign.drafts ? column(campaign.drafts, drafts) : [] });
      }
      return Object.assign({}, replay, { campaigns });
    },

    // The views that dim the types outside the filter count every type: the same replay without the filter.
    withUnfiltered(result, unfiltered) {
      const campaigns = {};
      for (const [name, campaign] of Object.entries(result.campaigns)) {
        campaigns[name] = Object.assign({}, campaign, { level_counts: unfiltered.level_counts[name], members: unfiltered.members[name] });
      }
      return Object.assign({}, result, { moves: unfiltered.moves, campaigns });
    },

    // Everything the rise share does not change: row positions, the types each measure shares, the chart domains.
    prepare() {
      const types = new Set();
      const shares = {};
      for (const measure of this.measures) {
        this.measuredTypes[measure] = new Map();
        shares[measure] = [];
      }
      for (const [name, rows] of Object.entries(this.tables)) {
        const positions = new Map();
        rows.forEach((row, position) => {
          positions.set(row.id, position);
          types.add(row.type);
          for (const share of row.shares) {
            const counts = this.measuredTypes[share.measure];
            if (!counts) continue;
            counts.set(row.type, (counts.get(row.type) || 0) + 1);
            if (share.share > 0) shares[share.measure].push(share.share);
          }
        });
        this.positions[name] = positions;
        const counts = new Map();
        for (const row of rows) {
          const entry = counts.get(row.type) || { events: 0, ruled: 0 };
          entry.events += 1;
          if (row.rule !== null) entry.ruled += 1;
          counts.set(row.type, entry);
        }
        this.typeCounts[name] = counts;
      }
      this.allTypes = [...types].sort();
      // The Base levels rows: every type the index can switch, most events in the whole table first. The order never
      // changes, so a switch never moves a row.
      const events = (type) => Object.values(this.typeCounts).reduce((sum, counts) => sum + ((counts.get(type) || {}).events || 0), 0);
      this.baseOrder = Object.keys(this.index.kinds).sort((a, b) => events(b) - events(a) || (a < b ? -1 : 1));
      for (const measure of this.measures) {
        // Around the code scaling's midpoint, from below its drop share to above its rise share.
        const code = Math.log10(this.codeRise(measure)) - Math.log10(this.index.constants.default_width) / 2;
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
      $("reset").addEventListener("click", () => {
        // A state of the focus alone: every key left out is the code's.
        this.ask({ state: { focus: this.state.focus } }, { resort: true, layout: true });
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
        if (this.dragging) this.drag();
      });
      slider.addEventListener("keydown", () => {
        this.dragging = false;
      });
      slider.addEventListener("change", () => {
        if (!this.dragging) this.settle();
      });

      const value = $("ref-value");
      const commit = () => {
        const text = value.value.trim();
        const number = /^(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/.test(text) ? Number(text) : NaN;
        if (!Number.isFinite(number) || number <= 0) {
          value.setAttribute("aria-invalid", "true");
          $("ref-error").textContent = `Enter a positive share, such as ${fmt(this.codeRise(this.focus))}.`;
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
          value.value = String(this.state.rises[this.focus]);
          value.removeAttribute("aria-invalid");
          $("ref-error").textContent = "";
        }
      });
      $("ref-code").addEventListener("click", () => {
        this.setReference(this.codeRise(this.focus), { from: "code" });
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
        // Each key item ties the three faces of a level together: its bar pattern, its gauge and its name.
        levelKey.append(
          el("span", { class: "level-key-item" }, el("i", { class: `level-swatch lv-${level}`, "aria-hidden": "true" }), levelGauge(level), levelName(level)),
        );
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
      try {
        if (window.localStorage.getItem(VIEW_KEY) === "drafts") this.view = "drafts";
      } catch (error) {
        // As for the count order: without storage the choice lasts for this visit.
      }
      for (const button of document.querySelectorAll("#view-switch .order-option")) {
        button.addEventListener("click", () => this.setView(button.dataset.view));
      }
      this.buildDial();

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
      this.buildBases();
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

    // The rise share control and the chart stay under the header bar while the column scrolls, so the cut-offs or
    // the drafts below can be read with the slider in reach. The bar's height (it wraps on narrow screens) sets
    // where they stick, and a rule marks the edge only once the column runs under them.
    buildDial() {
      const bar = document.querySelector(".bar");
      const dial = $("dial");
      const measure = () => {
        document.documentElement.style.setProperty("--bar-height", `${Math.round(bar.getBoundingClientRect().height)}px`);
        mark();
      };
      const mark = () => {
        const top = parseFloat(getComputedStyle(dial).top);
        dial.classList.toggle("dial-stuck", Number.isFinite(top) && window.scrollY > 0 && dial.getBoundingClientRect().top <= top + 0.5);
      };
      new ResizeObserver(measure).observe(bar);
      window.addEventListener("scroll", mark, { passive: true });
      measure();
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
        const measured = [...this.measuredTypes[measure].values()].reduce((sum, count) => sum + count, 0);
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
            el("td", { class: "num", text: fmt(this.codeRise(measure)), title: String(this.codeRise(measure)) }),
            el("td", { class: "num", text: String(measured) }),
          ),
        );
      }
      const drafts = this.index.drafts;
      const list = $("drafts");
      if (drafts.length === 0) {
        list.replaceChildren(el("li", { class: "draft-line", text: "No draft shares are declared in this table." }));
        return;
      }
      list.replaceChildren(
        ...drafts.map((draft) =>
          el(
            "li",
            { class: "draft-line", "data-draft": draft.name },
            el("span", { class: "badge badge-draft", text: `draft #${draft.issue}` }),
            el("span", { class: "draft-line-label", text: draft.label }),
            el("span", { class: "draft-line-meta", text: draft.measures.join(", ") }),
            el("span", { class: "draft-line-base" }),
          ),
        ),
      );
    },

    // --- State changes ------------------------------------------------------------------------------------

    sliderReference(position) {
      const code = this.codeRise(this.focus);
      if (Math.abs(position - Math.log10(code)) < SLIDER_STEP / 2) return code;
      return Number(Math.pow(10, position).toPrecision(3));
    },

    // A slider moves its own readout at once; the views follow by summary answers while it drags (drag), and the
    // full replay is asked when it is let go (settle).
    setReference(value, { from }) {
      this.state.rises = Object.assign({}, this.state.rises, { [this.focus]: value });
      // A drop share the new rise share would pass is dropped: the scaling keeps the default width.
      if (this.state.drops && this.state.drops[this.focus] >= value) {
        this.state.drops = Object.assign({}, this.state.drops);
        delete this.state.drops[this.focus];
      }
      if (from === "slider") this.renderControl({ from });
      else this.update({ resort: true, from });
    },

    setFocus(measure) {
      this.state.focus = measure === this.measures[0] ? null : measure;
      $("ref-error").textContent = "";
      $("ref-value").removeAttribute("aria-invalid");
      this.update({ resort: true, layout: true });
    },

    // The base level the state tries for a type, or the code's.
    typeBase(type) {
      const tried = this.state.type_bases ? this.state.type_bases[type] : undefined;
      return tried === undefined ? this.index.kinds[type].base : tried;
    },

    isSwitched(type) {
      return Boolean(this.index.kinds[type]) && this.typeBase(type) !== this.index.kinds[type].base;
    },

    // Setting the code's level clears the switch, so the state and its hash are as if it was never made.
    setTypeBase(type, level) {
      const next = Object.assign({}, this.state.type_bases);
      if (level === this.index.kinds[type].base) delete next[type];
      else next[type] = level;
      this.state.type_bases = next;
      this.update({ resort: true });
    },

    setType(type) {
      const only = this.state.types.length === 1 && this.state.types[0] === type;
      this.state.types = only ? [] : [type];
      this.update({ resort: true, layout: true });
    },

    settle() {
      this.update({ resort: true, from: "slider" });
    },

    // Ask for the controls' state once per frame, however many controls changed in it.
    update(options) {
      this.pending = Object.assign(this.pending || {}, options);
      if (this.frame) return;
      this.frame = window.requestAnimationFrame(() => {
        this.frame = 0;
        const pending = this.pending;
        this.pending = null;
        this.ask({ state: this.state }, pending);
      });
    },

    writeHash() {
      const hash = this.hash;
      const url = `${window.location.pathname}${window.location.search}${hash ? `#${hash}` : ""}`;
      if (window.location.hash.slice(1) !== hash) window.history.replaceState(null, "", url);
    },

    // --- Rendering ----------------------------------------------------------------------------------------

    render(options = {}) {
      this.renderHeader();
      this.renderControl(options);
      this.renderChart();
      this.renderTides();
      this.renderDrafts();
      this.renderCounts(options);
      this.renderReferences();
      this.renderBases();
      this.renderTotals();
      this.renderMembers();
      this.writeHash();
      Pop.refresh();
      Inspector.refresh();
    },

    // What a drag answer redraws: the views that follow the rise share, without re-sorting and without the URL hash,
    // the event lists, the base-level rows, the members, the drawer and the readout.
    renderDrag() {
      this.renderControl({ from: "slider" });
      this.renderChart();
      this.renderTides();
      this.renderDrafts();
      this.renderCounts();
      this.renderTotals();
    },

    renderHeader() {
      for (const button of document.querySelectorAll("#campaigns .toggle")) {
        button.setAttribute("aria-pressed", String(this.state.campaigns.includes(button.dataset.campaign)));
      }
      $("reset").disabled = this.isCode;
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
        const value = this.state.rises[measure];
        const changed = value !== this.codeRise(measure);
        chip.setAttribute("aria-pressed", String(measure === focus));
        chip.classList.toggle("chip-changed", changed);
        chip.querySelector(".chip-value").textContent = fmt(value);
      }
      const rise = this.state.rises[focus];
      const code = this.codeRise(focus);
      const domain = this.domains[focus];
      const slider = $("ref-slider");
      slider.min = String(domain.low);
      slider.max = String(domain.high);
      if (options.from !== "slider") slider.value = String(Math.log10(rise));
      slider.setAttribute("aria-valuetext", `${fmt(rise)} (code's ${fmt(code)})`);
      const field = $("ref-value");
      if (options.from !== "field" && document.activeElement !== field) field.value = String(rise);
      else if (options.from === "field") field.value = String(rise);
      $("ref-code").disabled = rise === code;
      $("ref-code").title = `Set ${this.index.measures[focus].label} back to the code's ${code}`;
      const [drop] = this.windowShares();
      $("ref-window").textContent = `keeps ${fmt(drop)} – ${fmt(rise)}`;
      if (options.layout || !this.typeOptions) this.renderTypeFilter();
    },

    renderTypeFilter() {
      const select = $("type-filter");
      const focus = this.focus;
      const measured = [...this.measuredTypes[focus].keys()].sort();
      const measuredSet = new Set(measured);
      const others = this.allTypes.filter((type) => !measuredSet.has(type));
      select.replaceChildren(el("option", { value: "", text: "All types" }));
      if (this.state.types.length > 1) {
        select.append(el("option", { value: "__several", text: `${this.state.types.length} types (from the link)` }));
      }
      if (measured.length > 0) {
        select.append(el("optgroup", { label: `Measured by ${this.index.measures[focus].label}` }, ...measured.map((type) => el("option", { value: type, text: type }))));
      }
      select.append(el("optgroup", { label: "Other types" }, ...others.map((type) => el("option", { value: type, text: type }))));
      select.value = this.state.types.length > 1 ? "__several" : this.state.types[0] || "";
      select.classList.toggle("type-filter-on", this.state.types.length > 0);
      this.typeOptions = true;
    },

    // The rise share of a measure's starting scaling in the code.
    codeRise(measure) {
      return this.index.scalings[measure].rise;
    },

    // The focus scaling's window: an event keeps its starting level between the drop share and the rise share.
    windowShares() {
      const rise = this.state.rises[this.focus];
      const drop = this.state.drops ? this.state.drops[this.focus] : undefined;
      return [drop === undefined ? rise / this.index.constants.default_width : drop, rise];
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
          const share = row.shares.find((item) => item.measure === focus);
          if (!share) return;
          if (!(share.share > 0)) {
            unshared += 1;
            return;
          }
          const place = Math.floor((Math.log10(share.share) - domain.low) / BIN + 1e-9);
          const bin = bins[Math.max(0, Math.min(count - 1, place))];
          bin.items.push({ campaign: name, position, share: share.share, chosen: types.size === 0 || types.has(row.type) });
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
      const rise = this.state.rises[this.focus];
      const code = this.codeRise(this.focus);
      const [lowCut, highCut] = this.windowShares();
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

      // The cut-offs of the current state: the window's two.
      for (const cutoff of this.result.cutoffs[this.focus] || []) {
        const at = x(Math.log10(cutoff.share));
        if (at < plotLeft || at > plotRight) continue;
        nodes.push(svg("line", { class: "cut", x1: at, x2: at, y1: plotTop - 4, y2: plotBottom }));
      }

      // The code's rise share and the current one.
      const codeAt = x(Math.log10(code));
      if (codeAt >= plotLeft && codeAt <= plotRight && code !== rise) {
        nodes.push(svg("line", { class: "code-line", x1: codeAt, x2: codeAt, y1: plotTop, y2: plotBottom }));
        nodes.push(svg("text", { class: "code-text", x: codeAt + 4, y: plotTop + 10, "text-anchor": "start" }, "code's"));
      }
      const refAt = x(Math.log10(rise));
      if (refAt >= plotLeft && refAt <= plotRight) {
        nodes.push(svg("line", { class: "ref-line", x1: refAt, x2: refAt, y1: plotTop - 4, y2: plotBottom }));
        const anchor = refAt < plotLeft + 40 ? "start" : refAt > plotRight - 40 ? "end" : "middle";
        nodes.push(svg("text", { class: "ref-text", x: refAt, y: plotTop - 8, "text-anchor": anchor }, fmt(rise)));
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
          "measured event",
        )}, rise share ${fmt(rise)}, drop share ${fmt(lowCut)}. Arrow keys step through the bars.`,
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
        const picked = cutoffs.filter((cutoff) => chosen.includes(cutoff.step));
        if (picked.length === 2) return picked;
      }
      const inside = cutoffs.filter((cutoff) => Math.abs(cutoff.step) === 1);
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
              title: `Cut-off at ${cutoff.share} (${cutoff.step > 0 ? "rises" : "drops"} ${plural(Math.abs(cutoff.step), "level")})`,
              text: fmt(cutoff.share),
              onclick: () => this.toggleCut(cutoff.step),
            }),
          ),
        );
      } else {
        const drafts = this.view === "drafts" && this.index.drafts.some((draft) => draft.measures.includes(this.focus));
        const note = drafts ? "Not counted in any real panel" : "Five events on each side of each cut-off";
        chips.replaceChildren(el("span", { class: "section-note", text: note }));
      }
      [0, 1].forEach((slot) => this.renderTide($(`tide-${slot}`), shown[slot] || null, slot));
    },

    toggleCut(step) {
      const shown = this.shownCutoffs().map((cutoff) => cutoff.step);
      if (shown.includes(step)) return;
      // The clicked cut-off replaces the one picked longest ago.
      const last = this.chosenCuts[this.focus] ? this.chosenCuts[this.focus][1] : shown[1];
      this.chosenCuts[this.focus] = [shown.includes(last) ? last : shown[1], step];
      this.renderTides();
      this.renderDrafts();
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
      const levels = Math.abs(cutoff.step);
      const direction = cutoff.step < 0 ? "below drops" : "above rises";
      const amount = levels === 1 ? "a level" : `${["", "", "two", "three"][levels] || levels} levels`;
      // Each further level is as wide as the starting one: the cut-off as a multiple of the rise or drop share.
      const [drop, rise] = this.windowShares();
      const edge = cutoff.step < 0 ? "drop share" : "rise share";
      const factor = fmt(cutoff.step < 0 ? drop / cutoff.share : cutoff.share / rise);
      caption.textContent = `${factor === "1" ? edge : `${edge} ${cutoff.step < 0 ? "÷" : "×"} ${factor}`} · ${direction} ${amount}`;
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
        id: neighbour.id, type: neighbour.type, label: neighbour.id, level: neighbour.oracle_level, date: null, shares: [],
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
      const share = decider && decider.shares.length ? `${decider.shares[0].measure} share` : "base level";
      const text = `Set by the cited ${label} (${share}), not by this event's own share.`;
      return el("span", { class: "badge", title: text, "aria-label": text, text: "cited" });
    },

    // --- Level counts -----------------------------------------------------------------------------------------
    //
    // One row per event type: the levels its events hold now, a band under the stretch that rose or dropped into
    // each level, and the exact changes beside it. Measured types come first, by their measured events or, if chosen,
    // by how many of their events change level; types that move without a share on the focused measure follow.
    // Rows only change place when the rise share settles, never while it slides.

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

    // Put the measured rows in the chosen order; rows that change place glide from where they were.
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
      const measured = this.measuredTypes[focus];
      if (this.countsLayout !== focus) {
        this.countsLayout = focus;
        this.countRows.clear();
        this.countExtras = [];
        // The static order: by the type's measured rows in the whole table, which the rise share never changes.
        const types = [...measured.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
        this.countStatic = types.map(([type]) => type);
        list.replaceChildren(...types.map(([type]) => this.countRow(type)));
        if (types.length === 0) list.append(el("p", { class: "empty", text: "No event type carries this share." }));
        resort = true;
      }

      const moves = new Map();
      for (const move of this.full.moves) moves.set(move.type, [...(moves.get(move.type) || []), move]);
      if (resort) this.orderCounts(moves);
      const unmeasured = [...moves.keys()].filter((type) => !measured.has(type)).sort();
      const extras = resort ? unmeasured : [...this.countExtras, ...unmeasured.filter((type) => !this.countExtras.includes(type))];
      if (extras.join("|") !== this.countExtras.join("|")) {
        for (const type of this.countExtras) {
          if (extras.includes(type)) continue;
          this.countRows.get(type).row.remove();
          this.countRows.delete(type);
        }
        this.countExtras = extras;
        for (const stale of list.querySelectorAll(".count-divider")) stale.remove();
        if (extras.length) list.append(el("p", { class: "count-divider", text: `Moving without a ${focus} share` }));
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
        this.fillSwitched(type, parts.switched);
        this.fillChanges(type, parts, typeMoves);
      }

      const shown = this.result.moves;
      const via = shown.reduce((sum, move) => sum + move.via_cited, 0);
      $("counts-note").textContent = shown.length
        ? `${plural(shown.length, "change")} · ${plural(this.result.totals.events_moved, "event")}${via ? `, ${via} via a cited event` : ""}`
        : "Nothing moves at these rise shares";
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
      // A switched type shows its tried base level after its name; the mark leads to its row in Base levels.
      const switched = el("button", { type: "button", class: "count-base", hidden: true, onclick: () => this.revealBase(type) });
      const row = el(
        "div",
        { class: "count-row" },
        el(
          "span",
          { class: "count-type" },
          el("button", { type: "button", class: "type-button", text: type, title: `Filter by ${type}`, onclick: () => this.setType(type) }),
          switched,
        ),
        el("div", { class: "count-bars" }, el("div", { class: "count-bar" }, ...segments), el("div", { class: "count-flow", "aria-hidden": "true" }, ...flows.flat())),
        total,
        changes,
      );
      const parts = { row, segments, flows, total, changes, switched, chips: new Map() };
      this.countRows.set(type, parts);
      return row;
    },

    fillSwitched(type, mark) {
      const on = this.isSwitched(type);
      mark.hidden = !on;
      if (!on) return;
      const tried = this.typeBase(type);
      if (mark.dataset.level !== tried) {
        mark.dataset.level = tried;
        mark.replaceChildren(el("span", { class: "count-base-label", text: "base" }), levelGauge(tried));
      }
      const text = `${type}: base level ${levelName(tried)}, the code's is ${levelName(this.index.kinds[type].base)}. Show it in Base levels.`;
      mark.title = text;
      mark.setAttribute("aria-label", text);
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
          el("span", { class: "change-path" }, ...levelMove(move.from_level, move.to_level)),
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

    // --- Rise shares and drafts --------------------------------------------------------------------------------

    renderReferences() {
      for (const row of document.querySelectorAll("#references tr")) {
        const measure = row.dataset.measure;
        const value = this.state.rises[measure];
        const changed = value !== this.codeRise(measure);
        const cell = row.querySelector(".ref-current");
        cell.textContent = fmt(value);
        cell.title = String(value);
        row.classList.toggle("changed", changed);
        row.classList.toggle("focused", measure === this.focus);
      }
      for (const line of document.querySelectorAll("#drafts .draft-line[data-draft]")) {
        const draft = this.index.drafts.find((item) => item.name === line.dataset.draft);
        const base = this.state.bases[draft.name];
        const cell = line.querySelector(".draft-line-base");
        cell.replaceChildren(levelGauge(base), base === draft.base ? `base ${levelName(base)}` : `base ${levelName(base)}, own ${levelName(draft.base)}`);
        line.classList.toggle("changed", base !== draft.base);
      }
    },

    // --- Base levels ------------------------------------------------------------------------------------------
    //
    // One row per event type: four buttons for its base level, the code's level beside them, its events, how many of
    // them a context rule decided (a switch leaves those as they are) and how many sit at another level than the
    // code's now. The rows are built once in a fixed order; finding a type or showing the switched ones only hides
    // rows, and the list scrolls inside a fixed height.

    // The four base buttons of a type, for a Base levels row or the inspector. The code's level carries a mark.
    baseOptions(type, label) {
      const code = this.index.kinds[type].base;
      const buttons = this.levels.map((level) =>
        el(
          "button",
          {
            type: "button",
            class: `base-option${level === code ? " base-code" : ""}`,
            "data-level": level,
            "aria-pressed": "false",
            title: level === code ? `${levelName(level)}: the code's base level of ${type}` : `Try ${levelName(level)} as the base level of ${type}`,
            onclick: () => this.setTypeBase(type, level),
          },
          levelGauge(level),
          el("span", { class: "level-name", text: levelName(level) }),
        ),
      );
      return { node: el("span", { class: "base-options", role: "group", "aria-label": label }, ...buttons), buttons };
    },

    syncBaseOptions(buttons, type) {
      const tried = this.typeBase(type);
      for (const button of buttons) button.setAttribute("aria-pressed", String(button.dataset.level === tried));
    },

    buildBases() {
      const body = $("bases");
      for (const type of this.baseOrder) {
        const kind = this.index.kinds[type];
        const options = this.baseOptions(type, `Base level of ${type}`);
        const name = el("button", { type: "button", class: "type-button", text: type, onclick: () => this.setType(type) });
        const cell = (title) => el("td", { class: "num", title });
        const events = cell(null);
        const ruled = cell(kind.rule ? `Decided by the ${kind.rule} context rule; a switched base does not apply to them` : "The kind has no context rule");
        const moving = cell(null);
        const row = el(
          "tr",
          { "data-type": type },
          el("th", { scope: "row" }, name),
          el("td", { class: "base-cell" }, options.node),
          el("td", { class: "base-code-cell" }, levelGauge(kind.base), el("span", { text: levelName(kind.base) })),
          events,
          ruled,
          moving,
        );
        this.baseRows.set(type, { row, name, buttons: options.buttons, events, ruled, moving });
        body.append(row);
      }
      $("bases-all").textContent = String(this.baseOrder.length);
      const find = $("bases-find");
      find.addEventListener("input", () => {
        this.basesFind = find.value.trim().toLowerCase();
        this.renderBases();
      });
      find.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || find.value === "") return;
        find.value = "";
        this.basesFind = "";
        this.renderBases();
      });
      for (const button of document.querySelectorAll("#bases-show .order-option")) {
        button.addEventListener("click", () => {
          this.basesShow = button.dataset.show;
          this.renderBases();
        });
      }
    },

    renderBases() {
      const moving = new Map();
      for (const move of this.full.moves) moving.set(move.type, (moving.get(move.type) || 0) + move.count);
      let switched = 0;
      let shown = 0;
      for (const [type, parts] of this.baseRows) {
        const on = this.isSwitched(type);
        if (on) switched += 1;
        this.syncBaseOptions(parts.buttons, type);
        const counts = { events: 0, ruled: 0 };
        for (const name of this.state.campaigns) {
          const entry = this.typeCounts[name].get(type);
          if (entry) {
            counts.events += entry.events;
            counts.ruled += entry.ruled;
          }
        }
        const moved = moving.get(type) || 0;
        parts.events.textContent = String(counts.events);
        parts.ruled.textContent = counts.ruled ? String(counts.ruled) : "–";
        parts.moving.textContent = moved ? String(moved) : "–";
        parts.moving.classList.toggle("moved", moved > 0);
        const chosen = this.state.types.length === 1 && this.state.types[0] === type;
        parts.name.setAttribute("aria-pressed", String(chosen));
        parts.name.title = chosen ? "Show every type" : `Filter by ${type}`;
        parts.row.classList.toggle("changed", on);
        parts.row.classList.toggle("focused", this.state.types.includes(type));
        const visible = (this.basesShow === "all" || on) && (!this.basesFind || type.toLowerCase().includes(this.basesFind));
        parts.row.hidden = !visible;
        if (visible) shown += 1;
      }
      $("bases-switched").textContent = String(switched);
      for (const button of document.querySelectorAll("#bases-show .order-option")) {
        button.setAttribute("aria-pressed", String(button.dataset.show === this.basesShow));
      }
      $("bases-note").textContent = switched ? `${switched} of ${plural(this.baseOrder.length, "type")} switched` : "Every type at the code's";
      const empty = $("bases-empty");
      empty.hidden = shown > 0;
      if (shown === 0) {
        empty.textContent =
          this.basesShow === "switched" && switched === 0
            ? "No type is switched; every type has the code's base level."
            : `No ${this.basesShow === "switched" ? "switched " : ""}type matches “${this.basesFind}”.`;
      }
    },

    // Bring a type's row into view in Base levels and put focus on its chosen level.
    revealBase(type) {
      const parts = this.baseRows.get(type);
      if (!parts) return;
      if (this.basesFind && !type.toLowerCase().includes(this.basesFind)) {
        this.basesFind = "";
        $("bases-find").value = "";
      }
      if (this.basesShow === "switched" && !this.isSwitched(type)) this.basesShow = "all";
      this.renderBases();
      parts.row.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      const chosen = parts.buttons.find((button) => button.getAttribute("aria-pressed") === "true") || parts.buttons[0];
      chosen.focus({ preventScroll: true });
      parts.row.classList.remove("base-row-flash");
      void parts.row.offsetWidth;
      parts.row.classList.add("base-row-flash");
    },

    // --- Draft shares -----------------------------------------------------------------------------------------
    //
    // Each draft with a candidate on the focused measure gets a panel: its base selector, its rows' levels at that
    // base against its own, how many rows a cited event or the kind's context rule decides, and its own rows nearest
    // the two cut-offs the tides show. Its rows never enter the real panels. A panel's size is fixed per focus,
    // campaigns and types, so nothing grows while a rise share slides.

    draftRowsOn(draft, measure) {
      const types = new Set(this.state.types);
      const rows = [];
      for (const name of this.state.campaigns) {
        const names = this.meta.draft_names[name] || [];
        (this.drafts[name] || []).forEach((row, position) => {
          if (names[position] !== draft.name) return;
          if (types.size && !types.has(row.type)) return;
          rows.push({ campaign: name, row, measured: row.shares.some((share) => share.measure === measure && share.share > 0) });
        });
      }
      return rows;
    },

    setView(view) {
      if (view === this.view) return;
      this.view = view;
      try {
        window.localStorage.setItem(VIEW_KEY, view);
      } catch (error) {
        // See build(): without storage the choice is kept for this visit.
      }
      Pop.close();
      this.renderTides();
      this.renderDrafts();
    },

    // Under the chart sits one of two readings of the same cut-offs: the real events nearest them, or the drafts on
    // the focused measure. A measure no draft shares shows the real ones and keeps the chosen view for the next.
    renderView(count) {
      const drafts = this.view === "drafts" && count > 0;
      $("view-switch").hidden = count === 0;
      $("cutoffs-title").classList.toggle("visually-hidden", count > 0);
      $("view-count").textContent = count ? String(count) : "";
      for (const button of document.querySelectorAll("#view-switch .order-option")) {
        button.setAttribute("aria-pressed", String((button.dataset.view === "drafts") === drafts));
      }
      $("cutoff-pair").hidden = drafts;
      $("draft-panels").hidden = !drafts;
      return drafts;
    },

    renderDrafts() {
      const focus = this.focus;
      const drafts = this.index.drafts.filter((draft) => draft.measures.includes(focus));
      if (!this.renderView(drafts.length)) return;
      const sizes = drafts.map((draft) => {
        const rows = this.draftRowsOn(draft, focus);
        return { draft, rows, slots: Math.min(this.index.constants.neighbours, rows.filter((item) => item.measured).length) };
      });
      const key = `${focus}|${this.state.campaigns.join(",")}|${this.state.types.join(",")}|${sizes.map((item) => `${item.draft.name}:${item.slots}`).join(",")}`;
      if (key !== this.draftLayout) {
        this.draftLayout = key;
        this.draftView = sizes.map((item) => this.draftPanel(item.draft, item.slots));
        $("draft-panels").replaceChildren(...this.draftView.map((view) => view.panel));
        $("draft-panels").classList.toggle("draft-pair", drafts.length > 1);
      }
      sizes.forEach((item, i) => this.fillDraft(this.draftView[i], item.rows));
    },

    draftPanel(draft, slots) {
      const titleId = `draft-title-${draft.name}`;
      const bases = this.levels.map((level) => {
        const own = level === draft.base;
        return el(
          "button",
          {
            type: "button",
            class: "base-option",
            "data-level": level,
            "aria-pressed": "false",
            title: own ? `${levelName(level)}: the draft's own base` : `Try ${levelName(level)} as the base`,
            onclick: () => {
              this.state.bases = Object.assign({}, this.state.bases, { [draft.name]: level });
              this.update({});
            },
          },
          levelGauge(level),
          el("span", { class: "level-name", text: levelName(level) }),
          own ? el("span", { class: "base-own", text: "own" }) : null,
        );
      });
      const segments = this.levels.map((level) => el("span", { class: `segment lv-${level}` }));
      const figures = this.levels.map((level) => {
        const count = el("span", { class: "draft-count" });
        const change = el("span", { class: "figure-change" });
        return {
          node: el("div", { class: "draft-figure" }, el("dt", {}, levelGauge(level), el("span", { class: "level-name", text: levelName(level) })), el("dd", {}, count, change)),
          count,
          change,
        };
      });
      const tides = [0, 1].map(() => {
        const figure = el("span", { class: "tide-figure" });
        const caption = el("span", { class: "tide-caption" });
        const rows = [];
        for (let i = 0; i < slots * 2 + 1; i += 1) rows.push(el("li", { class: i === slots ? "tide-cut" : "event event-compact event-blank" }));
        const node = el(
          "div",
          { class: "draft-tide" },
          el("header", { class: "tide-head" }, figure, caption),
          slots ? el("ol", { class: "tide-rows" }, ...rows) : el("p", { class: "empty", text: "No row of this draft has a share here." }),
        );
        return { node, figure, caption, rows, slots };
      });
      const ruled = el("p", { class: "draft-note" });
      const floored = el("p", { class: "draft-note" });
      const panel = el(
        "article",
        { class: "draft", "data-draft": draft.name, "aria-labelledby": titleId },
        el(
          "header",
          { class: "draft-head" },
          el("span", { class: "badge badge-draft", text: `draft #${draft.issue}`, title: `A draft share, calibrated for issue #${draft.issue}` }),
          el("h3", { class: "draft-title", id: titleId, text: draft.label }),
          el("span", { class: "draft-name", text: draft.name }),
        ),
        el(
          "div",
          { class: "draft-base", role: "group", "aria-label": `Base level of ${draft.label}` },
          el("span", { class: "control-label", text: "Base" }),
          el("span", { class: "base-options" }, ...bases),
        ),
        ruled,
        el("div", { class: "count-bar draft-bar", "aria-hidden": "true" }, ...segments),
        el("dl", { class: "draft-figures" }, ...figures.map((item) => item.node)),
        floored,
        el("div", { class: "draft-tides" }, ...tides.map((tide) => tide.node)),
      );
      return { draft, panel, bases, segments, figures, tides, ruled, floored };
    },

    fillDraft(view, rows) {
      const { draft } = view;
      const result = this.result.drafts[draft.name];
      const base = this.state.bases[draft.name];
      for (const button of view.bases) button.setAttribute("aria-pressed", String(button.dataset.level === base));
      const counts = result.level_counts;
      const total = this.levels.reduce((sum, level) => sum + counts.replay[level], 0);
      this.levels.forEach((level, i) => {
        const n = counts.replay[level];
        const was = counts.baseline[level];
        view.segments[i].style.flexBasis = total ? `${(n / total) * 100}%` : "0%";
        view.segments[i].hidden = n === 0;
        view.segments[i].textContent = n / Math.max(1, total) > 0.12 ? String(n) : "";
        const figure = view.figures[i];
        figure.count.textContent = String(n);
        figure.change.textContent = n === was ? "" : signed(n - was);
        figure.change.classList.toggle("moved", n !== was);
        figure.node.title = `${levelName(level)}: ${n} at base ${levelName(base)}, ${was} at its own base ${levelName(draft.base)}`;
        figure.node.classList.toggle("draft-figure-empty", n === 0 && was === 0);
      });
      const ruled = rows.filter((item) => item.row.ruled).length;
      view.ruled.textContent = ruled ? `${ruled} of ${plural(rows.length, "row")} ruled; the base does not apply to them` : `No row ruled; the base applies to ${rows.length === 1 ? "it" : `all ${rows.length}`}`;
      view.ruled.title = "A ruled row's level is set by its kind's context rule, so a base tried here leaves it as it is.";
      view.floored.textContent = `${result.floored} of ${plural(total, "row")} set by a cited event, not this share`;
      view.floored.title = "A cited event's score is the floor of the row's own, so this share cannot move these rows.";

      const shown = this.shownCutoffs();
      view.tides.forEach((tide, slot) => {
        const cutoff = shown[slot] || null;
        if (!cutoff) {
          tide.figure.textContent = "—";
          tide.caption.textContent = slot === 0 ? "No lower cut-off" : "No upper cut-off";
          tide.rows.forEach((node, i) => (i === tide.slots ? node.replaceChildren() : this.fillEventRow(node, null, { compact: true })));
          tide.node.classList.add("tide-empty");
          return;
        }
        tide.node.classList.remove("tide-empty");
        const sides = cutoff.drafts[draft.name] || { below: [], above: [] };
        tide.figure.textContent = fmt(cutoff.share);
        tide.figure.title = String(cutoff.share);
        tide.caption.textContent = `${sides.above.length} above · ${sides.below.length} below`;
        const above = [...sides.above].sort((a, b) => b.share - a.share);
        const below = [...sides.below].sort((a, b) => b.share - a.share);
        for (let i = 0; i < tide.slots; i += 1) {
          const top = above[i - (tide.slots - above.length)];
          this.fillEventRow(tide.rows[i], top ? this.draftItem(draft, top) : null, { compact: true });
          this.fillEventRow(tide.rows[tide.slots + 1 + i], below[i] ? this.draftItem(draft, below[i]) : null, { compact: true });
        }
        if (tide.slots) tide.rows[tide.slots].replaceChildren(el("span", { class: "tide-cut-label", text: `cut-off ${fmt(cutoff.share)}` }));
      });
    },

    // A draft row nearest a cut-off: it reads as the event it shadows and opens it, with the draft's badges.
    draftItem(draft, neighbour) {
      const row = (this.drafts[neighbour.campaign] || []).find((item) => item.id === neighbour.id);
      // A draft row's id is draft:<name>:<the id of the event it shadows> (drafts.py's draft_row_id).
      const shadowed = neighbour.id.slice(`draft:${draft.name}:`.length);
      const badges = [el("span", { class: "badge badge-draft", text: `draft #${draft.issue}`, title: `A row of the draft share ${draft.label} (#${draft.issue})` })];
      if (row && row.ruled) {
        badges.push(el("span", { class: "badge badge-ruled", text: "ruled", title: "Its kind's context rule sets the level; the draft's base does not apply." }));
      }
      return {
        campaign: neighbour.campaign,
        row: row || { id: neighbour.id, type: neighbour.type, label: shadowed, level: neighbour.oracle_level, date: null, shares: [] },
        level: neighbour.level,
        decidedBy: neighbour.decided_by,
        share: neighbour.share,
        measure: this.focus,
        score: neighbour.score,
        badges,
        opens: shadowed,
      };
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
          item.note = detail + (member.stale_share ? " · stale share" : "");
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
      const share = row.shares.find((item) => item.measure === this.focus) || row.shares[0] || null;
      return {
        campaign,
        row,
        level: event ? event.level : row.level,
        decidedBy: event ? event.decided_by : row.id,
        share: share ? share.share : null,
        measure: share ? share.measure : null,
        score: event ? event.score : row.score,
      };
    },

    // One event row, wherever the page lists events: the share (or —), the label, the cited badge, the level gauge
    // (old gauge → new one when it moved), campaign and date, then the type ID and any note. A list row sets the type
    // under the label, unless the list is of one type. A compact row keeps to one line for the tide tables and leaves
    // its type to the readout under the tide, so clicking anywhere on it opens the event: the inspector's hook (#490).
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
      const opens = item.opens || row.id;
      // A real row of a switched type whose level a context rule decided: the switch passes it by, so say why.
      const ruled =
        !item.opens && row.rule && this.isSwitched(row.type)
          ? el("span", {
              class: "badge badge-ruled",
              text: "ruled",
              title: `The ${row.rule} context rule decided its level; the ${levelName(this.typeBase(row.type))} base level tried for ${row.type} does not apply.`,
            })
          : null;
      const badges = [...(item.badges || []), ruled, item.decidedBy !== row.id ? this.citedBadge(item.campaign, row, item.decidedBy) : null].filter(Boolean);
      node.className = `event${compact ? " event-compact" : ""}${dimmed ? " dim" : ""}${Inspector.shows(item.campaign, opens) ? " event-open" : ""}`;
      node.tabIndex = 0;
      node.dataset.type = row.type;
      node.dataset.id = opens;
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
          el("span", { class: "event-share num", text: item.share === null ? "—" : fmt(item.share), title: item.measure && item.share !== null ? `${item.measure} share ${item.share}` : "No share of its own" }),
          el("span", { class: "event-main" }, el("span", { class: "event-label", text: label }), showType ? null : type),
          badges.length ? el("span", { class: "event-badges" }, ...badges) : null,
          el(
            "span",
            { class: `event-change${moved ? " moved" : ""}`, title: moved ? `${levelName(row.level)} → ${levelName(level)}` : levelName(level) },
            ...(moved ? levelMove(row.level, level) : [levelGauge(level)]),
            el("span", { class: "visually-hidden", text: moved ? `${levelName(row.level)} to ${levelName(level)}` : levelName(level) }),
          ),
          el("span", { class: "event-meta", text: `${compact ? item.campaign.slice(0, 4) : item.campaign} ${shortDate(row.date)}` }),
          sub.length ? el("span", { class: "event-sub" }, ...sub) : null,
        ].filter(Boolean),
      );
      return node;
    },

    // Every event row opens the inspector; a row inside the inspector swaps it to that event.
    openEvent(node, item) {
      Inspector.open(node, item.campaign, item.opens || item.row.id);
    },

    // --- Copy -------------------------------------------------------------------------------------------------

    copy() {
      const hash = this.hash;
      const text = [
        this.readout.snippet,
        "",
        this.readout.paragraph,
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
  // Page state only, never in the hash. The parts that the rise share cannot change are built once per event; level,
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

      // The type's base level, switchable here as in Base levels; a ruled event says the switch passes it by.
      const kind = App.index.kinds[row.type];
      const options = kind ? App.baseOptions(row.type, `Base level of ${row.type}`) : null;
      const baseCode = el("span", { class: "ins-base-code" });
      const ruled = kind && row.rule ? el("p", { class: "ins-ruled" }) : null;
      const baseSection = options
        ? el(
            "div",
            { class: "ins-base" },
            el("span", { class: "ins-base-label", text: "Type's base level" }),
            options.node,
            baseCode,
            ruled,
          )
        : null;

      const decided = el("li");
      const decidedSection = el(
        "section",
        { class: "ins-section", "aria-labelledby": "ins-decided" },
        el("h3", { class: "ins-head", id: "ins-decided", text: "Level set by" }),
        el("p", { class: "ins-lead", text: "A cited event sets this event's level, not its own share." }),
        el("ol", { class: "events" }, decided),
      );

      const shareRows = row.shares.map((share) => {
        const spec = App.index.measures[share.measure];
        const compare = el("span", { class: "ins-compare" });
        const tr = el(
          "tr",
          {},
          el("th", { scope: "row" }, el("span", { class: "ins-measure", text: spec ? spec.label : share.measure }), compare),
          el("td", { class: "num", text: fmt(share.share), title: String(share.share) }),
        );
        return { tr, compare, measure: share.measure, share: Number(share.share) };
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
        baseSection,
        decidedSection,
        el(
          "section",
          { class: "ins-section", "aria-labelledby": "ins-shares" },
          el("h3", { class: "ins-head", id: "ins-shares" }, "Shares", el("span", { class: "ins-count", text: String(row.shares.length) })),
          shareRows.length
            ? el("table", { class: "ins-table" }, el("tbody", {}, ...shareRows.map((item) => item.tr)))
            : el("p", { class: "ins-empty", text: "No shares: the base sets the score." }),
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
      this.parts = { campaign, id, position, row, level, score, base, baseButtons: options ? options.buttons : [], baseCode, ruled, decided, decidedSection, shareRows, cited, off };
    },

    // The focused share against the current rise share, written as the tide captions write a cut-off, and which side
    // of the window between the drop and the rise share the share falls on.
    compareText(share) {
      if (!(share > 0)) return "no share";
      const [drop, rise] = App.windowShares();
      const ratio = share / rise;
      const side = share < drop ? "below the window" : share > rise ? "above the window" : "in the window";
      const factor = fmt(ratio >= 1 ? ratio : 1 / ratio);
      return `${factor === "1" ? "at the rise share" : `rise share ${ratio >= 1 ? "×" : "÷"} ${factor}`} · ${side}`;
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

      parts.level.value.replaceChildren(levelGauge(level), levelName(level));
      const rank = (name) => App.levels.indexOf(name);
      const moved = level !== row.level;
      parts.level.note.className = `ins-note${moved ? (rank(level) > rank(row.level) ? " rise" : " drop") : ""}`;
      parts.level.note.textContent = moved ? `${rank(level) > rank(row.level) ? "rose" : "dropped"} from ${levelName(row.level)}` : "as the code's";
      parts.score.value.textContent = String(score);
      parts.score.note.textContent = score === row.score ? "as the code's" : `code's ${row.score}`;

      // The replay starts a rule-free row of a switched type from the tried level's base score.
      const switched = App.isSwitched(row.type);
      const tried = App.index.kinds[row.type] ? App.typeBase(row.type) : null;
      const applies = switched && row.rule === null;
      parts.base.value.textContent = String(applies ? App.meta.level_bases[tried] : row.base);
      parts.base.note.textContent = applies ? `tried ${levelName(tried)}; code's ${row.base}` : "before shares";
      parts.base.note.classList.toggle("moved", applies);
      if (parts.baseButtons.length) {
        App.syncBaseOptions(parts.baseButtons, row.type);
        const code = App.index.kinds[row.type].base;
        parts.baseCode.textContent = switched ? `code's ${levelName(code)}` : `the code's`;
        parts.baseCode.classList.toggle("moved", switched);
      }
      if (parts.ruled) {
        parts.ruled.textContent = switched
          ? `The ${row.rule} context rule decided this event's level, so the ${levelName(tried)} base level tried for ${row.type} does not apply to it.`
          : `The ${row.rule} context rule decided this event's level, so a base level tried for ${row.type} would not apply to it.`;
        parts.ruled.classList.toggle("ins-ruled-on", switched);
      }

      const decider = decidedBy !== row.id ? this.rowOf(campaign, decidedBy) : null;
      parts.decidedSection.hidden = decidedBy === row.id;
      if (decider) App.fillEventRow(parts.decided, App.eventItem(campaign, decider.position, result), {});
      else if (decidedBy !== row.id) parts.decided.replaceChildren(el("span", { class: "ins-entity-id", text: decidedBy }));

      for (const item of parts.shareRows) {
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
