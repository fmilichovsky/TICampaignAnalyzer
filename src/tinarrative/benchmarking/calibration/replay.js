// The browser replay: the calibration table rescored for a calibration state, and the state's URL-hash codec.
//
// A port of replay.py, whose TypedDicts and docstrings are the contract: replay(...) gives the same JSON, and
// encodeState(...) the same bytes. One classic script (file:// pages cannot load modules); it defines the single
// global TICalibrationReplay. Every constant of the pipeline comes from the index; nothing here is tuned.
(function (root) {
  "use strict";

  const SCHEMA_VERSION = 1;
  const STATE_KEYS = ["ref", "clamp", "campaigns", "types", "focus"];

  class ReplayError extends Error {
    constructor(message) {
      super(message);
      this.name = "ReplayError";
    }
  }

  class ReplayStateError extends ReplayError {
    constructor(message) {
      super(message);
      this.name = "ReplayStateError";
    }
  }

  const has = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const repr = (value) => (typeof value === "string" ? `'${value}'` : String(value));
  const compare = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  function compareTuples(a, b) {
    for (let i = 0; i < a.length; i += 1) {
      const order = compare(a[i], b[i]);
      if (order !== 0) return order;
    }
    return 0;
  }

  // Python's round(): halves go to the even neighbour. x - floor(x) is exact for every double.
  function roundHalfEven(x) {
    const floor = Math.floor(x);
    const fraction = x - floor;
    if (fraction > 0.5) return floor + 1;
    if (fraction < 0.5) return floor;
    return floor % 2 === 0 ? floor : floor + 1;
  }

  // --- Portable log10 --------------------------------------------------------------------------------------
  // fdlibm 5.3's __ieee754_log10 and __ieee754_log, as replay.py's portable_log10 ports them: engines round
  // Math.log10 their own way, so both replays use this one.

  const TWO54 = 1.80143985094819840000e16;
  const LN2_HI = 6.93147180369123816490e-1;
  const LN2_LO = 1.90821492927058770002e-10;
  const LG1 = 6.666666666666735130e-1;
  const LG2 = 3.999999999940941908e-1;
  const LG3 = 2.857142874366239149e-1;
  const LG4 = 2.222219843214978396e-1;
  const LG5 = 1.818357216161805012e-1;
  const LG6 = 1.531383769920937332e-1;
  const LG7 = 1.479819860511658591e-1;
  const IVLN10 = 4.34294481903251816668e-1;
  const LOG10_2HI = 3.01029995663611771306e-1;
  const LOG10_2LO = 3.69423907715893078616e-13;

  const words = new DataView(new ArrayBuffer(8));

  function highWord(x) {
    words.setFloat64(0, x);
    return words.getInt32(0);
  }

  function lowWord(x) {
    words.setFloat64(0, x);
    return words.getUint32(4);
  }

  function withHighWord(x, high) {
    words.setFloat64(0, x);
    words.setInt32(0, high | 0);
    return words.getFloat64(0);
  }

  function log(x) {
    let hx = highWord(x);
    let k = (hx >> 20) - 1023;
    hx &= 0x000fffff;
    let i = (hx + 0x95f64) & 0x100000;
    x = withHighWord(x, hx | (i ^ 0x3ff00000));
    k += i >> 20;
    const f = x - 1.0;
    if ((0x000fffff & (2 + hx)) < 3) {
      if (f === 0.0) {
        if (k === 0) return 0.0;
        return k * LN2_HI + k * LN2_LO;
      }
      const r = f * f * (0.5 - 0.33333333333333333 * f);
      if (k === 0) return f - r;
      return k * LN2_HI - ((r - k * LN2_LO) - f);
    }
    const s = f / (2.0 + f);
    const dk = k;
    const z = s * s;
    i = hx - 0x6147a;
    const w = z * z;
    const j = 0x6b851 - hx;
    const t1 = w * (LG2 + w * (LG4 + w * LG6));
    const t2 = z * (LG1 + w * (LG3 + w * (LG5 + w * LG7)));
    i |= j;
    const r = t2 + t1;
    if (i > 0) {
      const hfsq = 0.5 * f * f;
      if (k === 0) return f - (hfsq - s * (hfsq + r));
      return dk * LN2_HI - ((hfsq - (s * (hfsq + r) + dk * LN2_LO)) - f);
    }
    if (k === 0) return f - s * (f - r);
    return dk * LN2_HI - ((s * (f - r) - dk * LN2_LO) - f);
  }

  function log10(x) {
    let hx = highWord(x);
    const lx = lowWord(x);
    let k = 0;
    if (hx < 0x00100000) {
      if (((hx & 0x7fffffff) | lx) === 0) return -Infinity;
      if (hx < 0) return NaN;
      k -= 54;
      x *= TWO54;
      hx = highWord(x);
    }
    if (hx >= 0x7ff00000) return x + x;
    k += (hx >> 20) - 1023;
    const i = k < 0 ? 1 : 0;
    hx = (hx & 0x000fffff) | ((0x3ff - i) << 20);
    const y = k + i;
    x = withHighWord(x, hx);
    const z = y * LOG10_2LO + IVLN10 * log(x);
    return z + y * LOG10_2HI;
  }

  // --- Replay ----------------------------------------------------------------------------------------------

  function defaultState(index) {
    const references = {};
    for (const [name, measure] of Object.entries(index.measures)) references[name] = Number(measure.reference);
    return { references, clamp: true, campaigns: [...index.campaigns], types: [], focus: null };
  }

  function replay(index, tables, state) {
    validate(index, tables, state);
    const constants = index.constants;
    const levels = Object.keys(constants.level_bands);
    const gates = index.member_gates.map((gate) => ({
      groupTypes: new Set(gate.group_types),
      memberType: gate.member_type,
      admitted: new Set(gate.admitted_levels),
      minimum: gate.minimum,
    }));
    const types = new Set(state.types);
    const scored = {};
    const selected = {};
    for (const name of state.campaigns) {
      scored[name] = replayCampaign(index, tables[name], state, gates);
      selected[name] = scored[name].filter((item) => types.size === 0 || types.has(item.row.type));
    }
    const every = state.campaigns.flatMap((name) => selected[name]);
    const campaigns = {};
    for (const name of state.campaigns) {
      campaigns[name] = {
        events: scored[name].map((item) => ({
          id: item.row.id,
          score: item.score,
          level: item.level,
          decided_by: item.decidedBy,
        })),
        level_counts: levelCounts(selected[name], levels),
        members: selected[name].filter((item) => item.member !== null).map((item) => item.member),
      };
    }
    const cutoffs = {};
    for (const measure of Object.keys(index.measures)) cutoffs[measure] = measureCutoffs(measure, state, constants, selected);
    return {
      schema_version: SCHEMA_VERSION,
      state: {
        references: Object.assign({}, state.references),
        clamp: state.clamp,
        campaigns: [...state.campaigns],
        types: [...state.types],
        focus: state.focus,
      },
      campaigns,
      totals: totals(every, levels, constants.package_level),
      moves: moves(every, levels),
      cutoffs,
    };
  }

  function validate(index, tables, state) {
    const measures = Object.keys(index.measures);
    const given = Object.keys(state.references);
    if (compareTuples([...given].sort(), [...measures].sort()) !== 0 || given.length !== measures.length) {
      throw new ReplayStateError(`the state needs a reference for exactly the measures ${measures.join(", ")}`);
    }
    for (const [measure, value] of Object.entries(state.references)) {
      if (!Number.isFinite(value) || value <= 0) {
        throw new ReplayStateError(`the reference of ${measure} must be a positive number, not ${repr(value)}`);
      }
    }
    for (const name of state.campaigns) {
      if (!has(tables, name)) {
        throw new ReplayStateError(`unknown campaign ${repr(name)} (known: ${Object.keys(tables).join(", ")})`);
      }
    }
    const known = new Set();
    for (const rows of Object.values(tables)) for (const row of rows) known.add(row.type);
    const unknown = [...new Set(state.types)].filter((type) => !known.has(type)).sort(compare);
    if (unknown.length > 0) {
      throw new ReplayStateError(`unknown event type(s) in the filter: ${unknown.join(", ")}`);
    }
    if (state.focus !== null && !measures.includes(state.focus)) {
      throw new ReplayStateError(`unknown focus measure ${repr(state.focus)}`);
    }
  }

  function replayCampaign(index, rows, state, gates) {
    const constants = index.constants;
    const bands = Object.entries(constants.level_bands).map(([level, [low, high]]) => ({ level, low, high }));
    const layer = (row) => (row.tier === "narrative" ? Number(has(index.layers, row.type) ? index.layers[row.type] : 0) : 0);
    const byId = new Map(rows.map((row) => [row.id, row]));
    const done = new Map();
    const ordered = rows
      .map((row, position) => ({ row, position, layer: layer(row) }))
      .sort((a, b) => a.layer - b.layer || a.position - b.position);
    for (const { row, layer: ownLayer } of ordered) {
      for (const cited of row.cited) {
        if (!byId.has(cited)) throw new ReplayError(`${row.id} cites ${cited}, which is not a row of its campaign`);
        if (layer(byId.get(cited)) >= ownLayer) {
          throw new ReplayError(`${row.id} (layer ${ownLayer}) cites ${cited}, which is not in an earlier layer`);
        }
      }
      const gate = gates.find((candidate) => candidate.groupTypes.has(row.type)) || null;
      let citedRows = row.cited.map((cited) => done.get(cited));
      let lost = [];
      if (gate !== null) {
        lost = citedRows
          .filter((item) => item.row.type === gate.memberType && !gate.admitted.has(item.level))
          .map((item) => item.row.id);
        citedRows = citedRows.filter((item) => !lost.includes(item.row.id));
      }
      const own = ownScore(row, state, constants);
      let best = null;
      for (const item of citedRows) if (best === null || item.score > best.score) best = item;
      let score = own;
      let decidedBy = row.id;
      if (best !== null && own < best.score) {
        score = best.score;
        decidedBy = best.decidedBy;
      }
      const level = bands.find((band) => band.low <= score && score <= band.high).level;
      const item = { row, score, level, decidedBy, member: null };
      if (gate !== null) item.member = groupVerdict(row, gate, citedRows, lost);
      done.set(row.id, item);
    }
    for (const item of done.values()) {
      const gate = gates.find((candidate) => item.row.type === candidate.memberType) || null;
      if (gate !== null && !gate.admitted.has(item.row.level) && gate.admitted.has(item.level)) {
        item.member = {
          id: item.row.id,
          type: item.row.type,
          verdict: "could_become_member",
          kept: [],
          lost: [],
          distinct: 0,
          minimum: gate.minimum,
          stale_stake: false,
        };
      }
    }
    return rows.map((row) => done.get(row.id));
  }

  function ownScore(row, state, constants) {
    const base = row.base;
    if (row.stakes.length === 0) return base;
    const scales = row.stakes
      .map((stake) => scale(stake.share, state.references[stake.measure], state.clamp, constants))
      .filter((value) => value !== null);
    if (scales.length === 0) return constants.score_min;
    return Math.max(constants.score_min, Math.min(constants.score_max, base + Math.max(...scales)));
  }

  function scale(share, reference, clamp, constants) {
    const low = constants.scale_min;
    const high = constants.scale_max;
    if (share <= 0) return clamp ? low : null;
    const value = roundHalfEven(10 * log10(share / reference));
    return clamp ? Math.max(low, Math.min(high, value)) : value;
  }

  function groupVerdict(row, gate, keptRows, lost) {
    const kept = keptRows.filter((item) => item.row.type === gate.memberType);
    // The group's first entity is its actor (ADR-0009); the rest are the members' distinct entities.
    const held = new Set();
    for (const item of kept) for (const entity of item.row.entities) held.add(entity.id);
    const distinct = row.entities.slice(1).filter((entity) => held.has(entity.id)).length;
    let verdict = "keeps_members";
    if (lost.length > 0) verdict = distinct >= gate.minimum ? "loses_members" : "falls_apart";
    return {
      id: row.id,
      type: row.type,
      verdict,
      kept: kept.map((item) => item.row.id),
      lost: [...lost],
      distinct,
      minimum: gate.minimum,
      stale_stake: lost.length > 0,
    };
  }

  const fallen = (item) => item.member !== null && item.member.verdict === "falls_apart";

  function levelCounts(items, levels) {
    const count = (pairs) => {
      const counts = new Map();
      for (const key of pairs) counts.set(key, (counts.get(key) || 0) + 1);
      return counts;
    };
    const key = (type, level) => JSON.stringify([type, level]);
    const replayed = count(items.filter((item) => !fallen(item)).map((item) => key(item.row.type, item.level)));
    const baseline = count(items.map((item) => key(item.row.type, item.row.level)));
    const result = {};
    for (const type of [...new Set(items.map((item) => item.row.type))].sort(compare)) {
      const replayCounts = {};
      const baselineCounts = {};
      for (const level of levels) replayCounts[level] = replayed.get(key(type, level)) || 0;
      for (const level of levels) baselineCounts[level] = baseline.get(key(type, level)) || 0;
      result[type] = { replay: replayCounts, baseline: baselineCounts };
    }
    return result;
  }

  function totals(items, levels, packageLevel) {
    const packaged = new Set(levels.slice(levels.indexOf(packageLevel)));
    const narrative = items.filter((item) => item.row.tier === "narrative");
    const replayed = narrative.filter((item) => packaged.has(item.level) && !fallen(item)).length;
    const baseline = narrative.filter((item) => packaged.has(item.row.level)).length;
    return {
      events_moved: items.filter((item) => item.level !== item.row.level && !fallen(item)).length,
      package: { replay: replayed, baseline, change: replayed - baseline },
      members_changed: items.filter(
        (item) => item.member !== null && (item.member.verdict === "loses_members" || item.member.verdict === "falls_apart"),
      ).length,
    };
  }

  function moves(items, levels) {
    const groups = new Map();
    for (const item of items) {
      if (item.level === item.row.level || fallen(item)) continue;
      const key = JSON.stringify([item.row.type, item.row.level, item.level]);
      const group = groups.get(key) || { type: item.row.type, from: item.row.level, to: item.level, count: 0, via: 0 };
      group.count += 1;
      group.via += item.decidedBy !== item.row.id ? 1 : 0;
      groups.set(key, group);
    }
    const rank = (group) => [-group.count, group.type, levels.indexOf(group.from), levels.indexOf(group.to)];
    return [...groups.values()]
      .sort((a, b) => compareTuples(rank(a), rank(b)))
      .map((group) => ({
        type: group.type,
        from_level: group.from,
        to_level: group.to,
        count: group.count,
        via_cited: group.via,
      }));
  }

  // Every log10(share / reference) at which a stake moves an event of some base level one more level, ascending;
  // with the clamp, only those the scale window reaches (replay.py's cutoff_offsets).
  function cutoffOffsets(constants, clamp) {
    const bands = Object.values(constants.level_bands);
    const offsets = new Set();
    for (const [low, high] of bands) {
      const base = Math.floor((low + high) / 2);
      for (const [otherLow, otherHigh] of bands) {
        if (otherLow > base) offsets.add((otherLow - base - 0.5) / 10);
        if (otherHigh < base) offsets.add((otherHigh - base + 0.5) / 10);
      }
    }
    let result = [...offsets];
    if (clamp) {
      result = result.filter((offset) => constants.scale_min <= 10 * offset && 10 * offset <= constants.scale_max);
    }
    return result.sort((a, b) => a - b);
  }

  function measureCutoffs(measure, state, constants, selected) {
    const reference = state.references[measure];
    const candidates = [];
    for (const name of state.campaigns) {
      for (const item of selected[name]) {
        const share = candidate(item.row, measure);
        if (share !== null && share > 0) candidates.push({ name, item, share });
      }
    }
    const window = cutoffOffsets(constants, true);
    const result = [];
    for (const offset of cutoffOffsets(constants, state.clamp)) {
      const cut = reference * Math.pow(10, offset);
      if (!window.includes(offset) && !candidates.some(({ share }) => (offset < 0 ? share < cut : share > cut))) continue;
      const below = [];
      const above = [];
      for (const { name, item, share } of candidates) {
        const side = share < cut || (share === cut && offset > 0) ? below : above;
        side.push(neighbour(name, item, share, Math.abs(log10(share / cut))));
      }
      result.push({
        offset,
        share: cut,
        below: nearest(below, state.campaigns, constants.neighbours),
        above: nearest(above, state.campaigns, constants.neighbours),
      });
    }
    return result;
  }

  function nearest(side, campaigns, neighbours) {
    const rank = (item) => [item.distance, campaigns.indexOf(item.campaign), item.id];
    return [...side].sort((a, b) => compareTuples(rank(a), rank(b))).slice(0, neighbours);
  }

  function candidate(row, measure) {
    const stake = row.stakes.find((item) => item.measure === measure);
    return stake === undefined ? null : Number(stake.share);
  }

  function neighbour(campaign, item, share, distance) {
    return {
      campaign,
      id: item.row.id,
      type: item.row.type,
      share,
      distance,
      score: item.score,
      level: item.level,
      oracle_level: item.row.level,
      decided_by: item.decidedBy,
      decisive: item.decidedBy === item.row.id,
    };
  }

  // --- State codec -----------------------------------------------------------------------------------------

  const NUMBER = /^(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/;
  const NAME = /^[A-Za-z0-9._-]+$/;

  // The URL hash of a state, without the "#"; "" for the default state (replay.py's encode_state).
  function encodeState(state, index) {
    const fallback = defaultState(index);
    const fields = [];
    const changed = Object.keys(index.measures)
      .filter((measure) => state.references[measure] !== fallback.references[measure])
      .map((measure) => `${measure}:${String(state.references[measure])}`);
    if (changed.length > 0) fields.push(`ref=${changed.join(",")}`);
    if (!state.clamp) fields.push("clamp=off");
    const campaigns = index.campaigns.filter((name) => state.campaigns.includes(name));
    if (compareTuples(campaigns, fallback.campaigns) !== 0 || campaigns.length !== fallback.campaigns.length) {
      fields.push(`campaigns=${campaigns.join(",")}`);
    }
    if (state.types.length > 0) fields.push(`types=${[...state.types].sort(compare).join(",")}`);
    if (state.focus !== null) fields.push(`focus=${state.focus}`);
    return fields.join("&");
  }

  // The state of a URL hash; a leading "#" and any key order are accepted (replay.py's decode_state).
  function decodeState(text, index) {
    const state = defaultState(index);
    const body = text.startsWith("#") ? text.slice(1) : text;
    const seen = new Set();
    for (const field of body ? body.split("&") : []) {
      const separator = field.indexOf("=");
      if (separator < 0) throw new ReplayStateError(`state hash field ${repr(field)} is not key=value`);
      const key = field.slice(0, separator);
      const value = field.slice(separator + 1);
      if (!STATE_KEYS.includes(key)) {
        throw new ReplayStateError(`unknown state hash key ${repr(key)} (known: ${STATE_KEYS.join(", ")})`);
      }
      if (seen.has(key)) throw new ReplayStateError(`state hash key ${repr(key)} is repeated`);
      seen.add(key);
      if (key === "ref") {
        Object.assign(state.references, decodeReferences(value, index));
      } else if (key === "clamp") {
        if (value !== "on" && value !== "off") {
          throw new ReplayStateError(`state hash clamp must be on or off, not ${repr(value)}`);
        }
        state.clamp = value === "on";
      } else if (key === "campaigns") {
        const names = parseNames(value, "campaign", true);
        const unknown = names.filter((name) => !index.campaigns.includes(name));
        if (unknown.length > 0) {
          throw new ReplayStateError(
            `unknown campaign(s) in the state hash: ${unknown.join(", ")} (known: ${index.campaigns.join(", ")})`,
          );
        }
        state.campaigns = index.campaigns.filter((name) => names.includes(name));
      } else if (key === "types") {
        state.types = parseNames(value, "type", false).sort(compare);
      } else {
        if (!has(index.measures, value)) throw new ReplayStateError(`unknown focus measure ${repr(value)} in the state hash`);
        state.focus = value;
      }
    }
    return state;
  }

  function decodeReferences(value, index) {
    const references = {};
    if (!value) throw new ReplayStateError("state hash key 'ref' lists no reference");
    for (const item of value.split(",")) {
      const separator = item.indexOf(":");
      if (separator < 0) throw new ReplayStateError(`state hash reference ${repr(item)} is not measure:number`);
      const measure = item.slice(0, separator);
      const number = item.slice(separator + 1);
      if (!has(index.measures, measure)) {
        throw new ReplayStateError(
          `unknown measure ${repr(measure)} in the state hash (known: ${Object.keys(index.measures).join(", ")})`,
        );
      }
      if (has(references, measure)) throw new ReplayStateError(`measure ${repr(measure)} is repeated in the state hash`);
      const parsed = NUMBER.test(number) ? Number(number) : NaN;
      if (!Number.isFinite(parsed) || parsed <= 0) {
        throw new ReplayStateError(`the reference of ${measure} must be a positive number, not ${repr(number)}`);
      }
      references[measure] = parsed;
    }
    return references;
  }

  function parseNames(value, what, allowEmpty) {
    if (!value) {
      if (allowEmpty) return [];
      throw new ReplayStateError(`state hash lists no ${what}`);
    }
    const names = value.split(",");
    for (const name of names) {
      if (!NAME.test(name)) throw new ReplayStateError(`state hash ${what} ${repr(name)} is not a name`);
    }
    const repeated = [...new Set(names.filter((name, i) => names.indexOf(name) !== i))].sort(compare);
    if (repeated.length > 0) throw new ReplayStateError(`${what}(s) repeated in the state hash: ${repeated.join(", ")}`);
    return names;
  }

  root.TICalibrationReplay = Object.freeze({
    SCHEMA_VERSION,
    STATE_KEYS: Object.freeze([...STATE_KEYS]),
    ReplayError,
    ReplayStateError,
    defaultState,
    replay,
    encodeState,
    decodeState,
    cutoffOffsets,
    log10,
    roundHalfEven,
  });
})(globalThis);
