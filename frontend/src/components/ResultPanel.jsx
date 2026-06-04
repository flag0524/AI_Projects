export default function ResultPanel({ imageBase64, processingMs, error }) {
  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = imageBase64
    a.download = `fitting_result_${Date.now()}.png`
    a.click()
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-64 gap-3">
        <div className="text-4xl">⚠️</div>
        <p className="text-red-500 text-sm font-medium text-center px-4">{error}</p>
      </div>
    )
  }

  if (!imageBase64) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-64 gap-4 text-gray-300">
        <div className="text-6xl">👗</div>
        <p className="text-sm">피팅 결과가 여기에 표시됩니다</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl overflow-hidden border border-gray-100 shadow-sm bg-gray-50">
        <img
          src={imageBase64}
          alt="피팅 결과"
          className="w-full object-contain max-h-[500px]"
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">
          처리 시간: <span className="font-medium text-gray-600">{(processingMs / 1000).toFixed(2)}초</span>
        </span>
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium
            hover:bg-emerald-700 transition-colors shadow-sm"
        >
          <span>⬇</span> 다운로드
        </button>
      </div>
    </div>
  )
}
