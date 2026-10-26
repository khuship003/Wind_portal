const TZ = "Europe/London";

export const mw = (v) => (v == null ? "–" : `${Math.round(v).toLocaleString("en-GB")} MW`);
export const num = (v, d = 0) =>
  v == null ? "–" : Number(v).toLocaleString("en-GB", { maximumFractionDigits: d });

export const timeLabel = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: TZ });

export const dateTimeLabel = (iso) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: TZ,
      }) + " UK"
    : "–";

export const shortDate = (yyyymmdd) =>
  new Date(`${yyyymmdd}T12:00:00Z`).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
