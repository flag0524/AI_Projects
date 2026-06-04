import { DownloadIcon, AlertIcon, ImageIcon } from './Icons.jsx'

export default function ResultPanel({ imageBase64, processingMs, error }) {
  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = imageBase64
    a.download = `fitting_${Date.now()}.png`
    a.click()
  }

  if (error) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        height: '100%', minHeight: '320px',
        gap: '12px', color: 'var(--danger)',
      }}>
        <AlertIcon size={22} />
        <p style={{ fontSize: '12px', textAlign: 'center', maxWidth: '260px', color: 'var(--text-2)', lineHeight: 1.6 }}>
          {error}
        </p>
      </div>
    )
  }

  if (!imageBase64) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        height: '100%', minHeight: '320px',
        gap: '16px',
        border: '1px dashed var(--border)',
        borderRadius: 'var(--radius)',
        color: 'var(--text-3)',
      }}>
        <ImageIcon size={36} />
        <p style={{ fontSize: '12px', letterSpacing: '0.04em' }}>결과가 여기에 표시됩니다</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0', height: '100%' }}>
      {/* 결과 이미지 */}
      <div style={{
        flex: 1,
        background: '#F7F6F3',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <img
          src={imageBase64}
          alt="피팅 결과"
          style={{ maxWidth: '100%', maxHeight: '520px', objectFit: 'contain', display: 'block' }}
        />
      </div>

      {/* 하단 액션바 */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        paddingTop: '14px',
      }}>
        <span style={{ fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.04em' }}>
          {(processingMs / 1000).toFixed(2)}s
        </span>
        <button
          onClick={handleDownload}
          style={{
            display: 'flex', alignItems: 'center', gap: '7px',
            padding: '8px 16px',
            fontSize: '11px', fontWeight: 500,
            letterSpacing: '0.08em', textTransform: 'uppercase',
            color: 'var(--accent-fg)',
            background: 'var(--accent)',
            border: 'none',
            borderRadius: 'var(--radius)',
            cursor: 'pointer',
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.background = '#333'}
          onMouseLeave={e => e.currentTarget.style.background = 'var(--accent)'}
        >
          <DownloadIcon size={13} /> 저장
        </button>
      </div>
    </div>
  )
}
