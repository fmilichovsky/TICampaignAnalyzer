import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

import tinarrative
from tinarrative.cli import EXIT_NOT_IMPLEMENTED, EXIT_SUCCESS, main
from tinarrative.diff.state_diff import diff_states
from tinarrative.model.snapshot import SaveSnapshot


class ProjectSkeletonTests(unittest.TestCase):
    def test_package_imports(self) -> None:
        self.assertEqual(tinarrative.__version__, "0.1.0")

    def test_cli_runs_without_arguments(self) -> None:
        self.assertEqual(main([]), EXIT_SUCCESS)

    def test_placeholder_commands_have_stable_exit_codes(self) -> None:
        for command in ("inspect", "parse", "diff"):
            with self.subTest(command=command), redirect_stderr(StringIO()):
                self.assertEqual(main([command]), EXIT_NOT_IMPLEMENTED)

    def test_subcommand_help_does_not_need_a_save_file(self) -> None:
        for command in ("inspect", "parse", "diff"):
            with self.subTest(command=command), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main([command, "--help"])
            self.assertEqual(result.exception.code, EXIT_SUCCESS)

    def test_diff_preserves_snapshots(self) -> None:
        before = SaveSnapshot(source="before.save", date="2030-01-01")
        after = SaveSnapshot(source="after.save", date="2030-02-01")
        result = diff_states(before, after)
        self.assertEqual(result.before, before)
        self.assertEqual(result.after, after)
        self.assertEqual(result.changes, [])


if __name__ == "__main__":
    unittest.main()
