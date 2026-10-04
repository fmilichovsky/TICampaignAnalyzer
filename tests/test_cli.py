"""Coverage for the CLI skeleton that has no more specific fixture of its own."""

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

import tinarrative
from tinarrative.cli import EXIT_NOT_IMPLEMENTED, EXIT_SUCCESS, main


class CliSkeletonTests(unittest.TestCase):
    def test_version_flag_reports_the_package_version(self) -> None:
        with redirect_stdout(StringIO()) as out, self.assertRaises(SystemExit) as result:
            main(["--version"])
        self.assertEqual(result.exception.code, EXIT_SUCCESS)
        self.assertEqual(out.getvalue().strip(), f"tinarrative {tinarrative.__version__}")

    def test_cli_runs_without_arguments(self) -> None:
        self.assertEqual(main([]), EXIT_SUCCESS)

    def test_placeholder_commands_have_stable_exit_codes(self) -> None:
        for command in ("parse", "diff"):
            with self.subTest(command=command), redirect_stderr(StringIO()):
                self.assertEqual(main([command]), EXIT_NOT_IMPLEMENTED)

    def test_subcommand_help_does_not_need_a_save_file(self) -> None:
        for command in ("inspect", "parse", "diff"):
            with self.subTest(command=command), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main([command, "--help"])
            self.assertEqual(result.exception.code, EXIT_SUCCESS)


if __name__ == "__main__":
    unittest.main()
