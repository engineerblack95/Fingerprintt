import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { STATUS_META } from '../utils/constants';
import { ChartTooltip } from './ChartTooltip';

export function StatusDonut({ data = [], total = 0 }) {
  const safeData = total
    ? data
    : [{ status: 'EMPTY', count: 1, label: 'No entries yet' }];
  const displayData = safeData.map((item) => ({
    ...item,
    label: STATUS_META[item.status]?.label || item.label || item.status,
  }));

  return (
    <div className="donut-layout">
      <div className="donut-chart">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={displayData}
              dataKey="count"
              nameKey="label"
              innerRadius="68%"
              outerRadius="92%"
              paddingAngle={total ? 4 : 0}
              cornerRadius={8}
              stroke="none"
            >
              {displayData.map((entry) => (
                <Cell
                  key={entry.status}
                  fill={
                    entry.status === 'EMPTY'
                      ? '#e8edf5'
                      : STATUS_META[entry.status]?.color || '#cbd5e1'
                  }
                />
              ))}
            </Pie>
            {total ? (
              <Tooltip content={<ChartTooltip />} />
            ) : null}
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <strong>{total}</strong>
          <span>today</span>
        </div>
      </div>

      <ul className="donut-legend">
        {data.map((item) => {
          const meta = STATUS_META[item.status];
          const percent = total ? Math.round((item.count / total) * 100) : 0;
          return (
            <li key={item.status}>
              <span className="legend-dot" style={{ background: meta.color }} />
              <span className="legend-label">{meta.label}</span>
              <span className="legend-count">{item.count}</span>
              <span className="legend-percent">{percent}%</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
