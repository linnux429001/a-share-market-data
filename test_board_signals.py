"""Offline regression tests for board signal processing. No external network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import board_signals

def sample(at, pct):
    return {"collected_at": at, "source": "test", "market_data_timestamp": None,
            "industry": {"top": [{"code": str(100+i), "name": "行业"+str(i),
                                  "change_pct": pct if i == 0 else 0,
                                  "turnover_cny": 100000000} for i in range(35)]},
            "concept": {"top": []}}

class BoardSignalsTest(unittest.TestCase):
    def run_case(self, snapshots):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(board_signals, "ROOT", root), \
                 patch.object(board_signals, "HISTORY", root/"board_history.json"), \
                 patch.object(board_signals, "OUTPUT", root/"board_signals.json"):
                for s in snapshots:
                    (root/"latest.json").write_text(json.dumps(s), encoding="utf-8")
                    board_signals.main()
                return json.loads((root/"board_signals.json").read_text(encoding="utf-8"))

    def test_acceleration(self):
        result = self.run_case([sample("2026-11-11T10:00:00+08:00", 0.5),
                                sample("2026-11-11T10:05:00+08:00", 2.5)])
        self.assertEqual(result["alert_count"], 1)
        self.assertEqual(result["alerts"][0]["code"], "100")

    def test_no_cross_day_false_alarm(self):
        result = self.run_case([sample("2026-11-10T14:55:00+08:00", 0.5),
                                sample("2026-11-11T09:35:00+08:00", 3)])
        self.assertEqual(result["alert_count"], 0)

    def test_no_false_alarm_for_old_snapshot(self):
        result = self.run_case([sample("2026-11-11T09:30:00+08:00", 0.5),
                                sample("2026-11-11T13:30:00+08:00", 3)])
        self.assertEqual(result["alert_count"], 0)

if __name__ == "__main__":
    unittest.main()
