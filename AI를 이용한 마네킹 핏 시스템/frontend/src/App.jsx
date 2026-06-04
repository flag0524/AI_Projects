import { useState } from "react";
import { SinglePage } from "./pages/SinglePage";
import { LayeringPage } from "./pages/LayeringPage";
import { ResultGrid } from "./components/ResultGrid";
import { FitReportCard } from "./components/FitReportCard";
import { ProgressBar } from "./components/ProgressBar";
import { useTryOn } from "./hooks/useTryOn";

export default function App() {
  const [tab, setTab] = useState("single");
  const [mannequinFile, setMannequinFile] = useState(null);

  const { status, progress, results, fitReport, error, submit, submitLayered, reset } = useTryOn();

  const isProcessing = status === "uploading" || status === "processing";

  const handleReset = () => {
    reset();
    setMannequinFile(null);
  };

  const handleTabChange = (t) => {
    if (isProcessing) return;
    setTab(t);
    reset();
  };

  return (
    <div className="min-h-screen bg-paper">

      {/* 헤더 */}
      <header className="border-b border-border px-8 py-5">
        <div className="max-w-5xl mx-auto flex items-end justify-between">
          <div>
            <h1 className="text-base font-medium tracking-wide text-ink">
              마네킹 핏 시스템
            </h1>
            <p className="text-xs text-muted mt-0.5">Virtual Try-On · M1</p>
          </div>
          {status !== "idle" && (
            <button
              className="text-xs text-muted hover:text-ink underline underline-offset-2 transition-colors"
              onClick={handleReset}
            >
              처음으로
            </button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-8 py-10">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-16">

          {/* 왼쪽 — 입력 */}
          <div>
            {/* 탭 */}
            <div className="flex gap-6 mb-8 border-b border-border pb-4">
              {[
                { id: "single",   label: "의류 피팅" },
                { id: "layering", label: "레이어링 (고급)" },
              ].map((t) => (
                <button
                  key={t.id}
                  className={`text-sm pb-px transition-colors duration-100
                    ${tab === t.id
                      ? "text-ink border-b border-ink"
                      : "text-muted hover:text-ink"
                    }`}
                  onClick={() => handleTabChange(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {tab === "single" ? (
              <SinglePage
                mannequinFile={mannequinFile}
                onMannequinChange={setMannequinFile}
                onSubmit={submit}
                onSubmitLayered={submitLayered}
                isProcessing={isProcessing}
              />
            ) : (
              <LayeringPage
                mannequinFile={mannequinFile}
                onMannequinChange={setMannequinFile}
                onSubmit={submitLayered}
                isProcessing={isProcessing}
              />
            )}
          </div>

          {/* 오른쪽 — 결과 */}
          <div>
            <p className="section-title mb-6">결과</p>

            {/* 대기 */}
            {status === "idle" && (
              <div className="border border-dashed border-border h-80 flex flex-col
                              items-center justify-center text-center gap-3">
                <div className="w-6 h-px bg-border" />
                <p className="text-xs text-muted leading-relaxed">
                  이미지를 업로드하고<br />생성 버튼을 누르면<br />여기에 결과가 표시됩니다.
                </p>
              </div>
            )}

            {/* 진행 중 */}
            {isProcessing && (
              <div className="space-y-8">
                <div className="border border-border h-80 bg-warm flex items-center
                                justify-center">
                  <p className="text-xs text-muted">생성 중</p>
                </div>
                <ProgressBar step={progress.step} pct={progress.pct} />
              </div>
            )}

            {/* 오류 */}
            {status === "error" && (
              <div className="space-y-4">
                <div className="border border-accent/30 bg-accent/5 px-4 py-3">
                  <p className="text-sm text-accent font-medium mb-1">생성 실패</p>
                  <p className="text-xs text-muted">{error}</p>
                </div>
                <button className="btn-ghost text-xs" onClick={handleReset}>
                  다시 시도
                </button>
              </div>
            )}

            {/* 완료 */}
            {status === "done" && (
              <div className="space-y-6">
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-muted">{results.length}장 생성됨</span>
                  <button
                    className="text-xs text-muted hover:text-ink underline underline-offset-2"
                    onClick={handleReset}
                  >
                    다시 시작
                  </button>
                </div>

                <ResultGrid results={results} />
                <FitReportCard report={fitReport} />
              </div>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}
