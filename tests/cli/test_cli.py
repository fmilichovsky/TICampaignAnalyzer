"""Coverage for the CLI skeleton that has no more specific fixture of its own."""

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import tinarrative
from tests.fixtures import fixture_path
from tinarrative.cli import EXIT_INPUT_ERROR, EXIT_NOT_IMPLEMENTED, EXIT_SUCCESS, EXIT_UNSUPPORTED_INPUT, main


class CliSkeletonTests(unittest.TestCase):
    def test_version_flag_reports_the_package_version(self) -> None:
        with redirect_stdout(StringIO()) as out, self.assertRaises(SystemExit) as result:
            main(["--version"])
        self.assertEqual(result.exception.code, EXIT_SUCCESS)
        self.assertEqual(out.getvalue().strip(), f"tinarrative {tinarrative.__version__}")

    def test_cli_runs_without_arguments(self) -> None:
        self.assertEqual(main([]), EXIT_SUCCESS)

    def test_placeholder_commands_have_stable_exit_codes(self) -> None:
        with redirect_stderr(StringIO()):
            self.assertEqual(main(["diff"]), EXIT_NOT_IMPLEMENTED)

    def test_subcommand_help_does_not_need_a_save_file(self) -> None:
        for command in ("inspect", "parse", "diff"):
            with self.subTest(command=command), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main([command, "--help"])
            self.assertEqual(result.exception.code, EXIT_SUCCESS)


if __name__ == "__main__":
    unittest.main()


class ParseCommandTests(unittest.TestCase):
    def run_parse(self, path: Path) -> tuple[int, str, str]:
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["parse", str(path)])
        return code, out.getvalue(), err.getvalue()

    def test_supported_fixture_succeeds(self) -> None:
        code, out, err = self.run_parse(fixture_path("io", "terra_invicta_json_v1", "representative_campaign.json"))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("format: terra_invicta_json_v1", out)
        self.assertIn("game version: not serialized", out)
        self.assertEqual(err, "")

    def test_missing_path_is_an_input_error(self) -> None:
        code, _, err = self.run_parse(Path("does-not-exist.json"))
        self.assertEqual(code, EXIT_INPUT_ERROR)
        self.assertIn("cannot read", err)

    def test_bad_content_is_an_unsupported_input_without_traceback(self) -> None:
        cases = {
            "malformed_truncated.json": "not valid JSON",
            "missing_gamestates.json": "'gamestates'",
            "explicit_game_version_envelope.json": "Unsupported Terra Invicta game version",
        }
        for name, message in cases.items():
            with self.subTest(name=name):
                code, out, err = self.run_parse(fixture_path("io", "terra_invicta_json_v1", name))
                self.assertEqual(code, EXIT_UNSUPPORTED_INPUT)
                self.assertEqual(out, "")
                self.assertIn(message, err)
                self.assertNotIn("Traceback", err)
