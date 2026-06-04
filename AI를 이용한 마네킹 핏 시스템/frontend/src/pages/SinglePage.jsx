import { useState } from "react";
import { ImageDropZone } from "../components/ImageDropZone";
import { SizeInputPanel } from "../components/SizeInputPanel";
import { CategoryRadio } from "../components/CategoryRadio";

const FIT_MODES = [
  { value: "auto",    label: "자동" },
  { value: "tight",   label: "타이트" },
  { value: "regular", label: "레귤러" },
  { value: "loose",   label: "루즈" },
];

export function SinglePage({ mannequinFile, onMannequinChange, onSubmit, onSubmitLayered, isProcessing }) {
  const [category, setCategory] = useState("general");
  const [topFile,    setTopFile]    = useState(null);
  const [bottomFile, setBottomFile] = useState(null);
  const [topSize,    setTopSize]    = useState({});
  const [bottomSize, setBottomSize] = useState({});
  const [garmentFile, setGarmentFile] = useState(null);
  const [size,        setSize]        = useState({});
  const [form, setForm] = useState({
    fitMode: "auto",
    numCandidates: 1,
    removeBackground: false,
  });

  const handleCategoryChange = (cat) => {
    setCategory(cat);
    setTopFile(null); setBottomFile(null);
    setTopSize({}); setBottomSize({});
    setGarmentFile(null); setSize({});
  };

  const bothUploaded = category === "general" && topFile && bottomFile;
  const canSubmitGeneral = mannequinFile && (topFile || bottomFile) && !isProcessing;
  const canSubmitOther   = mannequinFile && garmentFile && !isProcessing;
  const canSubmit = category === "general" ? canSubmitGeneral : canSubmitOther;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    if (category === "general") {
      if (topFile && bottomFile) {
        onSubmitLayered({ mannequinFile, topFile, bottomFile, form: { ...form, topSize, bottomSize } });
      } else {
        const isTop = !!topFile;
        onSubmit({
          mannequinFile,
          garmentFile: isTop ? topFile : bottomFile,
          form: { ...form, category: isTop ? "top" : "bottom", size: isTop ? topSize : bottomSize },
        });
      }
    } else {
      onSubmit({ mannequinFile, garmentFile, form: { ...form, category, size } });
    }
  };

  const uploadHint = {
    dress:     "원피스 전체 이미지 — 흰 배경 또는 누끼",
    accessory: "악세서리 단독 이미지 — 흰 배경 권장",
  }[category] ?? "";

  return (
    <form onSubmit={handleSubmit} className="space-y-8">

      <div>
        <p className="section-title">마네킹</p>
        <ImageDropZone
          label="마네킹 이미지"
          hint="JPG, PNG · 정면 촬영 권장"
          file={mannequinFile}
          onChange={onMannequinChange}
        />
      </div>

      <div className="section">
        <p className="section-title">의류 종류</p>
        <CategoryRadio value={category} onChange={handleCategoryChange} />
      </div>

      <div className="section">
        <p className="section-title">의류 이미지</p>

        {category === "general" ? (
          <div className="space-y-6">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="field-label mb-0">상의</span>
                <span className="text-xs text-muted">선택 입력</span>
              </div>
              <ImageDropZone
                label=""
                hint="티셔츠 · 셔츠 · 재킷 · 코트 — 흰 배경 권장"
                file={topFile}
                onChange={setTopFile}
              />
              {topFile && (
                <div className="mt-3">
                  <SizeInputPanel category="top" values={topSize} onChange={setTopSize} />
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted">+</span>
              <div className="flex-1 h-px bg-border" />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="field-label mb-0">하의</span>
                <span className="text-xs text-muted">선택 입력</span>
              </div>
              <ImageDropZone
                label=""
                hint="바지 · 스커트 · 레깅스 — 흰 배경 권장"
                file={bottomFile}
                onChange={setBottomFile}
              />
              {bottomFile && (
                <div className="mt-3">
                  <SizeInputPanel category="bottom" values={bottomSize} onChange={setBottomSize} />
                </div>
              )}
            </div>

            {bothUploaded && (
              <p className="text-xs text-ink border-l-2 border-ink pl-3 leading-relaxed">
                상의와 하의가 모두 업로드됐습니다.
                자동으로 레이어링 합성을 진행합니다.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <ImageDropZone
              label=""
              hint={uploadHint}
              file={garmentFile}
              onChange={setGarmentFile}
            />
            {garmentFile && (
              <SizeInputPanel category={category} values={size} onChange={setSize} />
            )}
          </div>
        )}
      </div>

      <div className="section">
        <p className="section-title">옵션</p>
        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <label className="field-label">핏 강도</label>
            <div className="relative">
              <select
                className="field-select pr-6"
                value={form.fitMode}
                onChange={(e) => setForm((f) => ({ ...f, fitMode: e.target.value }))}
              >
                {FIT_MODES.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <span className="absolute right-0 top-1/2 -translate-y-1/2 text-muted text-xs pointer-events-none">v</span>
            </div>
          </div>

          {!bothUploaded && (
            <div>
              <label className="field-label">후보 수</label>
              <div className="relative">
                <select
                  className="field-select pr-6"
                  value={form.numCandidates}
                  onChange={(e) => setForm((f) => ({ ...f, numCandidates: Number(e.target.value) }))}
                >
                  {[1, 2, 3, 4].map((n) => (
                    <option key={n} value={n}>{n}장</option>
                  ))}
                </select>
                <span className="absolute right-0 top-1/2 -translate-y-1/2 text-muted text-xs pointer-events-none">v</span>
              </div>
            </div>
          )}
        </div>

        <label className="flex items-center gap-2.5 mt-4 cursor-pointer w-fit">
          <input
            type="checkbox"
            className="w-3.5 h-3.5 accent-ink"
            checked={form.removeBackground}
            onChange={(e) => setForm((f) => ({ ...f, removeBackground: e.target.checked }))}
          />
          <span className="text-sm text-muted">배경 자동 제거</span>
        </label>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="btn-primary w-full py-3 text-center"
      >
        {isProcessing
          ? "생성 중..."
          : bothUploaded
            ? "상하의 레이어링 생성"
            : "피팅 이미지 생성"}
      </button>
    </form>
  );
}
