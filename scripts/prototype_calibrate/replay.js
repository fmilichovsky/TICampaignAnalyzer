// PROTOTYPE, throwaway (#452). Replays every row's score at a given set of references.
// own = clamp(base + scale(share, reference)); a narrative event's final score is the max of its own and its cited
// events' final scores (ADR-0011). Without a basis, the own score is fixed.
(function (root) {
  const CODE_REFS = {
    power: 0.01, population: 0.01, organization: 0.01, hab: 0.015, fleet: 0.01, battle: 0.0033,
    faction: 1 / 7, nuclear: 0.01, boost: 0.01, mission_control: 0.01,
  };
  const BANDS = [
    ["trivial", 0, 24], ["minor", 25, 49], ["major", 50, 74], ["campaign_defining", 75, 100],
  ];
  const LEVELS = BANDS.map((b) => b[0]);
  const BASES = { trivial: 12, minor: 37, major: 62, campaign_defining: 87 };
  const SCALE_MIN = -20, SCALE_MAX = 15;

  function pyRound(x) {
    const r = Math.round(x);
    return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
  }
  function scale(share, ref, clamp) {
    if (share <= 0) return SCALE_MIN;
    const r = pyRound(10 * Math.log10(share / ref));
    return clamp ? Math.max(SCALE_MIN, Math.min(SCALE_MAX, r)) : r;
  }
  const clamp100 = (x) => Math.max(0, Math.min(100, x));
  const levelOf = (score) => (score >= 75 ? 3 : score >= 50 ? 2 : score >= 25 ? 1 : 0);

  function fixedOwn(rows) {
    // own score of a basis-less row; pipeline score bounds it when a cited event decided it
    return rows.map((r) => {
      if (r.m) return null;
      if (r.s !== "n" || !r.ci) return r.p;
      const cited = Math.max(...r.ci.map((i) => rows[i].p));
      return r.p > cited ? r.p : Math.min(r.kb, r.p);
    });
  }

  // Returns {score: Int16Array, own, decided: Int32Array (row index whose own score set the final)}
  function replay(rows, refs, opts) {
    const clamp = opts.clamp !== false;
    const fixed = opts.fixed || (opts.fixed = fixedOwn(rows));
    const n = rows.length;
    const own = new Int16Array(n), score = new Int16Array(n).fill(-1), decided = new Int32Array(n);
    for (let i = 0; i < n; i++) {
      const r = rows[i];
      own[i] = r.m ? clamp100(r.b + scale(r.sh, refs[r.m], clamp)) : fixed[i];
    }
    function final(i) {
      if (score[i] >= 0) return score[i];
      const r = rows[i];
      let best = own[i], by = i;
      if (r.s === "n" && r.ci) {
        for (const j of r.ci) {
          const s = final(j);
          if (s > best) { best = s; by = decided[j]; }
        }
      }
      score[i] = best; decided[i] = by;
      return best;
    }
    for (let i = 0; i < n; i++) final(i);
    return { score, own, decided };
  }

  // A draft row: own from the draft's chosen base and the max of its candidates' scales; floor = its cited events.
  function replayDraft(d, rows, real, refs, base, clamp) {
    let s = -Infinity, by = null;
    for (const [m, share] of Object.entries(d.cand)) {
      const k = scale(share, refs[m], clamp);
      if (k > s) { s = k; by = m; }
    }
    const own = clamp100(base + s);
    const floor = d.ci ? Math.max(...d.ci.map((i) => real.score[i])) : -1;
    return { score: Math.max(own, floor), own, floored: floor > own, by };
  }

  const api = { CODE_REFS, LEVELS, BASES, SCALE_MIN, SCALE_MAX, pyRound, scale, levelOf, replay, replayDraft };
  if (typeof module !== "undefined") module.exports = api;
  else root.Replay = api;
})(this);
