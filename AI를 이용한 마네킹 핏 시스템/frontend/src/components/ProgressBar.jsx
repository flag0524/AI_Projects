export function ProgressBar({ step, pct }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-muted">
        <span>{step || "처리 중"}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-px bg-border w-full">
        <div
          className="h-px bg-ink transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
