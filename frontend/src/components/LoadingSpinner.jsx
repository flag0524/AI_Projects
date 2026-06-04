export default function LoadingSpinner() {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '20px',
      height: '100%',
      minHeight: '320px',
    }}>
      {/* 미니멀 선형 로더 */}
      <div style={{ position: 'relative', width: '48px', height: '48px' }}>
        <svg viewBox="0 0 48 48" fill="none" style={{ width: '100%', height: '100%', animation: 'spin 1.4s linear infinite' }}>
          <circle cx="24" cy="24" r="20" stroke="#E3E1DA" strokeWidth="2"/>
          <path d="M24 4 A20 20 0 0 1 44 24" stroke="#111110" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </div>
      <div style={{ textAlign: 'center' }}>
        <p style={{ fontSize: '13px', color: '#111110', fontWeight: 500, letterSpacing: '0.04em' }}>처리 중</p>
        <p style={{ fontSize: '11px', color: '#9B9890', marginTop: '4px' }}>배경 제거 및 의류 합성 중입니다</p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
