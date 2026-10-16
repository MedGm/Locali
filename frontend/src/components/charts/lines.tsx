"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { BarSeries } from "./bars";

// Lines over runs, same rules as the bars: 2px lines, 8px markers, a legend for two or more series,
// recessive grid and axes, one y axis, and a crosshair tooltip.
export function RunLines({
  data,
  series,
  unit = "",
  max,
  height = 260,
}: {
  data: Record<string, string | number | null>[];
  series: BarSeries[];
  unit?: string;
  max?: number;
  height?: number;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--viz-grid)" strokeWidth={1} />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--viz-muted)", fontSize: 12 }}
            axisLine={{ stroke: "var(--viz-axis)" }}
            tickLine={false}
          />
          <YAxis
            domain={[0, max ?? "auto"]}
            allowDecimals={false}
            tick={{ fill: "var(--viz-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            unit={unit}
            width={48}
          />
          <Tooltip
            cursor={{ stroke: "var(--viz-axis)", strokeWidth: 1 }}
            formatter={(value, name) => [value == null ? "n/a" : `${value}${unit}`, name]}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          {series.length > 1 && (
            <Legend
              verticalAlign="top"
              align="left"
              iconType="circle"
              wrapperStyle={{ fontSize: 12, paddingBottom: 8 }}
              formatter={(value) => <span style={{ color: "var(--viz-ink-2)" }}>{value}</span>}
            />
          )}
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              dot={{ r: 4, fill: s.color, stroke: "var(--background)", strokeWidth: 2 }}
              activeDot={{ r: 5 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
