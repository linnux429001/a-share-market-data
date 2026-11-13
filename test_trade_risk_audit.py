import unittest
from trade_risk_audit import Trade, audit


class RiskAuditTests(unittest.TestCase):
    def test_real_position_exceeds_budget(self):
        result = audit(Trade("688777", 64.37, 1437, 64.37 * 0.95, 300000))
        self.assertTrue(result["exceeds_risk_budget"])
        self.assertEqual(result["max_shares_at_budget"], 932)
        self.assertAlmostEqual(result["stop_loss_cny_before_costs_slippage"], 4625.0, delta=1)

    def test_small_position(self):
        result = audit(Trade("603533", 30, 100, 28.5, 300000))
        self.assertFalse(result["exceeds_risk_budget"])
        self.assertEqual(result["stop_loss_cny_before_costs_slippage"], 150)

    def test_invalid_inputs(self):
        for trade in (
            Trade("X", 10, 100, 10, 300000),
            Trade("X", 10, 0, 9, 300000),
            Trade("X", -1, 100, 0.5, 300000),
            Trade("X", 10, 100, 9, 300000, 0),
        ):
            with self.subTest(trade=trade):
                with self.assertRaises(ValueError):
                    audit(trade)

    def test_no_verified_quote(self):
        result = audit(Trade("X", 10, 100, 9, 300000), quote_timestamp="2026-11-13T14:53:00+08:00")
        self.assertFalse(result["quote_timestamp_verified"])


if __name__ == "__main__":
    unittest.main()
