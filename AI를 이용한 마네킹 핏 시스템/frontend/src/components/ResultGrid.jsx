import { useState } from "react";

export function ResultGrid({ results, onRegenerate }) {
  const [selected, setSelected] = useState(null);

  if (!results.length) return null;

  return (
    <>
      <div className={`grid gap-2 ${results.length === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
        {results.map((item, i) => (
          <div
            key={i}
            className="relative group border border-border bg-warm cursor-pointer
                       overflow-hidden hover:border-ink transition-colors duration-150"
            onClick={() => setSelected(item)}
          >
            <img
              src={item.image_url}
              alt={`결과 ${i + 1}`}
              className="w-full object-contain"
            />

            {/* 호버 오버레이 */}
            <div className="absolute inset-0 bg-ink/0 group-hover:bg-ink/5 transition-colors" />

            <div className="absolute bottom-0 left-0 right-0 p-2.5 flex justify-between items-center
                            opacity-0 group-hover:opacity-100 transition-opacity bg-paper/90">
              <span className="text-xs text-muted">후보 {i + 1}</span>
              <div className="flex gap-2">
                {onRegenerate && (
                  <button
                    className="text-xs text-ink underline underline-offset-2"
                    onClick={(e) => { e.stopPropagation(); onRegenerate(item.seed); }}
                  >
                    재생성
                  </button>
                )}
                <a
                  href={item.image_url}
                  download={`tryon_${i + 1}.png`}
                  className="text-xs text-ink underline underline-offset-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  저장
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 확대 보기 */}
      {selected && (
        <div
          className="fixed inset-0 bg-ink/70 z-50 flex items-center justify-center p-6"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-paper max-w-lg w-full overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={selected.image_url}
              alt="확대 보기"
              className="w-full object-contain max-h-[72vh] bg-warm"
            />
            <div className="flex items-center justify-between px-4 py-3 border-t border-border">
              <span className="text-xs text-muted">seed {selected.seed}</span>
              <div className="flex gap-4">
                <a
                  href={selected.image_url}
                  download="tryon_result.png"
                  className="text-xs text-ink underline underline-offset-2"
                >
                  고해상도 저장
                </a>
                <button
                  className="text-xs text-muted hover:text-ink"
                  onClick={() => setSelected(null)}
                >
                  닫기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
