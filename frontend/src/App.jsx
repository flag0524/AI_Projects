import { useState } from 'react'
import UploadPanel from './components/UploadPanel.jsx'
import ResultPanel from './components/ResultPanel.jsx'
import LoadingSpinner from './components/LoadingSpinner.jsx'
import { submitFitting } from './api/fitApi.js'

export default function App() {
  const [loading, setLoading]       = useState(false)
  const [result, setResult]         = useState(null)
  const [processingMs, setMs]       = useState(0)
  const [error, setError]           = useState(null)

  const handleSubmit = async (formData) => {
    setLoading(true); setError(null); setResult(null)
    try {
      const data = await submitFitting(formData)
      setResult(data.fitted_image_base64)
      setMs(data.processing_time_ms)
    } catch (e) {
      setError(e.response?.data?.detail || '처리 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>

      {/* ── 헤더 ── */}
      <header style={{
        height: '52px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 32px',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
          <span style={{
            fontSize: '14px',
            fontWeight: 500,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--text-1)',
          }}>Fitting Studio</span>
          <span style={{
            fontSize: '10px',
            letterSpacing: '0.08em',
            color: 'var(--text-3)',
            textTransform: 'uppercase',
          }}>가상 피팅</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{
            width: '7px', height: '7px',
            borderRadius: '50%',
            background: loading ? '#F59E0B' : result ? '#10B981' : '#E3E1DA',
            display: 'inline-block',
            transition: 'background 0.3s',
          }} />
          <span style={{ fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.04em' }}>
            {loading ? '처리 중' : result ? '완료' : '대기'}
          </span>
        </div>
      </header>

      {/* ── 바디: 사이드바 + 메인 ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* 사이드바 (업로드) */}
        <aside style={{
          width: '320px',
          flexShrink: 0,
          borderRight: '1px solid var(--border)',
          background: 'var(--surface)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
        }}>
          {/* 사이드바 헤더 */}
          <div style={{
            padding: '20px 24px 16px',
            borderBottom: '1px solid var(--border)',
          }}>
            <p style={{
              fontSize: '10px',
              fontWeight: 500,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--text-2)',
            }}>이미지 설정</p>
          </div>

          {/* 업로드 패널 */}
          <div style={{ padding: '20px 24px', flex: 1, display: 'flex', flexDirection: 'column' }}>
            <UploadPanel onSubmit={handleSubmit} loading={loading} />
          </div>
        </aside>

        {/* 메인 뷰어 */}
        <main style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: 'var(--bg)',
        }}>
          {/* 뷰어 상단 툴바 */}
          <div style={{
            height: '44px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--surface)',
            display: 'flex',
            alignItems: 'center',
            padding: '0 28px',
            gap: '20px',
            flexShrink: 0,
          }}>
            <span style={{
              fontSize: '10px',
              fontWeight: 500,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--text-2)',
            }}>결과 미리보기</span>

            {result && !loading && (
              <span style={{
                fontSize: '10px',
                color: 'var(--text-3)',
                letterSpacing: '0.06em',
              }}>
                PNG · {(processingMs / 1000).toFixed(2)}s
              </span>
            )}
          </div>

          {/* 결과 영역 */}
          <div style={{ flex: 1, padding: '32px', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
            {loading
              ? <LoadingSpinner />
              : <ResultPanel imageBase64={result} processingMs={processingMs} error={error} />
            }
          </div>
        </main>
      </div>
    </div>
  )
}
