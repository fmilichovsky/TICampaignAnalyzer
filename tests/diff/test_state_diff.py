import unittest

from tinarrative.diff.state_diff import diff_states
from tinarrative.model.snapshot import SaveSnapshot


class DiffStatesTests(unittest.TestCase):
    def test_diff_preserves_snapshots(self) -> None:
        before = SaveSnapshot(source="before.save", date="2030-01-01")
        after = SaveSnapshot(source="after.save", date="2030-02-01")
        result = diff_states(before, after)
        self.assertEqual(result.before, before)
        self.assertEqual(result.after, after)
        self.assertEqual(result.changes, [])


if __name__ == "__main__":
    unittest.main()
