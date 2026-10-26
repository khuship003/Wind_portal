import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { mw, num, shortDate } from "../format";
import Kpi from "./Kpi";

function Chart({ title, note, children }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {children}
      {note && <p className="muted small">{note}</p>}
    </div>
  );
}

export default function AccuracyView({ meta, cutoff }) {
  const [start, setStart] = useState(meta.decision_start);
  const [end, setEnd] = useState(meta.decision_end);
  const [acc, setAcc] = useState(null);
  const [hor, setHor] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (start > end) { setErr("Start date must not be after end date."); return; }
    let live = true;
    setErr(null);
    Promise.all([api.accuracy(start, end, cutoff), api.horizon(start, end)])
      .then(([a, h]) => live && (setAcc(a), setHor(h)))
      .catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [start, end, cutoff]);

  const m = acc?.metrics;
  const q = m?.error_quantiles;
  const hist = (acc?.histogram || []).map((b) => ({ ...b, label: `${num((b.from + b.to) / 2)}` }));
  const hours = (acc?.by_hour || []).map((r) => ({ ...r, h: `${String(r.hour).padStart(2, "0")}:00` }));
  const horizon = (hor?.buckets || []).map((b) => ({ ...b, label: `${b.from_h}–${b.to_h}h` }));
  const daily = (acc?.daily || []).map((d) => ({ ...d, day: shortDate(d.delivery_date) }));

  return (
    <section>
      <div className="controls">
        <label>From decision day
          <input type="date" value={start} min={meta.decision_start} max={meta.decision_end}
                 onChange={(e) => e.target.value && setStart(e.target.value)} />
        </label>
        <label>To decision day
          <input type="date" value={end} min={meta.decision_start} max={meta.decision_end}
                 onChange={(e) => e.target.value && setEnd(e.target.value)} />
        </label>
        <div className="pill">Forecast = latest available at {cutoff} UK on the day before delivery</div>
      </div>

      {err && <div className="alert">{err}</div>}

      {m && m.n > 0 && (
        <>
          <div className="kpis">
            <Kpi label="MAE" value={mw(m.mae)} sub="typical absolute miss" />
            <Kpi label="RMSE" value={mw(m.rmse)} sub="penalises big misses" />
            <Kpi label="Bias" value={mw(m.bias)} sub={m.bias > 0 ? "forecasts run high on average" : "forecasts run low on average"}
                 tone={m.bias > 0 ? "warn" : "good"} />
            <Kpi label="WAPE" value={`${num(m.wape_pct, 1)}%`} sub="total error ÷ total wind" />
            <Kpi label="90% of misses below" value={mw(m.abs_error_p90)} sub={`95%: ${mw(m.abs_error_p95)}`} />
            <Kpi label="Shortfall risk (1 in 10)" value={mw(q?.p90)}
                 sub="wind this far below forecast, or worse" tone="warn" />
          </div>

          <p className="callout">
            <b>How to use this:</b> on a typical day the day-ahead wind forecast is off by about{" "}
            <b>{mw(m.mae)}</b> per half-hour. About 1 half-hour in 10 has wind at least{" "}
            <b>{mw(q?.p90)}</b> below forecast (extra power to buy), and 1 in 10 has at least{" "}
            <b>{mw(q?.p10 != null ? -q.p10 : null)}</b> more than forecast. Based on{" "}
            {num(m.n)} of {num(acc.coverage.expected_targets)} half-hours.
          </p>

          <div className="grid2">
            <Chart title="Daily accuracy" note="Bars: MAE. Line: bias (positive = forecast too high).">
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={daily}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" interval="preserveStartEnd" />
                  <YAxis />
                  <Tooltip formatter={(v) => mw(v)} />
                  <Legend />
                  <ReferenceLine y={0} stroke="#999" />
                  <Bar dataKey="mae" name="MAE (MW)" fill="#2563eb" />
                  <Line dataKey="bias" name="Bias (MW)" stroke="#dc2626" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </Chart>

            <Chart title="Error by time of day (UK)" note="Are some hours harder to forecast?">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={hours}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="h" interval={2} />
                  <YAxis />
                  <Tooltip formatter={(v) => mw(v)} />
                  <Bar dataKey="mae" name="MAE (MW)" fill="#7c3aed" />
                </BarChart>
              </ResponsiveContainer>
            </Chart>

            <Chart title="Error vs forecast lead time"
                   note="All forecast runs, not just the one at cut-off. Shows how much waiting for a fresher forecast would help.">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={horizon}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip formatter={(v) => mw(v)} />
                  <Bar dataKey="mae" name="MAE (MW)" fill="#0891b2" />
                </BarChart>
              </ResponsiveContainer>
            </Chart>

            <Chart title="Error distribution" note="Forecast − actual. Right of zero = wind below forecast (buy more).">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={hist}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" interval={3} />
                  <YAxis />
                  <Tooltip />
                  <ReferenceLine x={hist.find((b) => b.from <= 0 && b.to > 0)?.label} stroke="#999" />
                  <Bar dataKey="count" name="Half-hours" fill="#ea580c" />
                </BarChart>
              </ResponsiveContainer>
            </Chart>
          </div>

          <details className="card">
            <summary>Daily table</summary>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Delivery day</th><th>MAE</th><th>RMSE</th><th>Bias</th><th>WAPE %</th><th>Forecast MWh</th><th>Actual MWh</th></tr>
                </thead>
                <tbody>
                  {acc.daily.map((d) => (
                    <tr key={d.delivery_date}>
                      <td>{shortDate(d.delivery_date)}</td><td>{num(d.mae)}</td><td>{num(d.rmse)}</td>
                      <td>{num(d.bias)}</td><td>{num(d.wape_pct, 1)}</td>
                      <td>{num(d.forecast_mwh)}</td><td>{num(d.actual_mwh)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
      {m && m.n === 0 && <div className="alert">No overlapping forecast and actual data in this range.</div>}
    </section>
  );
}
