import { useRef, useState, useEffect } from "react";

export function ImageDropZone({ label, hint, file, onChange }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState(null);

  // 파일이 바뀔 때마다 미리보기 URL을 생성하고, 정리 시 해제한다.
  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith("image/")) onChange(f);
  };

  return (
    <div className="space-y-1.5">
      <span className="field-label">{label}</span>

      <div
        className={`
          relative border overflow-hidden cursor-pointer transition-colors duration-150
          ${dragging ? "border-ink bg-warm" : "border-border hover:border-ink"}
          ${preview ? "h-72" : "h-40"}
        `}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        {preview ? (
          <>
            <img
              src={preview}
              alt="미리보기"
              className="w-full h-full object-contain bg-warm"
            />
            <button
              className="absolute top-2 right-2 bg-paper border border-border
                         w-6 h-6 flex items-center justify-center text-muted
                         text-xs hover:border-ink hover:text-ink transition-colors"
              onClick={(e) => { e.stopPropagation(); onChange(null); }}
            >
              ✕
            </button>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-2 px-4 text-center">
            <div className="w-8 h-px bg-border mb-1" />
            <p className="text-xs text-muted">
              클릭하거나 파일을 끌어다 놓으세요
            </p>
            {hint && <p className="text-xs text-muted opacity-60">{hint}</p>}
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        />
      </div>
    </div>
  );
}
