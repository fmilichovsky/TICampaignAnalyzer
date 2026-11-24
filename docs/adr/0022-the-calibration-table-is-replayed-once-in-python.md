# The calibration table is replayed once, in Python

The calibration page shows how the sample campaigns' events change level when a share's reference or a base level
changes. Each of those changes is a replay of the calibration table, and the same replay backs
`benchmark calibrate report`.

- **One replay.** `replay.py` is the only code that rescores the table, encodes and decodes a calibration state's
  hash, and words the shared paragraph and the snippet of the readout.
- **The page is a renderer.** `benchmark calibrate open` serves the page from a small local server on `127.0.0.1`
  and blocks until it is interrupted. The page sends the server a state hash or the values of its controls, and
  draws the answer: the state, its canonical hash, the replay and the readout texts. The page holds no scoring, no
  state codec and no readout wording, and treats the hash as an opaque string.
- **The answer is compact.** Per row it carries only what a state changes (score, level, the deciding row), plus the
  aggregates the page shows; the page reads the row facts that never change from the tables it loads as files.
  While a control moves, the page may ask for a summary answer instead: the same answer without the per-row columns
  and the readout texts, which only a settled state draws. It asks for the full answer when the control settles.

## Considered options

- **A page that works from `file://`.** It was built and dropped. A page opened from disk cannot ask Python
  anything, so it forced a second implementation in JavaScript: the replay and the readout, kept byte for byte equal
  to Python. That needed a hand-ported `log10`, because every libm and JavaScript engine rounds its own way, and
  JavaScript number formatting emulated in Python. The parity could only be tested in Node, outside `make check`,
  and every change to scoring was written twice.

Tracked in #591.
