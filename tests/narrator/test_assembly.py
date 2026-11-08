"""Coverage for tinarrative.narrator.assembly: footnote renumbering, the citation audit, the header and the manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from tinarrative.narrator.assembly import (
    StoredChapter,
    assemble,
    citable,
    citations,
    parse_plan,
    split_footnotes,
    stored_chapter,
)
from tinarrative.narrator.request import build_request, render_request

GENERATED = datetime(2026, 10, 22, 9, 30, 15, tzinfo=UTC)
PLAN: dict[str, Any] = {
    "prompt_version": "prompt-hash",
    "package_sha256": "package-hash",
    "settings": {
        "max_input_tokens": 9000,
        "chars_per_token": 3,
        "quarter_span_days": 730,
        "half_span_days": 1825,
        "recalled_narrative_events": 40,
        "top_economies": 10,
    },
    "request": {"period": "half"},
    "chapters": [],
}


def _package(
    saves: Sequence[str],
    narrative: Sequence[tuple[str, str]] = (),
    *,
    events: Sequence[str] = (),
    continuing: Sequence[str] = (),
    earlier: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "campaign": {"index": 1, "key": "fixture-campaign"},
        "saves": [{"key": key, "date": key} for key in saves],
        "intervals": [
            {"key": saves[-1], "not_before": saves[0], "date": saves[-1], "events": [{"id": i} for i in events]}
        ],
        "narrative": [{"id": identifier, "significance": level} for identifier, level in narrative],
        "glossary": [{"ref": "nation:1", "name": "Freedonia"}],
        "continuity": {
            "continuing": [{"id": identifier, "significance": "major"} for identifier in continuing],
            "earlier": [{"id": identifier} for identifier in earlier],
            "earlier_omitted": 0,
        },
    }


def _chapter(
    index: int,
    package: dict[str, Any],
    text: str,
    *,
    model: str = "some-model",
    reported: str | None = "some-model-2026",
    input_tokens: int | None = 1000,
) -> StoredChapter:
    request = render_request(build_request(package, {"chapter": f"{index} of 2"})).encode("utf-8")
    sha = hashlib.sha256(request).hexdigest()
    saves = package["saves"]
    entry = {
        "index": index,
        "part": "first" if index == 1 else "last",
        "covers": {"from": saves[0]["key"], "to": saves[-1]["key"]},
        "periods": ["2030-H1"],
        "period": "half",
        "period_basis": "campaign_span",
        "estimate": 500,
        "reduction": None,
        "request_sha256": sha,
    }
    response = {
        "index": index,
        "request_sha256": sha,
        "provider": "anthropic",
        "model": model,
        "max_output_tokens": 16000,
        "temperature": None,
        "reported_model": reported,
        "finish": "complete",
        "estimate": 500,
        "input_tokens": input_tokens,
        "output_tokens": 200,
        "text": text,
    }
    return stored_chapter(entry, request, json.dumps(response).encode("utf-8"))


FIRST = _package(
    ["2030-01-01T00:00:00", "2030-07-01T00:00:00"],
    [("dev.a", "major"), ("dev.b", "campaign_defining"), ("dev.minor", "minor")],
    events=["atomic.x"],
)
SECOND = _package(
    ["2030-07-01T00:00:00", "2031-01-01T00:00:00"],
    [("dev.c", "major"), ("dev.uncited", "major")],
    continuing=["dev.b"],
    earlier=["dev.a"],
)


def test_footnotes_are_renumbered_in_sequence_with_definitions_at_the_end() -> None:
    first = _chapter(
        1,
        FIRST,
        "## 2030-H1\n\nA rose.[^1] B followed.[^2][^3] A again.[^1]\n\n---\n\n### Footnotes\n\n"
        "[^1]: `dev.a`\n[^2]: `dev.b`  \n[^3]: atomic.x\n",
    )
    second = _chapter(
        2,
        SECOND,
        "## 2030-H2\n\nC happened.[^1]\n\n[^1]: `dev.c`; `dev.b`\n\n***\n\n"
        "**Where things stood**\n\nStill open.[^2]\n\n[^2]: `situation 2031-01-01T00:00:00`\n",
    )

    history = assemble([first, second], PLAN, generated=GENERATED, version="0.1.0").history

    body, _, notes = history.partition("\n\n[^1]: ")
    assert "A rose.[^1] B followed.[^2][^3] A again.[^1]\n\n## 2030-H2\n\nC happened.[^4]" in body
    assert "***\n\n**Where things stood**\n\nStill open.[^5]" in body
    assert "Footnotes" not in history and "---" not in history
    assert ("[^1]: " + notes).splitlines() == [
        "[^1]: `dev.a`",
        "[^2]: `dev.b`",
        "[^3]: atomic.x",
        "[^4]: `dev.c`; `dev.b`",
        "[^5]: `situation 2031-01-01T00:00:00`",
    ]


def test_unreferenced_definitions_follow_and_undefined_references_take_their_label() -> None:
    chapter = _chapter(
        1,
        FIRST,
        "B.[^situation 2030-07-01T00:00:00] Then [^9].\n\n[^1]: `dev.a`\n[^2]: `dev.b`\n",
    )

    assembly = assemble([chapter], PLAN, generated=GENERATED, version="0.1.0")

    assert "B.[^1] Then [^2]." in assembly.history
    assert assembly.history.endswith("[^1]: situation 2030-07-01T00:00:00\n[^2]: 9\n[^3]: `dev.a`\n[^4]: `dev.b`\n")
    audit = assembly.manifest["audit"]
    assert audit["undefined"] == [
        {"chapter": 1, "footnote": 1, "label": "situation 2030-07-01T00:00:00"},
        {"chapter": 1, "footnote": 2, "label": "9"},
    ]
    assert audit["unreferenced"] == [
        {"chapter": 1, "footnote": 3, "label": "1"},
        {"chapter": 1, "footnote": 4, "label": "2"},
    ]
    assert audit["unmatched"] == []
    assert assembly.findings == {"undefined": 2, "unreferenced": 2}


def test_split_footnotes_keeps_continuation_lines_and_mid_text_definitions() -> None:
    text = split_footnotes("One.[^a]\n\n[^a]: `x`;\n    `y`\n\n\n\nTwo.[^b]\n\nNotes:\n\n[^b]: `z`\n\n")

    assert text.body == "One.[^a]\n\nTwo.[^b]"
    assert text.references == ("a", "b")
    assert text.definitions == {"a": "`x`; `y`", "b": "`z`"}


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        ("`a@1`; `b@2`", ["a@1", "b@2"]),
        ("See `a@1` and `situation  2030-01-01T00:00:00`.", ["a@1", "situation 2030-01-01T00:00:00"]),
        ("a@1; b@2.", ["a@1", "b@2"]),
        ("a@1, b@2", ["a@1", "b@2"]),
        ("situation 2030-01-01T00:00:00", ["situation 2030-01-01T00:00:00"]),
        ("", []),
    ],
)
def test_citations_are_the_backticked_spans_else_the_listed_parts(definition: str, expected: list[str]) -> None:
    assert citations(definition) == expected


def test_citable_ids_are_the_chapter_package_entries_and_its_situations() -> None:
    assert citable(SECOND) == {
        "dev.c",
        "dev.uncited",
        "dev.b",
        "dev.a",
        "situation 2030-07-01T00:00:00",
        "situation 2031-01-01T00:00:00",
    }


def test_the_audit_checks_each_citation_against_its_own_chapter_package() -> None:
    first = _chapter(
        1,
        FIRST,
        "A.[^1] B.[^2]\n\n[^1]: `dev.a`; `atomic.x`; `nation:1`\n[^2]: `dev.c`; `situation 2030-07-01T00:00:00`\n",
    )
    second = _chapter(
        2,
        SECOND,
        "C.[^1] B again.[^2]\n\n[^1]: `dev.c`; `dev.a@2030-01-01`\n[^2]: `dev.b`; `situation 2030-01-01T00:00:00`\n",
    )

    assembly = assemble([first, second], PLAN, generated=GENERATED, version="0.1.0")

    audit = assembly.manifest["audit"]
    assert audit["unmatched"] == [
        {"chapter": 1, "footnote": 1, "id": "nation:1"},
        {"chapter": 1, "footnote": 2, "id": "dev.c"},
        {"chapter": 2, "footnote": 3, "id": "dev.a@2030-01-01"},
        {"chapter": 2, "footnote": 4, "id": "situation 2030-01-01T00:00:00"},
    ]
    # dev.b is cited only by the later chapter, through continuity; dev.minor is below major.
    assert audit["uncited"] == [{"chapter": 2, "id": "dev.uncited", "significance": "major"}]
    assert (audit["footnotes"], audit["cited_ids"]) == (4, 9)
    assert assembly.findings == {"unmatched": 4, "uncited": 1}


def test_a_wave_member_is_citable_but_never_reported_uncited() -> None:
    package = _package(["2030-01-01T00:00:00", "2030-07-01T00:00:00"], [("dev.wave", "major")])
    package["narrative"].append({"id": "dev.member", "significance": "major", "member_of": "dev.wave"})

    assembly = assemble(
        [_chapter(1, package, "A wave.[^1]\n\n[^1]: `dev.wave`; `dev.member`\n")],
        PLAN,
        generated=GENERATED,
        version="0.1.0",
    )

    assert "dev.member" in citable(package)
    assert assembly.manifest["audit"]["unmatched"] == [] and assembly.manifest["audit"]["uncited"] == []


def test_without_footnotes_no_narrative_event_is_reported_uncited() -> None:
    plan = {**PLAN, "request": {"period": "half", "citations": "none"}}

    assembly = assemble([_chapter(1, FIRST, "Prose only.\n")], plan, generated=GENERATED, version="0.1.0")

    assert assembly.manifest["audit"]["citations"] == "none"
    assert assembly.manifest["audit"]["uncited"] is None
    assert assembly.findings == {}
    assert assembly.history.endswith("\n\nProse only.\n")


def test_the_header_names_provider_model_prompt_campaign_period_and_time() -> None:
    chapters = [
        _chapter(1, FIRST, "One.\n", reported="reported-a"),
        _chapter(2, SECOND, "Two.\n", reported=None),
    ]

    history = assemble(chapters, PLAN, generated=GENERATED, version="0.1.0").history

    assert history == (
        "# Campaign history\n\n"
        "- Provider: anthropic\n"
        "- Model: reported-a, not reported (requested some-model)\n"
        "- Prompt version: prompt-hash\n"
        "- Campaign: fixture-campaign\n"
        "- Period: 2030-01-01 to 2031-01-01\n"
        "- Generated: 2026-10-22T09:30:15Z\n\n"
        "One.\n\nTwo.\n"
    )


def test_the_manifest_records_the_run_and_the_token_calibration() -> None:
    chapters = [
        _chapter(1, FIRST, "One.\n", input_tokens=1000),
        _chapter(2, SECOND, "Two.\n", model="other-model", input_tokens=None),
    ]

    manifest = assemble(chapters, PLAN, generated=GENERATED, version="0.1.0").manifest

    assert manifest["program"] == {"name": "tinarrative", "version": "0.1.0"}
    assert manifest["generated"] == "2026-10-22T09:30:15Z"
    assert (manifest["prompt_version"], manifest["package_sha256"]) == ("prompt-hash", "package-hash")
    assert manifest["campaign"] == "fixture-campaign"
    assert manifest["covers"] == {"from": "2030-01-01T00:00:00", "to": "2031-01-01T00:00:00"}
    assert manifest["settings"] == {
        "max_input_tokens": PLAN["settings"]["max_input_tokens"],
        "chars_per_token": PLAN["settings"]["chars_per_token"],
        "provider": "anthropic",
        "model": ["some-model", "other-model"],
        "max_output_tokens": 16000,
        "temperature": None,
    }
    assert manifest["request"] == {"period": "half"}
    first, second = manifest["chapters"]
    assert first["request_sha256"] == chapters[0].entry["request_sha256"]
    assert first["request_characters"] == chapters[0].characters
    assert (first["period"], first["period_basis"]) == ("half", "campaign_span")
    assert (first["finish"], first["reported_model"], first["output_tokens"]) == ("complete", "some-model-2026", 200)
    assert manifest["tokens"] == {
        "estimate": 1000,
        "request_characters": chapters[0].characters + chapters[1].characters,
        "input_tokens": 1000,
        "output_tokens": 400,
        "characters_per_input_token": round(chapters[0].characters / 1000, 3),
    }


def _files(package: dict[str, Any]) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    request = render_request(build_request(package, {})).encode("utf-8")
    sha = hashlib.sha256(request).hexdigest()
    entry = {"index": 2, "request_sha256": sha, "covers": {"from": "a", "to": "b"}}
    return entry, request, {"request_sha256": sha, "text": "Prose."}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("no request", "chapter 2: no request file"),
        ("edited request", "chapter 2: the request file does not match plan.json"),
        ("no response", "chapter 2: no response; send it with --send"),
        ("other request", "chapter 2: the response was made from another request"),
        ("no text", "chapter 2: the response file is not a response"),
    ],
)
def test_a_chapter_file_that_is_missing_or_does_not_match_is_named(change: str, message: str) -> None:
    entry, request, response = _files(FIRST)
    request_bytes: bytes | None = request
    response_bytes: bytes | None = json.dumps(response).encode("utf-8")
    if change == "no request":
        request_bytes = None
    elif change == "edited request":
        request_bytes = request + b" "
    elif change == "no response":
        response_bytes = None
    elif change == "other request":
        response_bytes = json.dumps({**response, "request_sha256": "0" * 64}).encode("utf-8")
    else:
        response_bytes = json.dumps({"request_sha256": response["request_sha256"]}).encode("utf-8")

    with pytest.raises(ValueError, match=message):
        stored_chapter(entry, request_bytes, response_bytes)


@pytest.mark.parametrize("text", [b"not json", b"[]", b'{"chapters": []}', b'{"chapters": [{"index": 1}]}'])
def test_a_file_that_is_not_a_plan_is_rejected(text: bytes) -> None:
    with pytest.raises(ValueError, match="not a chapter plan"):
        parse_plan(text)
