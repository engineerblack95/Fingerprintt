export function ChartTooltip({ active, payload, label, labelFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">
        {labelFormatter ? labelFormatter(label) : label}
      </div>
      {payload.map((item) => (
        <div className="chart-tooltip-row" key={`${item.dataKey}-${item.name}`}>
          <span
            className="chart-tooltip-dot"
            style={{ background: item.color || item.payload?.fill || item.fill }}
          />
          <span>{item.name}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}
