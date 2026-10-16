"""Current parser-boundary behavior exercised through structured fragments."""

from tinarrative.model.values import Unknown
from tinarrative.parsing.normalization import normalize
from tinarrative.parsing.raw_save import RawSave


def test_normalize_carries_source_and_version_from_the_raw_save() -> None:
    root: dict[str, object] = {"currentID": {"value": 1}, "gamestates": {}}
    raw = RawSave(source="fixture.json", format="terra_invicta_json_v1", game_version="x", root=root, size_bytes=2)
    snapshot = normalize(raw)
    assert (snapshot.source, snapshot.game_version, snapshot.date) == ("fixture.json", "x", Unknown())
