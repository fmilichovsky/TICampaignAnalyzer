"""Coverage for the logging conventions in ``tinarrative.log``."""

import logging
from collections.abc import Iterator
from io import StringIO

import pytest

from tinarrative.log import (
    ROOT_LOGGER,
    TIMING_LOGGER,
    configure_logging,
    excerpt,
    fields,
    get_logger,
    logging_state,
    safe_path,
    shape,
)


def test_fields_keep_call_order_and_render_scalars_plainly() -> None:
    assert (
        fields(save="Save.json", count=3, ok=True, missing=None, ratio=0.5)
        == "save=Save.json count=3 ok=true missing=none ratio=0.5"
    )


def test_strings_with_spaces_or_quotes_are_quoted() -> None:
    assert fields(reason="not a list") == "reason='not a list'"
    assert fields(pointer="/gamestates/A.B/0/Value") == "pointer=/gamestates/A.B/0/Value"


def test_safe_path_keeps_only_the_file_name() -> None:
    assert safe_path("/home/someone/saves/Save.json") == "Save.json"
    assert safe_path("Save.json") == "Save.json"


def test_shape_names_json_types_and_sizes_without_content() -> None:
    assert shape(None) == "null"
    assert shape(True) == "boolean"
    assert shape(7) == "number"
    assert shape("Secret Faction") == "string[14]"
    assert shape([1, 2, 3]) == "array[3]"
    assert shape({"a": 1}) == "object{1}"


def test_excerpt_is_bounded_and_marks_the_cut() -> None:
    assert excerpt("short") == "'short'"
    assert excerpt("abcdefghij", limit=4) == "'abcd'...(+6 chars)"


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    yield
    configure_logging("warning", StringIO())


def test_lines_go_to_the_given_stream_in_the_documented_format() -> None:
    stream = StringIO()
    configure_logging("debug", stream)
    get_logger("tinarrative.example").debug("decoded %s", fields(root="object"))
    assert stream.getvalue() == "DEBUG tinarrative.example: decoded root=object\n"


def test_default_level_hides_debug_and_info() -> None:
    stream = StringIO()
    configure_logging("warning", stream)
    logger = get_logger("tinarrative.example")
    logger.debug("hidden")
    logger.info("hidden")
    logger.warning("shown")
    assert stream.getvalue() == "WARNING tinarrative.example: shown\n"


def test_reconfiguring_replaces_the_handler_instead_of_stacking() -> None:
    first, second = (StringIO(), StringIO())
    configure_logging("info", first)
    configure_logging("info", second)
    get_logger("tinarrative.example").info("once")
    root = logging.getLogger(ROOT_LOGGER)
    assert len([h for h in root.handlers if isinstance(h, logging.StreamHandler)]) == 1
    assert first.getvalue() == ""
    assert second.getvalue() == "INFO tinarrative.example: once\n"


def test_the_state_repeats_the_last_configuration() -> None:
    configure_logging("info", StringIO(), timing=True)
    assert logging_state() == ("info", True)
    configure_logging("warning", StringIO())
    assert logging_state() == ("warning", False)


def test_timing_lines_are_off_at_every_level_unless_asked_for() -> None:
    quiet, timed = (StringIO(), StringIO())
    configure_logging("debug", quiet)
    get_logger(TIMING_LOGGER).info("normalize %s", fields(seconds=0.5))
    configure_logging("warning", timed, timing=True)
    get_logger(TIMING_LOGGER).info("normalize %s", fields(seconds=0.5))
    get_logger("tinarrative.example").info("hidden")
    assert quiet.getvalue() == ""
    assert timed.getvalue() == "INFO tinarrative.timing: normalize seconds=0.5\n"


def test_unknown_level_is_rejected() -> None:
    with pytest.raises(ValueError):
        configure_logging("loud", StringIO())
