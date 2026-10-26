import tempfile
import unittest
from pathlib import Path

from app.main import create_app
from scripts.make_synthetic_data import generate
import json


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        actuals, forecasts = generate("2026-01-01", "2026-01-06")
        actuals.to_csv(d / "actuals.csv", index=False)
        forecasts.to_csv(d / "forecasts.csv", index=False)
        (d / "meta.json").write_text(json.dumps(
            {"source": "synthetic", "decision_start": "2026-01-01", "decision_end": "2026-01-06"}))
        cls.client = create_app(d).test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_health(self):
        self.assertEqual(self.client.get("/api/health").get_json()["status"], "ok")

    def test_meta(self):
        j = self.client.get("/api/meta").get_json()
        self.assertEqual(j["source"], "synthetic")
        self.assertEqual(j["decision_start"], "2026-01-01")

    def test_decision_shape(self):
        r = self.client.get("/api/decision?decision_date=2026-01-03&cutoff=09:00")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(j["delivery_date"], "2026-01-04")
        self.assertEqual(len(j["series"]), 48)
        # No forecast used may be published after the cut-off.
        self.assertLessEqual(j["summary"]["latest_publish_time"], j["cutoff_utc"])
        first = j["series"][0]
        self.assertLessEqual(first["low"], first["forecast"])
        self.assertGreaterEqual(first["high"], first["forecast"])

    def test_decision_validation(self):
        self.assertEqual(self.client.get("/api/decision").status_code, 400)
        self.assertEqual(self.client.get("/api/decision?decision_date=nope").status_code, 400)
        self.assertEqual(self.client.get("/api/decision?decision_date=2026-01-03&cutoff=99:99").status_code, 400)
        self.assertEqual(self.client.get("/api/decision?decision_date=2030-01-03").status_code, 404)

    def test_accuracy(self):
        j = self.client.get("/api/accuracy").get_json()
        self.assertEqual(j["coverage"]["expected_targets"], 6 * 48)
        self.assertGreater(j["metrics"]["n"], 0)
        self.assertGreaterEqual(j["metrics"]["rmse"], j["metrics"]["mae"])
        self.assertEqual(len(j["by_hour"]), 24)
        self.assertEqual(len(j["daily"]), 6)

    def test_horizon_error_grows_with_lead_time(self):
        b = self.client.get("/api/horizon").get_json()["buckets"]
        self.assertGreater(len(b), 3)
        self.assertLess(b[0]["mae"], b[-1]["mae"])  # synthetic data is built this way

    def test_missing_data_is_503(self):
        with tempfile.TemporaryDirectory() as empty:
            r = create_app(Path(empty)).test_client().get("/api/meta")
            self.assertEqual(r.status_code, 503)
            self.assertIn("fetch_data", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
