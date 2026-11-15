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

  // One paragraph: the references against the code's, the clamp, campaigns and types, the totals, the top moves.
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
    const totals = result.totals;
    const pkg = totals.package;
    const moves = result.moves.slice(0, TOP_MOVES).map(move).join("; ") || "nothing";
    return (
      `References: ${references}. ` +
      `Clamp ${state.clamp ? "on" : "off"}. ` +
      `Campaigns: ${state.campaigns.join(", ") || "none"}. ` +
      `Types: ${state.types.join(", ") || "all"}. ` +
      `${events(totals.events_moved)} move level; ` +
      `the narrator package goes from ${pkg.baseline} to ${pkg.replay} ` +
      `${pkg.replay === 1 ? "event" : "events"} at ${index.constants.package_level} or above ` +
      `(${signed(pkg.change)}); ` +
      `${events(totals.members_changed)} with members change. ` +
      `What moves: ${moves}.`
    );
  }

  // The changed references as measure registry entries, one line each in index order.
  function snippet(index, result) {
    const references = result.state.references;
    const lines = Object.entries(index.measures)
      .filter(([measure, spec]) => references[measure] !== spec.reference)
      .map(
        ([measure, spec]) =>
          `StakeMeasure.${measure.toUpperCase()}: MeasureSpec(reference=${String(references[measure])}, ...),` +
          `  # code: ${String(spec.reference)}`,
      );
    return lines.length > 0 ? lines.join("\n") : "# Every reference is the code's.";
  }

  root.TICalibrationReadout = Object.freeze({ TOP_MOVES, sharedParagraph, snippet });
})(globalThis);
