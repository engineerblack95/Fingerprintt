import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { ChartTooltip } from './ChartTooltip';

export function HourlyChart({ data = [] }) {
  const currentHour = new Date().getHours();
  return (
    <div className="chart-wrap chart-wrap-sm">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="4 7" vertical={false} stroke="#e9eef6" />
          <XAxis
            dataKey="hour"
            tickFormatter={(hour) => `${hour}:00`}
            interval={3}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#94a3b8', fontSize: 10, fontWeight: 600 }}
            dy={6}
          />
          <YAxis
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            width={34}
            tick={{ fill: '#94a3b8', fontSize: 10 }}
          />
          <Tooltip
            content={<ChartTooltip labelFormatter={(hour) => `${hour}:00 – ${hour}:59`} />}
            cursor={{ fill: 'rgba(99, 102, 241, 0.06)' }}
          />
          <Bar dataKey="count" name="Entries" radius={[6, 6, 0, 0]} maxBarSize={18}>
            {data.map((entry) => (
              <Cell
                key={entry.hour}
                fill={entry.hour === currentHour ? '#4f46e5' : '#c7d2fe'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
