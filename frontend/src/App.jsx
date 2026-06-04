import { useState } from 'react'
import UploadPanel from './components/UploadPanel.jsx'
import ResultPanel from './components/ResultPanel.jsx'
import LoadingSpinner from './components/LoadingSpinner.jsx'
import { submitFitting } from './api/fitApi.js'

export default function App() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [processingMs, setProcessingMs] = useState(0)
  const [error, setError] = useState(null)

  const handleSubmit = async (formData) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await submitFitting(formData)
      setResult(data.fitted_image_base64)
      setProcessingMs(data.processing_time_ms)
    } catch (e) {
      const msg = e.response?.data?.detail || '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-100 shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-3">
          <span className="text-2xl">👗</span>
          <div>
            <h1 className="text-xl font-bold text-gray-800">마네킹 피팅 시스템</h1>
            <p className="text-xs text-gray-400">AI 기반 가상 의류 합성</p>
          </div>
        </div>
      </header>

      {/* 메인 */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 업로드 패널 */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-base font-semibold text-gray-700 mb-5 flex items-center gap-2">
              <span className="w-6 h-6 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-xs font-bold">1</span>
              이미지 업로드
            </h2>
            <UploadPanel onSubmit={handleSubmit} loading={loading} />
          </div>

          {/* 결과 패널 */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-base font-semibold text-gray-700 mb-5 flex items-center gap-2">
              <span className="w-6 h-6 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center text-xs font-bold">2</span>
              피팅 결과
            </h2>
            {loading ? (
              <LoadingSpinner />
            ) : (
              <ResultPanel imageBase64={result} processingMs={processingMs} error={error} />
            )}
          </div>
        </div>

        {/* 파이프라인 안내 */}
        <div className="mt-8 bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-sm font-semibold text-gray-600 mb-4">처리 파이프라인</h2>
          <div className="flex flex-wrap gap-2 items-center">
            {[
              { icon: '🖼', label: '이미지 전처리' },
              { icon: '✂️', label: '배경 제거' },
              { icon: '🦴', label: '포즈 추정' },
              { icon: '🗂', label: '신체 분할' },
              { icon: '🔄', label: 'TPS 와핑' },
              { icon: '🎨', label: '알파 합성' },
            ].map((step, i) => (
              <div key={i} className="flex items-center gap-1">
                <div className="flex items-center gap-1.5 bg-gray-50 border border-gray-100 rounded-lg px-3 py-1.5">
                  <span>{step.icon}</span>
                  <span className="text-xs text-gray-600">{step.label}</span>
                </div>
                {i < 5 && <span className="text-gray-300 text-xs">→</span>}
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
