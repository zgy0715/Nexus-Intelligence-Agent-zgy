interface StatusBadgeProps {
  status: "connected" | "disconnected" | "warning";
  label?: string;
}

const statusConfig = {
  connected: {
    color: "var(--accent)",
    animation: "pulse-glow 2s ease-in-out infinite",
    defaultLabel: "已连接",
  },
  disconnected: {
    color: "var(--error)",
    animation: "none",
    defaultLabel: "已断开",
  },
  warning: {
    color: "var(--warning)",
    animation: "pulse-glow 1.5s ease-in-out infinite",
    defaultLabel: "警告",
  },
};

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <div className="inline-flex items-center gap-2">
      <div
        className="w-2 h-2 rounded-full shrink-0"
        style={{
          background: config.color,
          boxShadow: status !== "disconnected"
            ? `0 0 6px ${config.color}`
            : "none",
          animation: config.animation,
        }}
      />
      {label !== undefined && (
        <span
          className="text-xs"
          style={{
            color: config.color,
            fontFamily: "var(--font-heading)",
          }}
        >
          {label}
        </span>
      )}
      {label === undefined && (
        <span
          className="text-xs"
          style={{
            color: config.color,
            fontFamily: "var(--font-heading)",
          }}
        >
          {config.defaultLabel}
        </span>
      )}
    </div>
  );
}
