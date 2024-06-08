import unittest
from pathlib import Path
from unittest.mock import MagicMock

from dynatrace_extension import Extension
from dynatrace_extension.sdk.snapshot import Snapshot

test_data_dir = Path(__file__).parent.parent / "data"


class TestSnapshot(unittest.TestCase):
    def test_extension_get_snapshot(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension.initialize()

        snapshot = extension.get_snapshot(test_data_dir / "snapshot.json")
        self.assertIsNotNone(snapshot)
        assert snapshot.host_id == "HOST-524E3E2974F9AC2A"
        self.assertEqual(len(snapshot.entries), 24)

        processes = snapshot.get_process_groups_by_technology("DOCKER")
        self.assertEqual(len(processes), 4)

    def test_snapshot_parsing(self):
        snapshot = Snapshot.parse_from_file(test_data_dir / "snapshot.json")
        self.assertIsNotNone(snapshot)
        assert snapshot.host_id == "HOST-524E3E2974F9AC2A"
        self.assertEqual(len(snapshot.entries), 24)

        for entry in snapshot.entries:
            for process in entry.processes:
                if process.process_name in ("squid", "squid.exe"):
                    self.assertEqual(entry.process_type, 0)
                    self.assertEqual(entry.group_name, "squid")
                    self.assertEqual(len(entry.properties.technologies), 1)
                    self.assertEqual(len(entry.properties.pg_technologies), 1)
                    self.assertEqual(len(entry.processes), 1)
                    self.assertEqual(process.process_name, "squid")
                    self.assertEqual(process.pid, 2245656)
                    self.assertEqual(len(process.properties.listening_ports), 1)
                    self.assertEqual(process.properties.listening_ports[0], 3128)
                    self.assertEqual(process.properties.cmd_line, "-f /etc/squid/squid.conf -NYC")
                    self.assertEqual(len(process.properties.port_bindings), 1)

                    self.assertEqual(process.properties.port_bindings[0].ip, "127.0.0.1")
                    self.assertEqual(process.properties.port_bindings[0].port, 3128)
