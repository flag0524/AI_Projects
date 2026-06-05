import { useState, useEffect } from 'react'
import UploadPanel from './components/UploadPanel.jsx'
import ResultPanel from './components/ResultPanel.jsx'
import LoadingSpinner from './components/LoadingSpinner.jsx'
import { submitFitting, submitGenerate, fetchGenerateStatus } from './api/fitApi.js'

const MODES = [
  { value: 'generate', label: '모델 컷 생성', desc: '실제 모델 착용 컷 (AI)' },
  { value: 'fit',      label: '마네킹 피팅', desc: '마네킹 위 의류 합성' },
]

export default function App() {
  const [mode, setMode]             = useState('generate')
  const [loading, setLoading]       = useState(false)
  const [result, setResult]         = useState(null)
  const [processingMs, setMs]       = useState(0)
  const [method, setMethod]         = useState(null)
  const [error, setError]           = useState(null)
  const [genStatus, setGenStatus]   = useState(null)

  useEffect(() => {
    fetchGenerateStatus().then(setGenStatus).catch(() => setGenStatus(null))
  }, [])

  const handleSubmit = async (payload) => {
    setLoading(true); setError(null); setResult(null); setMethod(null)
    try {
      if (mode === 'generate') {
        const data = await submitGenerate(payload)
        setResult(data.result_image_base64)
        setMs(data.processing_time_ms)
        setMethod(data.method)
      } else {
        const data = await submitFitting(payload)
        setResult(data.fitted_image_base64)
        setMs(data.processing_time_ms)
        setMethod('procedural')
      }
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
        height: '52px', borderBottom: '1px solid var(--border)', background: 'var(--surface)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 32px', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
          <span style={{
            fontSize: '14px', fontWeight: 500, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: 'var(--text-1)',
          }}>LaonGEN</span>
          <span style={{
            fontSize: '10px', letterSpacing: '0.08em', color: 'var(--text-3)', textTransform: 'uppercase',
          }}>모델 착용 컷 생성</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{
            width: '7px', height: '7px', borderRadius: '50%',
            background: loading ? '#F59E0B' : result ? '#10B981' : '#E3E1DA',
            display: 'inline-block', transition: 'background 0.3s',
          }} />
          <span style={{ fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.04em' }}>
            {loading ? '생성 중' : result ? '완료' : '대기'}
          </span>
        </div>
      </header>

      {/* ── 바디 ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* 사이드바 */}
        <aside style={{
          width: '320px', flexShrink: 0, borderRight: '1px solid var(--border)',
          background: 'var(--surface)', display: 'flex', flexDirection: 'column', overflow: 'auto',
        }}>
          {/* 모드 토글 */}
          <div style={{ padding: '16px 24px 0' }}>
            <div style={{
              display: 'flex', gap: '4px', padding: '3px',
              background: '#F0EFEC', borderRadius: 'var(--radius)',
            }}>
              {MODES.map(m => (
                <button
                  key={m.value}
                  onClick={() => { setMode(m.value); setResult(null); setError(null) }}
                  style={{
                    flex: 1, padding: '7px 6px', fontSize: '11px',
                    fontWeight: mode === m.value ? 500 : 400,
                    color: mode === m.value ? 'var(--text-1)' : 'var(--text-3)',
                    background: mode === m.value ? 'var(--surface)' : 'transparent',
                    border: 'none', borderRadius: '3px', cursor: 'pointer',
                    boxShadow: mode === m.value ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                    transition: 'all 0.12s',
                  }}
                >{m.label}</button>
              ))}
            </div>
            <p style={{ fontSize: '10px', color: 'var(--text-3)', marginTop: '8px', letterSpacing: '0.02em' }}>
              {MODES.find(m => m.value === mode)?.desc}
              {mode === 'generate' && genStatus && (
                <span style={{ color: genStatus.generative_available ? '#10B981' : '#B91C1C', marginLeft: '6px' }}>
                  · {genStatus.generative_available ? 'AI 연결됨' : 'AI 미연결'}
                </span>
              )}
            </p>
          </div>

          <div style={{ padding: '16px 24px 24px', flex: 1, display: 'flex', flexDirection: 'column' }}>
            <UploadPanel mode={mode} onSubmit={handleSubmit} loading={loading} />
          </div>
        </aside>

        {/* 메인 뷰어 */}
        <main style={{
          flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)',
        }}>
          <div style={{
            height: '44px', borderBottom: '1px solid var(--border)', background: 'var(--surface)',
            display: 'flex', alignItems: 'center', padding: '0 28px', gap: '20px', flexShrink: 0,
          }}>
            <span style={{
              fontSize: '10px', fontWeight: 500, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: 'var(--text-2)',
            }}>{mode === 'generate' ? '모델 컷 미리보기' : '피팅 미리보기'}</span>

            {result && !loading && (
              <span style={{ fontSize: '10px', color: 'var(--text-3)', letterSpacing: '0.06em' }}>
                PNG · {(processingMs / 1000).toFixed(1)}s
                {method && <span style={{ marginLeft: '8px', textTransform: 'uppercase' }}>· {method}</span>}
              </span>
            )}
          </div>

          <div style={{ flex: 1, padding: '32px', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
            {loading
              ? <LoadingSpinner mode={mode} />
              : <ResultPanel imageBase64={result} processingMs={processingMs} error={error} />
            }
          </div>
        </main>
      </div>
    </div>
  )
}
