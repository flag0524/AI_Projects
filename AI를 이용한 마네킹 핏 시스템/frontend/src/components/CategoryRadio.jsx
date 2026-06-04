/**
 * 카테고리 라디오 선택기.
 * 일반의상 / 원피스 / 기타 악세서리
 */
const OPTIONS = [
  {
    value: "general",
    label: "일반 의상",
    desc: "상의 · 하의 · 점프수트 등",
  },
  {
    value: "dress",
    label: "원피스",
    desc: "원피스 · 미니 · 맥시",
  },
  {
    value: "accessory",
    label: "기타 악세서리",
    desc: "모자 · 가방 · 벨트 · 스카프 등",
  },
];

export function CategoryRadio({ value, onChange }) {
  return (
    <div className="space-y-1.5">
      {OPTIONS.map((opt) => (
        <label
          key={opt.value}
          className={`flex items-start gap-3 px-3 py-3 border cursor-pointer
                      transition-colors duration-100 select-none
                      ${value === opt.value
                        ? "border-ink bg-warm"
                        : "border-border hover:border-ink"
                      }`}
        >
          {/* 라디오 */}
          <span className="mt-0.5 flex-shrink-0">
            <span
              className={`inline-block w-3.5 h-3.5 border rounded-full
                          flex items-center justify-center
                          ${value === opt.value ? "border-ink" : "border-border"}`}
            >
              {value === opt.value && (
                <span className="block w-2 h-2 rounded-full bg-ink" />
              )}
            </span>
          </span>
          <span className="flex-1">
            <span className="block text-sm text-ink font-medium leading-tight">
              {opt.label}
            </span>
            <span className="block text-xs text-muted mt-0.5">{opt.desc}</span>
          </span>
          <input
            type="radio"
            name="category"
            value={opt.value}
            checked={value === opt.value}
            onChange={() => onChange(opt.value)}
            className="hidden"
          />
        </label>
      ))}
    </div>
  );
}

export const CATEGORY_OPTIONS = OPTIONS;
