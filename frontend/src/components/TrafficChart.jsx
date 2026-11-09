import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { CHART_COLORS } from '../utils/constants';
import { ChartTooltip } from './ChartTooltip';

function dayLabel(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(date);
}

export function TrafficChart({ data = [] }) {
  return (
    <div className="chart-wrap chart-wrap-lg">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 12, right: 12, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="gradMembers" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.members} stopOpacity={0.35} />
              <stop offset="100%" stopColor={CHART_COLORS.members} stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="gradVisitors" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.visitors} stopOpacity={0.32} />
              <stop offset="100%" stopColor={CHART_COLORS.visitors} stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="gradUnknowns" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.unknowns} stopOpacity={0.28} />
              <stop offset="100%" stopColor={CHART_COLORS.unknowns} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="4 7" vertical={false} stroke="#e9eef6" />
          <XAxis
            dataKey="date"
            tickFormatter={dayLabel}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 600 }}
            dy={8}
          />
          <YAxis
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            width={38}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
          />
          <Tooltip
            content={<ChartTooltip labelFormatter={(value) => dayLabel(value)} />}
            cursor={{ stroke: '#cbd5e1', strokeDasharray: '4 4' }}
          />
          <Area
            type="monotone"
            dataKey="members"
            name="Members"
            stackId="1"
            stroke={CHART_COLORS.members}
            strokeWidth={2.4}
            fill="url(#gradMembers)"
            activeDot={{ r: 4, strokeWidth: 2 }}
          />
          <Area
            type="monotone"
            dataKey="visitors"
            name="Visitors"
            stackId="1"
            stroke={CHART_COLORS.visitors}
            strokeWidth={2.4}
            fill="url(#gradVisitors)"
            activeDot={{ r: 4, strokeWidth: 2 }}
          />
          <Area
            type="monotone"
            dataKey="unknowns"
            name="Unknowns"
            stackId="1"
            stroke={CHART_COLORS.unknowns}
            strokeWidth={2.4}
            fill="url(#gradUnknowns)"
            activeDot={{ r: 4, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
