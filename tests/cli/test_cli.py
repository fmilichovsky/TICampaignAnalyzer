"""Coverage for the CLI skeleton that has no more specific fixture of its own."""

import json
import os
import re
import tempfile
import unittest
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import tinarrative
from tests.fixtures import fixture_path
from tinarrative.cli import (
    EXIT_INPUT_ERROR,
    EXIT_PATH_NOT_FOUND,
    EXIT_REGISTRY_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED_INPUT,
    EXIT_USAGE_ERROR,
    main,
)
from tinarrative.log import ENV_VAR
from tinarrative.maintenance import REGISTRY_ENV_VAR

REPRESENTATIVE = ("io", "terra_invicta_json_v1", "representative_campaign.json")


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def listed_commands(help_text: str) -> list[str]:
    """Command names of the ``COMMAND`` section of an argparse help text, in listed order."""
    section = help_text.split("  COMMAND\n", 1)[1]
    return re.findall(r"^    (\S+)", section, flags=re.MULTILINE)


class CliSkeletonTests(unittest.TestCase):
    def test_version_flag_reports_the_package_version(self) -> None:
        with redirect_stdout(StringIO()) as out, self.assertRaises(SystemExit) as result:
            main(["--version"])
        self.assertEqual(result.exception.code, EXIT_SUCCESS)
        self.assertEqual(out.getvalue().strip(), f"tinarrative {tinarrative.__version__}")

    def test_cli_runs_without_arguments(self) -> None:
        self.assertEqual(main([]), EXIT_SUCCESS)

    def test_subcommand_help_does_not_need_a_save_file(self) -> None:
        for command in (
            ["save", "inspect"],
            ["save", "parse"],
            ["save", "diff"],
            ["unknowns"],
            ["events"],
            ["campaigns"],
        ):
            with self.subTest(command=command), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main([*command, "--help"])
            self.assertEqual(result.exception.code, EXIT_SUCCESS)

    def test_top_level_lists_campaigns_events_save_and_unknowns(self) -> None:
        with redirect_stdout(StringIO()) as out, self.assertRaises(SystemExit):
            main(["--help"])
        self.assertEqual(listed_commands(out.getvalue()), ["campaigns", "events", "save", "unknowns"])

    def test_save_group_lists_inspect_parse_and_diff(self) -> None:
        with redirect_stdout(StringIO()) as out, self.assertRaises(SystemExit):
            main(["save", "--help"])
        self.assertEqual(listed_commands(out.getvalue()), ["inspect", "parse", "diff"])

    def test_save_without_a_command_is_a_usage_error(self) -> None:
        with redirect_stderr(StringIO()) as err, self.assertRaises(SystemExit) as result:
            main(["save"])
        self.assertEqual(result.exception.code, EXIT_USAGE_ERROR)
        self.assertIn("COMMAND", err.getvalue())

    def test_per_save_commands_are_not_top_level(self) -> None:
        save = str(fixture_path(*REPRESENTATIVE))
        for command in ("inspect", "parse", "diff"):
            with self.subTest(command=command), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main([command, save, save])
            self.assertEqual(result.exception.code, EXIT_USAGE_ERROR)


