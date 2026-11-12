import { useState } from "react";
import { fmtInt } from "../format.js";

// Hand-written SVG line chart: one product's last 12 weeks (solid) + 4-week forecast (dashed).
// A chart library would add ~100 KB to the bundle for this one chart.
const W = 720;
const H = 260;
const PAD = { top: 16, right: 76, bottom: 28, left: 52 };
const TICKS = 4;

function niceMax(value) {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / magnitude) * magnitude;
}

const shortDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

export default function ForecastChart({ product, historyWeeks, forecastWeeks }) {
  const [active, setActive] = useState(null);
  const points = [
    ...product.history.map((value, i) => ({ week: historyWeeks[i], value, kind: "Actual" })),
    ...product.forecast.map((value, i) => ({ week: forecastWeeks[i], value, kind: "Forecast" })),
  ];
  const yMax = niceMax(Math.max(...points.map((p) => p.value)) * 1.05);
  const x = (i) => PAD.left + (i / (points.length - 1)) * (W - PAD.left - PAD.right);
  const y = (v) => PAD.top + (1 - v / yMax) * (H - PAD.top - PAD.bottom);
  const path = (list) => list.map((p) => `${x(p.i)},${y(p.value)}`).join(" ");

  const indexed = points.map((p, i) => ({ ...p, i }));
  const actual = indexed.filter((p) => p.kind === "Actual");
  // The forecast line starts at the last actual point so the two lines connect.
  const forecast = [actual[actual.length - 1], ...indexed.filter((p) => p.kind === "Forecast")];
  const last = indexed[indexed.length - 1];
  const lastActual = actual[actual.length - 1];

  function pointerMove(event) {
    const box = event.currentTarget.getBoundingClientRect();
    const svgX = ((event.clientX - box.left) / box.width) * W;
    const i = Math.round(((svgX - PAD.left) / (W - PAD.left - PAD.right)) * (points.length - 1));
    setActive(Math.max(0, Math.min(points.length - 1, i)));
  }

  function keyDown(event) {
    if (event.key === "ArrowRight") setActive((a) => Math.min(points.length - 1, (a ?? -1) + 1));
    if (event.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? points.length) - 1));
  }

  const hovered = active == null ? null : indexed[active];

  return (
    <figure className="chart">
      <div className="chart-box">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`Weekly units for ${product.description}: last 12 weeks and 4-week forecast. Use arrow keys to read values.`}
          tabIndex={0}
          onPointerMove={pointerMove}
          onPointerLeave={() => setActive(null)}
          onFocus={() => setActive(points.length - 1)}
          onBlur={() => setActive(null)}
          onKeyDown={keyDown}
        >
          {Array.from({ length: TICKS + 1 }, (_, k) => {
            const v = (yMax / TICKS) * k;
            return (
              <g key={k}>
                <line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} />
                <text className="axis" x={PAD.left - 8} y={y(v)} dy="0.32em" textAnchor="end">{fmtInt(v)}</text>
              </g>
            );
          })}
          {indexed.filter((_, i) => i % 3 === 0 || i === points.length - 1).map((p) => (
            <text key={p.i} className="axis" x={x(p.i)} y={H - 8} textAnchor="middle">{shortDate(p.week)}</text>
          ))}
          <line className="today" x1={x(lastActual.i)} x2={x(lastActual.i)} y1={PAD.top} y2={H - PAD.bottom} />

          <polyline className="line actual" points={path(actual)} />
          <polyline className="line forecast" points={path(forecast)} />
          <text className="direct-label" x={x(lastActual.i) - 6} y={PAD.top + 10} textAnchor="end">Actual</text>
          <text className="direct-label" x={x(last.i) + 8} y={y(last.value)} dy="0.32em">Forecast</text>

          {hovered && (
            <g>
              <line className="crosshair" x1={x(hovered.i)} x2={x(hovered.i)} y1={PAD.top} y2={H - PAD.bottom} />
              <circle className="marker" cx={x(hovered.i)} cy={y(hovered.value)} r="5" />
            </g>
          )}
        </svg>
        {hovered && (
          <div
            className="tooltip"
            style={{ left: `${(x(hovered.i) / W) * 100}%`, top: `${(y(hovered.value) / H) * 100}%` }}
          >
            <strong>{fmtInt(hovered.value)} units</strong>
            <span>{hovered.kind} · week to {shortDate(hovered.week)}</span>
          </div>
        )}
      </div>
      <figcaption className="muted">
        Solid: real weekly units. Dashed: forecast for the next 4 weeks. Weeks end on the date shown.
      </figcaption>
    </figure>
  );
}
