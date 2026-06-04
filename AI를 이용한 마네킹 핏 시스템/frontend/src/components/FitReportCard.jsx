function EaseLine({ label, valueCm }) {
  if (valueCm == null) return null;
  const sign = valueCm > 0 ? "+" : "";
  const color =
    valueCm < -2  ? "text-red-600" :
    valueCm < 4   ? "text-amber-600" :
    valueCm < 18  ? "text-green-700" :
                    "text-blue-600";

  return (
    <div className="flex items-baseline justify-between py-2 border-b border-border last:border-0">
      <span className="text-sm text-ink">{label}</span>
      <span className={`text-sm font-medium tabular-nums ${color}`}>
        {sign}{valueCm.toFixed(1)} cm
      </span>
    </div>
  );
}

export function FitReportCard({ report }) {
  if (!report) return null;

  return (
    <div className="section">
      <div className="flex items-baseline justify-between mb-2">
        <p className="section-title mb-0">핏 분석</p>
        {report.fit_label && (
          <span className="text-xs text-ink border-b border-ink pb-px">
            {report.fit_label}
          </span>
        )}
      </div>

      <div>
        <EaseLine label="가슴 여유분" valueCm={report.chest_ease_cm} />
        <EaseLine label="허리 여유분" valueCm={report.waist_ease_cm} />
        <EaseLine label="엉덩이 여유분" valueCm={report.hip_ease_cm} />
      </div>

      {report.length_landmark && (
        <p className="text-sm text-muted mt-2">
          옷자락 위치 — <span className="text-ink">{report.length_landmark}</span>
        </p>
      )}

      {report.estimated && (
        <p className="text-xs text-muted mt-3">
          * 치수 미입력으로 이미지 비율 기반 추정값을 사용했습니다.
        </p>
      )}

      {report.warnings?.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {report.warnings.map((w, i) => (
            <p key={i} className="text-xs text-accent">
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
