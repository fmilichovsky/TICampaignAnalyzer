"""A synthetic samples directory for the benchmark tests."""

from __future__ import annotations

import json
import lzma
from pathlib import Path

from tests.fixtures import fixture_path
from tinarrative.benchmarking.manifest import MANIFEST, update_samples

SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]


def synthetic_samples(root: Path) -> Path:
    """A samples directory of one campaign: the synthetic politics saves, compressed, with its manifest."""
    samples = root / "samples"
    campaign = samples / "politics"
    campaign.mkdir(parents=True)
    for name in SAVES:
        (campaign / f"{name}.xz").write_bytes(
            lzma.compress(fixture_path("io", "terra_invicta_json_v1", name).read_bytes())
        )
    manifest = update_samples(samples)
    manifest["campaigns"]["politics"]["description"] = "Synthetic politics sequence."
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return samples
