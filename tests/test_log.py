"""Coverage for the logging conventions in ``tinarrative.log``."""

import logging
import unittest
from io import StringIO

from tinarrative.log import ROOT_LOGGER, configure_logging, excerpt, fields, get_logger, safe_path, shape


class FieldRenderingTests(unittest.TestCase):
    def test_fields_keep_call_order_and_render_scalars_plainly(self) -> None:
        self.assertEqual(
            fields(save="Save.json", count=3, ok=True, missing=None, ratio=0.5),
            "save=Save.json count=3 ok=true missing=none ratio=0.5",
        )

    def test_strings_with_spaces_or_quotes_are_quoted(self) -> None:
        self.assertEqual(fields(reason="not a list"), "reason='not a list'")
        self.assertEqual(fields(pointer="/gamestates/A.B/0/Value"), "pointer=/gamestates/A.B/0/Value")

    def test_safe_path_keeps_only_the_file_name(self) -> None:
        self.assertEqual(safe_path("/home/someone/saves/Save.json"), "Save.json")
        self.assertEqual(safe_path("Save.json"), "Save.json")

    def test_shape_names_json_types_and_sizes_without_content(self) -> None:
        self.assertEqual(shape(None), "null")
        self.assertEqual(shape(True), "boolean")
        self.assertEqual(shape(7), "number")
        self.assertEqual(shape("Secret Faction"), "string[14]")
        self.assertEqual(shape([1, 2, 3]), "array[3]")
        self.assertEqual(shape({"a": 1}), "object{1}")

    def test_excerpt_is_bounded_and_marks_the_cut(self) -> None:
        self.assertEqual(excerpt("short"), "'short'")
        self.assertEqual(excerpt("abcdefghij", limit=4), "'abcd'...(+6 chars)")


class ConfigureLoggingTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_logging("warning", StringIO())

    def test_lines_go_to_the_given_stream_in_the_documented_format(self) -> None:
        stream = StringIO()
        configure_logging("debug", stream)
        get_logger("tinarrative.example").debug("decoded %s", fields(root="object"))
        self.assertEqual(stream.getvalue(), "DEBUG tinarrative.example: decoded root=object\n")

    def test_default_level_hides_debug_and_info(self) -> None:
        stream = StringIO()
        configure_logging("warning", stream)
        logger = get_logger("tinarrative.example")
        logger.debug("hidden")
        logger.info("hidden")
        logger.warning("shown")
        self.assertEqual(stream.getvalue(), "WARNING tinarrative.example: shown\n")

    def test_reconfiguring_replaces_the_handler_instead_of_stacking(self) -> None:
        first, second = StringIO(), StringIO()
        configure_logging("info", first)
        configure_logging("info", second)
        get_logger("tinarrative.example").info("once")
        root = logging.getLogger(ROOT_LOGGER)
        self.assertEqual(len([h for h in root.handlers if isinstance(h, logging.StreamHandler)]), 1)
        self.assertEqual(first.getvalue(), "")
        self.assertEqual(second.getvalue(), "INFO tinarrative.example: once\n")

    def test_unknown_level_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            configure_logging("loud", StringIO())


if __name__ == "__main__":
    unittest.main()
