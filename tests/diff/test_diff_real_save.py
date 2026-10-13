"""Opt-in check that diffing two real consecutive saves is deterministic and fully evidenced (never committed)."""

import json
import os
from pathlib import Path

import pytest

from tinarrative.diff.state_diff import ChangeKind, diff_states
from tinarrative.io.save_loader import load_raw_save
from tinarrative.parsing.normalization import normalize

pytestmark = pytest.mark.real_save


def real_save_pair() -> tuple[Path, Path]:
    before = os.environ.get("TINARRATIVE_REAL_SAVE")
    after = os.environ.get("TINARRATIVE_REAL_SAVE_AFTER")
    if not before or not after:
        pytest.skip("TINARRATIVE_REAL_SAVE and TINARRATIVE_REAL_SAVE_AFTER are not both set")
    return Path(before), Path(after)


def test_real_save_pair_diffs_deterministically_with_evidence_on_every_change() -> None:
    before_path, after_path = real_save_pair()
    before = normalize(load_raw_save(before_path))
    after = normalize(load_raw_save(after_path))
    first = diff_states(before, after)
    second = diff_states(before, after)
    assert first == second
    assert json.dumps(first.to_dict()) == json.dumps(second.to_dict())
    assert first.changes
    for change in first.changes:
        assert change.evidence.before_location is not None and change.evidence.after_location is not None
        assert change.evidence.before_location.save_id == before.source
        assert change.evidence.after_location.save_id == after.source
        assert (change.field is None) == (change.kind in (ChangeKind.APPEARED, ChangeKind.DISAPPEARED))
        for word in ("destroy", "creat", "purg", "annex"):
            assert word not in change.evidence.description
