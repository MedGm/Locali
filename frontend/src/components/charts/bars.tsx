"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type BarSeries = { key: string; label: string; color: string };

// Horizontal bars, one row per item. Follows the chart rules used across the app: bars at most 24px
// thick with a 4px rounded end, hairline vertical grid, a legend whenever there are two or more
// series, values in text colours (never the series colour), and a hover tooltip on every bar.
export function HorizontalBars({
  data,
  series,
  unit = "",
  max,
  rowHeight = 44,
}: {
  data: Record<string, string | number | null>[];
  series: BarSeries[];
  unit?: string;
  max?: number;
  rowHeight?: number;
}) {
  const barSize = Math.min(24, Math.floor((rowHeight - 12) / series.length) - 2);
  return (
    <div style={{ height: data.length * rowHeight + 60 }} className="w-full">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 48, bottom: 8, left: 8 }} barGap={2}>
          <CartesianGrid horizontal={false} stroke="var(--viz-grid)" strokeWidth={1} />
          <XAxis
            type="number"
            domain={[0, max ?? "auto"]}
            tick={{ fill: "var(--viz-muted)", fontSize: 12 }}
            axisLine={{ stroke: "var(--viz-axis)" }}
            tickLine={false}
            unit={unit}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={220}
            tick={{ fill: "var(--viz-ink-2)", fontSize: 12 }}
            axisLine={{ stroke: "var(--viz-axis)" }}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "var(--viz-grid)", opacity: 0.4 }}
            formatter={(value, name) => [value == null ? "n/a" : `${value}${unit}`, name]}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          {series.length > 1 && (
            <Legend verticalAlign="top" align="left" iconType="circle" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
          )}
          {series.map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color}
              barSize={barSize}
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
