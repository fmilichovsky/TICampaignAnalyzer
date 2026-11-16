// Runs replay.js and readout.js over a calibration table the way a file:// page does, for
// tests/benchmarking/browser_replay.py. readout.js is read from beside replay.js.
//
// node replay_harness.js <replay.js> <table directory>
// stdin: a JSON list of requests ({op: "replay" | "decode" | "readout", hash}, {op: "encode", state},
// {op: "log10" | "round", values}); stdout: a JSON list of {ok: <JSON.stringify(result)>} or {error: {name, message}}, one per request.
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

function load(context, file) {
  new vm.Script(fs.readFileSync(file, "utf8"), { filename: file }).runInContext(context);
}

const [replayPath, tableDirectory] = process.argv.slice(2);
const context = vm.createContext({});
context.window = context;
context.TI_CALIBRATION = { campaigns: {} };
load(context, path.join(tableDirectory, "index.js"));
const index = context.TI_CALIBRATION.index;
for (const name of index.campaigns) load(context, path.join(tableDirectory, "tables", `${name}.js`));

const before = new Set(Object.getOwnPropertyNames(context));
load(context, replayPath);
const added = Object.getOwnPropertyNames(context).filter((name) => !before.has(name));
if (added.length !== 1 || added[0] !== "TICalibrationReplay") {
  throw new Error(`replay.js must add exactly the global TICalibrationReplay, not ${added.join(", ")}`);
}
const api = context.TICalibrationReplay;
const loaded = new Set(Object.getOwnPropertyNames(context));
load(context, path.join(path.dirname(replayPath), "readout.js"));
const readoutGlobals = Object.getOwnPropertyNames(context).filter((name) => !loaded.has(name));
if (readoutGlobals.length !== 1 || readoutGlobals[0] !== "TICalibrationReadout") {
  throw new Error(`readout.js must add exactly the global TICalibrationReadout, not ${readoutGlobals.join(", ")}`);
}
const readout = context.TICalibrationReadout;
const tables = {};
const drafts = {};
for (const name of index.campaigns) {
  tables[name] = context.TI_CALIBRATION.campaigns[name].events;
  drafts[name] = context.TI_CALIBRATION.campaigns[name].drafts;
}

const operations = {
  replay: (request) => api.replay(index, tables, api.decodeState(request.hash, index), drafts),
  decode: (request) => api.decodeState(request.hash, index),
  readout: (request) => {
    const result = api.replay(index, tables, api.decodeState(request.hash, index), drafts);
    return { paragraph: readout.sharedParagraph(index, result), snippet: readout.snippet(index, result) };
  },
  encode: (request) => api.encodeState(request.state, index),
  log10: (request) => request.values.map(api.log10),
  round: (request) => request.values.map(api.roundHalfEven),
  constants: () => ({ SCHEMA_VERSION: api.SCHEMA_VERSION, STATE_KEYS: [...api.STATE_KEYS] }),
};

const requests = JSON.parse(fs.readFileSync(0, "utf8"));
const answers = requests.map((request) => {
  try {
    return { ok: JSON.stringify(operations[request.op](request)) };
  } catch (error) {
    if (!(error instanceof api.ReplayError)) throw error;
    return { error: { name: error.name, message: error.message } };
  }
});
process.stdout.write(JSON.stringify(answers));
