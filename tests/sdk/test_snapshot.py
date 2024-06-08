import unittest
from pathlib import Path
from unittest.mock import MagicMock

from dynatrace_extension import Extension

test_data_dir = Path(__file__).parent.parent / "data"


class TestSnapshot(unittest.TestCase):
    def test_snapshot_parsing(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension.initialize()

        snapshot = extension.get_snapshot(test_data_dir / "snapshot.json")
        self.assertIsNotNone(snapshot)
        assert snapshot.host_id == "0X524E3E2974F9AC2A"
        self.assertEqual(len(snapshot.entries), 24)

        processes = snapshot.get_process_groups_by_technology("DOCKER")
        self.assertEqual(len(processes), 4)