class ParseCommandTests(unittest.TestCase):
    def run_parse(self, path: Path) -> tuple[int, str, str]:
        return run_cli(["save", "parse", str(path)])

    def test_supported_fixture_succeeds(self) -> None:
        code, out, err = self.run_parse(fixture_path("io", "terra_invicta_json_v1", "representative_campaign.json"))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("format: terra_invicta_json_v1", out)
        self.assertIn("game version: not serialized", out)
        self.assertEqual(err, "")

    def test_summary_ends_with_the_unknown_structure_count(self) -> None:
        code, out, err = self.run_parse(fixture_path("io", "terra_invicta_json_v1", "campaign_assets.json"))
        self.assertEqual((code, err), (EXIT_SUCCESS, ""))
        self.assertEqual(out.splitlines()[-1], "unknown structures: 0")
        code, out, _ = self.run_parse(fixture_path("io", "terra_invicta_json_v1", "political_control.json"))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertEqual(out.splitlines()[-1], "unknown structures: 2")

    def test_summary_counts_known_record_sets_and_their_entries(self) -> None:
        code, out, err = self.run_parse(fixture_path("io", "terra_invicta_json_v1", "records_before.json"))
        self.assertEqual((code, err), (EXIT_SUCCESS, ""))
        self.assertEqual(out.splitlines()[-2:], ["records: 19 fields, 28 entries", "unknown structures: 0"])
        code, out, _ = self.run_parse(fixture_path("io", "terra_invicta_json_v1", "campaign_assets.json"))
        self.assertIn("records: 0 fields, 0 entries", out.splitlines())

    def test_record_unknowns_needs_a_registry_and_writes_one(self) -> None:
        save = fixture_path("io", "terra_invicta_json_v1", "political_control.json")
        with mock.patch.dict(os.environ):
            os.environ.pop(REGISTRY_ENV_VAR, None)
            code, out, err = run_cli(["save", "parse", str(save), "--record-unknowns"])
            self.assertEqual(code, EXIT_USAGE_ERROR)
            self.assertIn("unknown structures: 2", out)
            self.assertIn(f"--record-unknowns needs --registry PATH or {REGISTRY_ENV_VAR}", err)
            with tempfile.TemporaryDirectory() as directory:
                registry = Path(directory) / "registry.json"
                code, out, err = run_cli(["save", "parse", str(save), "--record-unknowns", "--registry", str(registry)])
                self.assertEqual((code, err), (EXIT_SUCCESS, ""))
                self.assertEqual(out.splitlines()[-1], f"registry: {registry}: 2 added, 0 updated, 0 pruned, 2 total")
                self.assertTrue(registry.exists())
                os.environ[REGISTRY_ENV_VAR] = str(registry)
                code, out, err = run_cli(["save", "parse", str(save), "--record-unknowns"])
                self.assertEqual((code, err), (EXIT_SUCCESS, ""))
                self.assertIn("2 updated", out.splitlines()[-1])
                code, out, err = run_cli(
                    ["save", "parse", str(save), "--registry", str(registry)]
                )  # flag alone: no write
                self.assertEqual((code, err), (EXIT_SUCCESS, ""))
                self.assertNotIn("registry:", out)
                code, out, err = run_cli(["save", "parse", str(save), "--record-unknowns", "--registry", directory])
                self.assertEqual(code, EXIT_REGISTRY_ERROR)
                self.assertIn("unknown structures: 2", out)
                self.assertIn("cannot update registry", err)
                self.assertNotIn("Traceback", err)

    def test_missing_path_is_an_input_error(self) -> None:
        code, _, err = self.run_parse(Path("does-not-exist.json"))
        self.assertEqual(code, EXIT_INPUT_ERROR)
        self.assertIn("cannot read", err)

    def test_bad_content_is_an_unsupported_input_without_traceback(self) -> None:
        cases = {
            "malformed_truncated.json": "not valid JSON",
            "missing_gamestates.json": "'gamestates'",
        }
        for name, message in cases.items():
            with self.subTest(name=name):
                code, out, err = self.run_parse(fixture_path("io", "terra_invicta_json_v1", name))
                self.assertEqual(code, EXIT_UNSUPPORTED_INPUT)
                self.assertEqual(out, "")
                self.assertIn(message, err)
                self.assertNotIn("Traceback", err)

    def test_shape_error_during_normalization_is_reported_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad_container.json"
            root = {
                "currentID": {"value": 1},
                "gamestates": {"PavonisInteractive.TerraInvicta.TIFactionState": 5},
            }
            path.write_text(json.dumps(root), encoding="utf-8")
            code, out, err = self.run_parse(path)
        self.assertEqual(code, EXIT_UNSUPPORTED_INPUT)
        self.assertEqual(out, "")
        self.assertEqual(err.count("\n"), 1)
        self.assertIn("TIFactionState: expected a pair array", err)
        self.assertNotIn("Traceback", err)


