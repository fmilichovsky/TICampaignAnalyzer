// The page's readout: the shared paragraph and the snippet of a replay, byte for byte as readout.py writes them.
//
// One classic script (file:// pages cannot load modules); it defines the single global TICalibrationReadout. Every
// number is written with String(number), which readout.py's js_number mirrors, and every string is ASCII.
(function (root) {
  "use strict";

  const TOP_MOVES = 5;

  const events = (count) => `${count} ${count === 1 ? "event" : "events"}`;
  const signed = (number) => (number > 0 ? `+${number}` : String(number));

  function move(item) {
    const via = item.via_cited ? ` (${item.via_cited} via a cited event)` : "";
    return `${item.type} ${item.from_level} -> ${item.to_level} ${item.count}${via}`;
  }

  // Every draft stake with its issue, its base and its rows' levels (readout.py's _drafts).
  function drafts(index, result) {
    const levels = Object.keys(index.constants.level_bands);
    const parts = index.drafts.map((draft) => {
      const own = result.drafts[draft.name];
      const counts = own.level_counts;
      const instead = own.base === draft.base ? "" : ` instead of ${draft.base}`;
      const shown = levels
        .filter((level) => counts.replay[level] || counts.baseline[level])
        .map(
          (level) =>
            `${level} ${counts.replay[level]}` +
            (counts.replay[level] !== counts.baseline[level] ? ` ${signed(counts.replay[level] - counts.baseline[level])}` : ""),
        );
      const total = levels.reduce((sum, level) => sum + counts.replay[level], 0);
      return (
        `${draft.name} (#${draft.issue}) at base ${own.base}${instead}: ${events(total)}` +
        (shown.length ? ` (${shown.join(", ")})` : "") +
        `, ${own.floored} set by a cited event`
      );
    });
    return parts.join("; ") || "none";
  }

  // One paragraph: the references against the code's, the clamp, campaigns and types, the totals, the top moves
  // and every draft stake with its issue.
  function sharedParagraph(index, result) {
    const state = result.state;
    const code = index.measures;
    const measures = Object.keys(code);
    const changed = measures
      .filter((measure) => state.references[measure] !== code[measure].reference)
      .map((measure) => `${measure} ${String(state.references[measure])} (code ${String(code[measure].reference)})`);
    let references;
    if (changed.length === 0) references = "every measure at the code's";
    else if (changed.length === measures.length) references = changed.join(", ");
    else references = `${changed.join(", ")}; every other measure at the code's`;
    const switched = Object.entries(state.type_bases).map(
      ([type, level]) => `${type} ${level} (code ${index.kinds[type].base})`,
    );
    let bases;
    if (switched.length === 0) bases = "every type at the code's";
    else if (switched.length === Object.keys(index.kinds).length) bases = switched.join(", ");
    else bases = `${switched.join(", ")}; every other type at the code's`;
    const totals = result.totals;
    const pkg = totals.package;
    const moves = result.moves.slice(0, TOP_MOVES).map(move).join("; ") || "nothing";
    return (
      `References: ${references}. ` +
      `Base levels: ${bases}. ` +
      `Clamp ${state.clamp ? "on" : "off"}. ` +
      `Campaigns: ${state.campaigns.join(", ") || "none"}. ` +
      `Types: ${state.types.join(", ") || "all"}. ` +
      `${events(totals.events_moved)} move level; ` +
      `the narrator package goes from ${pkg.baseline} to ${pkg.replay} ` +
      `${pkg.replay === 1 ? "event" : "events"} at ${index.constants.package_level} or above ` +
      `(${signed(pkg.change)}); ` +
      `${events(totals.members_changed)} with members change. ` +
      `What moves: ${moves}. ` +
      `Drafts: ${drafts(index, result)}.`
    );
  }

  // The changed references as measure registry entries, one line each in index order, then one comment line per
  // switched event type, sorted by type.
  function snippet(index, result) {
    const references = result.state.references;
    const lines = Object.entries(index.measures)
      .filter(([measure, spec]) => references[measure] !== spec.reference)
      .map(
        ([measure, spec]) =>
          `StakeMeasure.${measure.toUpperCase()}: MeasureSpec(reference=${String(references[measure])}, ...),` +
          `  # code: ${String(spec.reference)}`,
      );
    for (const [type, level] of Object.entries(result.state.type_bases)) {
      lines.push(`# ${type}: base ${index.kinds[type].base.toUpperCase()} -> ${level.toUpperCase()}`);
    }
    return lines.length > 0 ? lines.join("\n") : "# Every reference and base level is the code's.";
  }

  root.TICalibrationReadout = Object.freeze({ TOP_MOVES, sharedParagraph, snippet });
})(globalThis);
