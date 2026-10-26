import unittest

import pandas as pd

from app import analysis as an


def ts(s):
    return pd.Timestamp(s, tz="UTC")


class DecisionSelection(unittest.TestCase):
    def setUp(self):
        # Target: 2026-01-15 12:00Z. Cut-off (09:00 on 14th) -> 2026-01-14 09:00Z.
        self.f = pd.DataFrame(
            {
                "publishTime": [ts("2026-01-13 20:00"), ts("2026-01-14 08:00"),
                                ts("2026-01-14 09:00"), ts("2026-01-14 10:00")],
                "startTime": [ts("2026-01-15 12:00")] * 4,
                "generation": [100.0, 200.0, 300.0, 999.0],
            }
        )

    def test_latest_before_cutoff_is_chosen_and_later_is_excluded(self):
        out = an.select_decision_forecasts(self.f, (9, 0), "2026-01-15", "2026-01-15")
        self.assertEqual(len(out), 1)
        self.assertEqual(out.iloc[0]["forecast"], 300.0)  # 09:00 inclusive, 10:00 excluded

    def test_earlier_cutoff_changes_vintage(self):
        out = an.select_decision_forecasts(self.f, (8, 30), "2026-01-15", "2026-01-15")
        self.assertEqual(out.iloc[0]["forecast"], 200.0)

    def test_early_cutoff_falls_back_to_older_vintage(self):
        out = an.select_decision_forecasts(self.f, (6, 0), "2026-01-15", "2026-01-15")
        self.assertEqual(out.iloc[0]["forecast"], 100.0)  # only the 13th 20:00 run is old enough

    def test_no_forecast_before_cutoff_gives_empty(self):
        late_only = self.f[self.f["publishTime"] >= ts("2026-01-14 08:00")]
        out = an.select_decision_forecasts(late_only, (6, 0), "2026-01-15", "2026-01-15")
        self.assertEqual(len(out), 0)

    def test_other_delivery_dates_ignored(self):
        out = an.select_decision_forecasts(self.f, (9, 0), "2026-01-20", "2026-01-21")
        self.assertEqual(len(out), 0)


class Metrics(unittest.TestCase):
    def test_known_values(self):
        df = pd.DataFrame(
            {
                "forecast": [110.0, 90.0, 100.0, 140.0],
                "actual": [100.0, 100.0, 100.0, 100.0],
            }
        )
        df["error"] = df["forecast"] - df["actual"]  # 10, -10, 0, 40
        m = an.compute_metrics(df)
        self.assertEqual(m["n"], 4)
        self.assertAlmostEqual(m["mae"], 15.0)
        self.assertAlmostEqual(m["bias"], 10.0)
        self.assertAlmostEqual(m["rmse"], ((100 + 100 + 0 + 1600) / 4) ** 0.5, places=1)
        self.assertAlmostEqual(m["wape_pct"], 15.0)
        self.assertAlmostEqual(m["overforecast_share_pct"], 50.0)

    def test_empty(self):
        self.assertEqual(an.compute_metrics(pd.DataFrame({"error": [], "actual": [], "forecast": []}))["n"], 0)

    def test_nan_actuals_are_skipped(self):
        df = pd.DataFrame({"forecast": [1.0, 2.0], "actual": [1.0, float("nan")]})
        df["error"] = df["forecast"] - df["actual"]
        self.assertEqual(an.compute_metrics(df)["n"], 1)


class ErrorBand(unittest.TestCase):
    def test_leave_one_out_excludes_day(self):
        d1, d2 = pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-03")
        df = pd.DataFrame(
            {"delivery_date": [d1] * 48 + [d2] * 48, "error": [10.0] * 48 + [1000.0] * 48}
        )
        band = an.error_band(df, exclude_date=d2)
        self.assertEqual(band["n"], 48)
        self.assertAlmostEqual(band["q_hi"], 10.0)

    def test_too_little_data_returns_none(self):
        df = pd.DataFrame({"delivery_date": [pd.Timestamp("2026-01-02")] * 5, "error": [1.0] * 5})
        self.assertIsNone(an.error_band(df))


class Cutoff(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(an.parse_cutoff("09:20"), (9, 20))
        for bad in ("9", "25:00", "ab:cd", "09:61"):
            with self.assertRaises(ValueError):
                an.parse_cutoff(bad)


if __name__ == "__main__":
    unittest.main()