class LogLevelTests(unittest.TestCase):
    """Diagnostic logging is silent by default and opt-in through the flag or the environment."""

    def setUp(self) -> None:
        self.save = fixture_path(*REPRESENTATIVE)
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(ENV_VAR, None)

    def test_default_run_writes_nothing_to_stderr(self) -> None:
        save = str(self.save)
        for argv in (["save", "parse", save], ["save", "inspect", save], ["save", "diff", save, save]):
            with self.subTest(argv=argv[0]):
                code, _, err = run_cli(argv)
                self.assertEqual(code, EXIT_SUCCESS)
                self.assertEqual(err, "")

    def test_debug_flag_explains_parse_decisions_on_stderr_only(self) -> None:
        code, out, err = run_cli(["--log-level", "debug", "save", "parse", str(self.save)])
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertNotIn("DEBUG", out)
        lines = err.splitlines()
        self.assertEqual(lines[0], f"INFO tinarrative.cli: save parse start save={self.save.name}")
        self.assertIn("DEBUG tinarrative.parsing.raw_save: json decoded root=dict", lines)
        self.assertIn("DEBUG tinarrative.parsing.game_version: game_version detected source=none", lines)
        self.assertTrue(
            any(line.startswith("DEBUG tinarrative.parsing.normalization: domain normalized") for line in lines)
        )
        self.assertTrue(lines[-1].startswith("INFO tinarrative.cli: save parse done save="))
        self.assertIn("unknowns=3 exit=0", lines[-1])
        self.assertIn(
            "INFO tinarrative.parsing.unknowns: unknown structures total=3 state_types=0 fields=3 envelope_keys=0 "
            "field_shapes=0 reference_domains=0 singletons=0 containers=0",
            lines,
        )

    def test_info_level_summarizes_without_debug_lines(self) -> None:
        code, _, err = run_cli(["--log-level", "info", "save", "parse", str(self.save)])
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertNotIn("DEBUG", err)
        self.assertIn("INFO tinarrative.parsing.normalization: normalized", err)

    def test_log_lines_name_the_file_but_never_its_directory(self) -> None:
        _, _, err = run_cli(["--log-level", "debug", "save", "parse", str(self.save)])
        self.assertIn(f"save={self.save.name}", err)
        self.assertNotIn(str(self.save.parent), err)

    def test_debug_inspect_reports_pointer_resolution(self) -> None:
        code, out, err = run_cli(
            ["--log-level", "debug", "save", "inspect", str(self.save), "-p", "/currentID", "-p", "/nope"]
        )
        self.assertEqual(code, EXIT_PATH_NOT_FOUND)
        self.assertIn("tinarrative save inspect report", out)
        self.assertIn("DEBUG tinarrative.inspection.decode: json decoded root=dict", err)
        self.assertIn("DEBUG tinarrative.inspection.analysis: pointer resolved pointer=/currentID type=object", err)
        self.assertIn("pointer unresolved pointer=/nope code=pointer_not_found", err)
        self.assertIn(
            "INFO tinarrative.cli: save inspect done save=representative_campaign.json status=path_not_found exit=6",
            err,
        )

    def test_debug_logs_a_rejected_save_with_the_error_class(self) -> None:
        bad = fixture_path("io", "terra_invicta_json_v1", "malformed_truncated.json")
        code, _, err = run_cli(["--log-level", "debug", "save", "parse", str(bad)])
        self.assertEqual(code, EXIT_UNSUPPORTED_INPUT)
        self.assertIn("decode rejected code=json_decode_error line=", err)
        self.assertIn("parse failed save=malformed_truncated.json error=MalformedSaveError", err)
        self.assertIn("Traceback", err)  # only at debug level, after the structured line

    def test_environment_variable_enables_logging_and_the_flag_wins(self) -> None:
        os.environ[ENV_VAR] = "debug"
        _, _, err = run_cli(["save", "parse", str(self.save)])
        self.assertIn("DEBUG tinarrative.parsing.raw_save", err)
        _, _, err = run_cli(["--log-level", "error", "save", "parse", str(self.save)])
        self.assertEqual(err, "")

    def test_invalid_environment_value_is_a_usage_error(self) -> None:
        os.environ[ENV_VAR] = "loud"
        with redirect_stderr(StringIO()) as err, self.assertRaises(SystemExit) as result:
            main(["save", "parse", str(self.save)])
        self.assertEqual(result.exception.code, EXIT_USAGE_ERROR)
        self.assertIn(f"{ENV_VAR}='loud' is not one of", err.getvalue())

    def test_invalid_flag_value_is_a_usage_error(self) -> None:
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as result:
            main(["--log-level", "loud", "save", "parse", str(self.save)])
        self.assertEqual(result.exception.code, EXIT_USAGE_ERROR)


if __name__ == "__main__":
    unittest.main()
