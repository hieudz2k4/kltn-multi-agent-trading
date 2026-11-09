import { useId } from "react";

type SparklineCellProps = {
  values?: number[];
  width?: number;
  height?: number;
  showEndpoint?: boolean;
};

export function SparklineCell({ values = [], width = 118, height = 36, showEndpoint = true }: SparklineCellProps) {
  const gradientId = useId();
  if (values.length < 2) {
    return <span className="text-terminal-muted">--</span>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const rising = values[values.length - 1] >= values[0];
  const stroke = rising ? "#00e676" : "#ff5252";
  const fill = rising ? "#00e676" : "#ff5252";
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - 4 - ((value - min) / range) * (height - 8);
      return `${x},${y}`;
    })
    .join(" ");
  const firstPoint = points.split(" ")[0];
  const lastPoint = points.split(" ")[points.split(" ").length - 1];
  const areaPoints = `${firstPoint} ${points} ${width},${height} 0,${height}`;
  const [lastX, lastY] = lastPoint.split(",").map(Number);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={fill} stopOpacity="0.24" />
          <stop offset="100%" stopColor={fill} stopOpacity="0" />
        </linearGradient>
      </defs>
      <line x1="0" x2={width} y1={height / 2} y2={height / 2} stroke="rgba(148, 163, 184, 0.18)" strokeDasharray="3 4" />
      <polygon fill={`url(#${gradientId})`} points={areaPoints} />
      <polyline fill="none" stroke={stroke} strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" points={points} />
      {showEndpoint ? <circle cx={lastX} cy={lastY} r="2.4" fill={stroke} stroke="#020617" strokeWidth="1" /> : null}
    </svg>
  );
}
