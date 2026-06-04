import { useState } from "react";
import { ImageDropZone } from "../components/ImageDropZone";
import { SizeInputPanel } from "../components/SizeInputPanel";

const FIT_MODES = [
  { value: "auto",    label: "자동" },
  { value: "tight",   label: "타이트" },
  { value: "regular", label: "레귤러" },
  { value: "loose",   label: "루즈" },
];

export function LayeringPage({ mannequinFile, onMannequinChange, onSubmit, isProcessing }) {
  const [topFile, setTopFile] = useState(null);
  const [bottomFile, setBottomFile] = useState(null);
  const [form, setForm] = useState({
    fitMode: "auto",
    removeBackground: false,
    topSize: {},
    bottomSize: {},
  });

  const canSubmit = mannequinFile && topFile && bottomFile && !isProcessing;

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (canSubmit) onSubmit({ mannequinFile, topFile, bottomFile, form }); }}
      className="space-y-8"
    >
      {/* 이미지 업로드 */}
      <div>
        <p className="section-title">이미지</p>
        <div className="space-y-5">
          <ImageDropZone
            label="마네킹"
            hint="정면 촬영 권장"
            file={mannequinFile}
            onChange={onMannequinChange}
          />
          <div className="grid grid-cols-2 gap-3">
            <ImageDropZone
              label="상의"
              hint="흰 배경 권장"
              file={topFile}
              onChange={setTopFile}
            />
            <ImageDropZone
              label="하의"
              hint="흰 배경 권장"
              file={bottomFile}
              onChange={setBottomFile}
            />
          </div>
        </div>
      </div>

      {/* 상의 치수 */}
      <div className="section">
        <SizeInputPanel
          category="top"
          values={form.topSize}
          onChange={(topSize) => setForm((f) => ({ ...f, topSize }))}
        />
      </div>

      {/* 하의 치수 */}
      <div className="section">
        <SizeInputPanel
          category="bottom"
          values={form.bottomSize}
          onChange={(bottomSize) => setForm((f) => ({ ...f, bottomSize }))}
        />
      </div>

      {/* 옵션 */}
      <div className="section">
        <p className="section-title">옵션</p>
        <div className="relative">
          <label className="field-label">핏 강도</label>
          <select
            className="field-select pr-6"
            value={form.fitMode}
            onChange={(e) => setForm((f) => ({ ...f, fitMode: e.target.value }))}
          >
            {FIT_MODES.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <span className="absolute right-0 bottom-2 text-muted text-xs pointer-events-none">↓</span>
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

        <p className="text-xs text-muted mt-4 leading-relaxed">
          상의를 먼저 합성한 뒤 하의를 입히는 방식으로 처리됩니다.
          단일 생성보다 시간이 더 걸릴 수 있습니다.
        </p>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="btn-primary w-full py-3 text-center"
      >
        {isProcessing ? "레이어링 생성 중..." : "상하의 동시 피팅"}
      </button>
    </form>
  );
}
