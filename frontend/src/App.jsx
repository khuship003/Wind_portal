import { useEffect, useState } from "react";
import { api } from "./api";
import DecisionView from "./components/DecisionView.jsx";
import AccuracyView from "./components/AccuracyView.jsx";

export default function App() {
  const [meta, setMeta] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState("decision");
  const [cutoff, setCutoff] = useState("09:00");

  useEffect(() => {
    api.meta()
      .then((m) => { setMeta(m); setCutoff(m.default_cutoff); })
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="app">
      <header>
        <h1>Wind Forecast Portal</h1>
        <p>GB national wind generation · day-ahead purchase decisions · source: Elexon BMRS</p>
        <nav>
          <button className={tab === "decision" ? "on" : ""} onClick={() => setTab("decision")}>
            Decision view
          </button>
          <button className={tab === "accuracy" ? "on" : ""} onClick={() => setTab("accuracy")}>
            Forecast accuracy
          </button>
        </nav>
      </header>

      {meta && meta.source !== "elexon" && (
        <div className="alert">
          ⚠ Showing <b>{meta.source}</b> data, not real Elexon data. Do not use for decisions.
        </div>
      )}
      {err && <div className="alert">{err}</div>}

      {meta && (
        <main>
          {tab === "decision" ? (
            <DecisionView meta={meta} cutoff={cutoff} setCutoff={setCutoff} />
          ) : (
            <AccuracyView meta={meta} cutoff={cutoff} />
          )}
        </main>
      )}

      <footer>
        Data: Elexon BMRS (FUELHH actuals, WINDFOR forecasts)
        {meta?.fetched_at ? ` · snapshot ${meta.fetched_at}` : ""}. Error = forecast − actual.
      </footer>
    </div>
  );
}
