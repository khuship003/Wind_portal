import { useEffect, useMemo, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { dateTimeLabel, mw, num, shortDate, timeLabel } from "../format";
import Kpi from "./Kpi";

export default function DecisionView({ meta, cutoff, setCutoff }) {
  const [date, setDate] = useState(meta.decision_start);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setErr(null);
    api
      .decision(date, cutoff)
      .then((d) => live && setData(d))
      .catch((e) => live && (setData(null), setErr(e.message)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [date, cutoff]);

  const chart = useMemo(
    () =>
      (data?.series || []).map((r) => ({
        t: timeLabel(r.startTime),
        forecast: r.forecast,
        actual: r.actual,
        // stacked-area trick: transparent base up to `low`, visible band = high-low
        base: r.low,
        band: r.low != null && r.high != null ? r.high - r.low : null,
        low: r.low,
        high: r.high,
      })),
    [data]
  );

  const s = data?.summary;
  const m = data?.metrics;

  return (
    <section>
      <div className="controls">
        <label>
          Decision day (when you buy)
          <input type="date" value={date} min={meta.decision_start} max={meta.decision_end}
                 onChange={(e) => e.target.value && setDate(e.target.value)} />
        </label>
        <label>
          Decision cut-off (UK time)
          <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
        </label>
        {data && (
          <div className="pill">
            Buying for delivery on <b>{shortDate(data.delivery_date)}</b>
          </div>
        )}
      </div>

      {loading && <p className="muted">Loading…</p>}
      {err && <div className="alert">{err}</div>}

      {data && (
        <>
          <p className="callout">
            On <b>{shortDate(data.decision_date)}</b> at <b>{data.cutoff_local}</b> the latest wind forecast
            available for <b>{shortDate(data.delivery_date)}</b> was issued at{" "}
            <b>{dateTimeLabel(s.latest_publish_time)}</b>. Anything published after that could not
            have informed the purchase.
          </p>

          <div className="kpis">
            <Kpi label="Latest forecast issued" value={dateTimeLabel(s.latest_publish_time)} sub="used for every half-hour below" />
            <Kpi label="Average wind" value={mw(s.mean_mw)} sub={`${num(s.total_mwh)} MWh over the day`} />
            <Kpi label="Peak wind" value={mw(s.peak_mw)} sub={`at ${timeLabel(s.peak_time)}`} />
            <Kpi label="Lowest wind" value={mw(s.min_mw)} sub="largest need for other generation" />
            {s.actuals_available && m?.n > 0 && (
              <>
                <Kpi label="Actual error today (MAE)" value={mw(m.mae)} sub="mean |forecast − actual|" />
                <Kpi label="Bias" value={mw(m.bias)}
                     sub={m.bias > 0 ? "over-forecast: wind fell short" : "under-forecast: more wind than expected"}
                     tone={m.bias > 0 ? "warn" : "good"} />
              </>
            )}
          </div>

          <div className="card">
            <h3>Wind forecast vs actual – {shortDate(data.delivery_date)}</h3>
            <ResponsiveContainer width="100%" height={380}>
              <ComposedChart data={chart} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="t" interval={5} />
                <YAxis tickFormatter={(v) => `${v / 1000}k`} label={{ value: "MW", angle: -90, position: "insideLeft" }} />
                <Tooltip formatter={(v, n) => (n === "band" || n === "base" ? null : [mw(v), n])}
                         labelFormatter={(l) => `${l} UK`} />
                <Legend />
                <Area dataKey="base" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
                <Area dataKey="band" stackId="b" stroke="none" fill="#2563eb" fillOpacity={0.15}
                      name="Likely range (80%)" isAnimationActive={false} />
                <Line dataKey="forecast" name="Forecast (at cut-off)" stroke="#2563eb" dot={false} strokeWidth={2} />
                <Line dataKey="actual" name="Actual" stroke="#16a34a" dot={false} strokeWidth={2} connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
            {data.band && (
              <p className="muted small">
                {data.band.label}; based on {num(data.band.based_on_points)} half-hours. Excludes the
                selected day, so it never “peeks” at the answer.
              </p>
            )}
          </div>

          <details className="card">
            <summary>Half-hourly numbers</summary>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Time (UK)</th><th>Forecast MW</th><th>Low</th><th>High</th><th>Actual MW</th><th>Error MW</th></tr>
                </thead>
                <tbody>
                  {data.series.map((r) => (
                    <tr key={r.startTime}>
                      <td>{timeLabel(r.startTime)}</td>
                      <td>{num(r.forecast)}</td><td>{num(r.low)}</td><td>{num(r.high)}</td>
                      <td>{num(r.actual)}</td><td>{num(r.error)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
