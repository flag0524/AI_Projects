/**
 * 카테고리별 치수 입력 패널.
 * category: "general" | "dress" | "accessory"
 * general = 상의+하의 통합 필드
 */
const FIELDS = {
  general: [
    { key: "total_length", label: "총장",       placeholder: "65" },
    { key: "chest",        label: "가슴 둘레",  placeholder: "96" },
    { key: "shoulder",     label: "어깨 너비",  placeholder: "42" },
    { key: "waist",        label: "허리 둘레",  placeholder: "76" },
    { key: "hip",          label: "엉덩이 둘레",placeholder: "100" },
    { key: "sleeve",       label: "소매 길이",  placeholder: "60" },
  ],
  dress: [
    { key: "total_length", label: "총장",       placeholder: "105" },
    { key: "chest",        label: "가슴 둘레",  placeholder: "88" },
    { key: "waist",        label: "허리 둘레",  placeholder: "72" },
    { key: "shoulder",     label: "어깨 너비",  placeholder: "37" },
  ],
  accessory: [
    { key: "total_length", label: "길이 / 높이", placeholder: "30" },
    { key: "chest",        label: "둘레 (해당 시)", placeholder: "56" },
  ],
  // 하위 호환 (layering 탭에서 top/bottom 직접 전달)
  top: [
    { key: "total_length", label: "총장",      placeholder: "65" },
    { key: "chest",        label: "가슴 둘레", placeholder: "96" },
    { key: "shoulder",     label: "어깨 너비", placeholder: "42" },
    { key: "sleeve",       label: "소매 길이", placeholder: "60" },
  ],
  bottom: [
    { key: "total_length", label: "총장",        placeholder: "95" },
    { key: "waist",        label: "허리 둘레",   placeholder: "76" },
    { key: "hip",          label: "엉덩이 둘레", placeholder: "100" },
  ],
};

export function SizeInputPanel({ category, values, onChange }) {
  const fields = FIELDS[category] ?? [];
  if (!fields.length) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="field-label mb-0">치수</span>
        <span className="text-xs text-muted">cm · 선택 입력</span>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-4">
        {fields.map(({ key, label, placeholder }) => (
          <div key={key}>
            <label className="field-label">{label}</label>
            <input
              type="number"
              min={0}
              step={0.1}
              className="field-input"
              placeholder={placeholder}
              value={values?.[key] ?? ""}
              onChange={(e) => onChange({ ...values, [key]: e.target.value })}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
