"""Pure-function coverage for the semantics-free save inspector."""

import json

import pytest

from tinarrative.inspection import (
    RenderLimits,
    decode_save,
    inspect_bytes,
    render_json,
    render_text,
    resolve_pointer,
    truncate_value,
    type_label,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({}, "object"),
        ([], "array"),
        ("x", "string"),
        (1, "number"),
        (1.5, "number"),
        (True, "boolean"),
        (None, "null"),
    ],
)
def test_type_label_uses_json_vocabulary(value: object, expected: str) -> None:
    assert type_label(value) == expected


DOCUMENT = {"a": {"b": [10, 20, {"c": "deep"}]}, "": "empty-key", "k/y~z": 1}


@pytest.mark.parametrize(
    ("pointer", "expected"),
    [
        ("", DOCUMENT),
        ("/a", DOCUMENT["a"]),
        ("/a/b/1", 20),
        ("/a/b/2/c", "deep"),
        ("/", "empty-key"),
        ("/k~1y~0z", 1),
    ],
)
def test_resolve_pointer_follows_rfc_6901(pointer: str, expected: object) -> None:
    lookup = resolve_pointer(DOCUMENT, pointer)

    assert lookup.found is True
    assert lookup.value == expected


@pytest.mark.parametrize(
    ("pointer", "code", "reason_fragment"),
    [
        ("/nope", "pointer_not_found", "missing key 'nope' at root"),
        ("/a/b/3", "pointer_not_found", "out of range (array length 3) at /a/b"),
        ("/a/b/-", "pointer_not_found", "'-' is not a decimal array index"),
        ("/a/b/01", "pointer_not_found", "'01' is not a decimal array index"),
        ("/a/b/0/x", "pointer_not_found", "cannot descend into number at /a/b/0"),
        ("a/b", "pointer_syntax", "must be empty or start with '/'"),
    ],
)
def test_resolve_pointer_explains_each_failure(pointer: str, code: str, reason_fragment: str) -> None:
    lookup = resolve_pointer(DOCUMENT, pointer)

    assert lookup.found is False
    assert lookup.code == code
    assert lookup.reason is not None
    assert reason_fragment in lookup.reason


def test_truncate_value_marks_hidden_items_keys_and_chars() -> None:
    limits = RenderLimits(max_items=10, max_string=8, max_depth=3)

    assert truncate_value(list(range(15)), limits) == [*range(10), "...(+5 items)"]
    truncated_object = truncate_value({f"k{i}": i for i in range(12)}, limits)
    assert list(truncated_object)[-1] == "..."
    assert truncated_object["..."] == "(+2 keys)"
    assert len(truncated_object) == 11
    assert truncate_value("x" * 100, limits) == "xxxxxxxx...(+92 chars)"
    assert truncate_value("short", limits) == "short"


def test_truncate_value_stops_at_max_depth_but_keeps_empty_containers() -> None:
    nested = {"l1": {"l2": {"l3": {"l4": 1}, "empty": {}, "list": [[]]}}}

    assert truncate_value(nested, RenderLimits(max_depth=3)) == {
        "l1": {"l2": {"l3": "{...}", "empty": {}, "list": "[...]"}}
    }
    assert truncate_value(nested, RenderLimits(max_depth=0)) == "{...}"
    assert truncate_value([1, 2], RenderLimits(max_items=0)) == ["...(+2 items)"]


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "empty_file"),
        (b"\x1f\x8b\x08\x00rest", "gzip_magic"),
        (b"PK\x03\x04rest", "zip_magic"),
        (b"\xff\xfe{\x00}\x00", "utf16_bom"),
        (b"\xff{}", "invalid_utf8"),
        (b"[1,", "json_decode_error"),
        (b"   ", "json_decode_error"),
    ],
)
def test_decode_save_reports_each_unsupported_input(data: bytes, code: str) -> None:
    result = decode_save(data)

    assert result.ok is False
    assert result.value is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [code]


def test_decode_save_skips_a_utf8_bom_but_records_it() -> None:
    result = decode_save(b"\xef\xbb\xbf{}")

    assert result.ok is True
    assert result.value == {}
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["utf8_bom"]


def test_decode_save_locates_json_syntax_errors() -> None:
    result = decode_save(b'{"a": 1,\n "b": }')

    (diagnostic,) = result.diagnostics
    assert diagnostic.code == "json_decode_error"
    assert "line 2 column 7 (char 15)" in diagnostic.message
    assert diagnostic.detail == 'context: \'{"a": 1,\\n "b": }\''


def test_inspect_bytes_describes_a_non_object_root_without_failing() -> None:
    report = inspect_bytes(b"[1, 2]", "root.json", pointers=("/0", "/2"))

    assert report.status == "path_not_found"
    assert report.root_type == "array"
    assert report.top_level == ()
    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "root_not_object",
        "pointer_not_found",
    ]
    assert report.paths[0].found is True
    assert report.paths[0].value == 1
    text = render_text(report)
    assert "top-level keys: n/a (root is array)" in text


def test_inspect_bytes_reports_missing_envelope_keys_as_findings() -> None:
    report = inspect_bytes(b'{"date": "2030-01-01"}', "fragment.json")

    assert report.status == "ok"
    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "missing_key",
        "missing_key",
    ]


def test_inspect_bytes_does_not_evaluate_paths_when_decoding_fails() -> None:
    report = inspect_bytes(b"[1,", "broken.json", pointers=("/0",))

    assert report.status == "unsupported_input"
    assert report.paths[0].reason == "not evaluated"
    assert "/0: not evaluated (input could not be decoded)" in render_text(report)


def test_rendering_is_deterministic_and_ascii_only() -> None:
    data = json.dumps({"gamestates": {"état": ["ünïcode"]}, "currentID": 1}).encode()

    first = inspect_bytes(data, "save.json", pointers=("/gamestates",))
    second = inspect_bytes(data, "save.json", pointers=("/gamestates",))

    assert render_text(first) == render_text(second)
    assert render_json(first) == render_json(second)
    assert render_text(first).isascii()
    assert render_json(first).isascii()
    assert json.loads(render_json(first))["paths"][0]["value"] == {"état": ["ünïcode"]}
