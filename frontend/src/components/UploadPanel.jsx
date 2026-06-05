import { useRef, useState } from 'react'
import { UploadIcon, PlusIcon, TrashIcon, ImageIcon } from './Icons.jsx'

const GARMENT_TYPES = [
  { value: 'top',       label: '상의' },
  { value: 'bottom',    label: '하의' },
  { value: 'dress',     label: '원피스' },
  { value: 'accessory', label: '액세서리' },
]

const s = {
  label: {
    fontSize: '10px',
    fontWeight: 500,
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    color: 'var(--text-2)',
    marginBottom: '8px',
    display: 'block',
  },
  dropzone: (active, hasFile) => ({
    border: `1px dashed ${active ? 'var(--text-1)' : hasFile ? 'var(--border)' : 'var(--border-2)'}`,
    borderRadius: 'var(--radius)',
    background: active ? '#F0EFEc' : hasFile ? 'var(--surface)' : 'transparent',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    overflow: 'hidden',
    position: 'relative',
  }),
}

function DropZone({ label, onFile, preview, compact = false }) {
  const inputRef = useRef()
  const [dragging, setDragging] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }

  return (
    <div
      style={s.dropzone(dragging, !!preview)}
      onClick={() => inputRef.current.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef} type="file" accept="image/*"
        style={{ display: 'none' }}
        onChange={(e) => e.target.files[0] && onFile(e.target.files[0])}
      />
      {preview ? (
        <div style={{ position: 'relative' }}>
          <img
            src={preview} alt={label}
            style={{
              width: '100%',
              height: compact ? '120px' : '200px',
              objectFit: 'contain',
              display: 'block',
              background: '#F7F6F3',
            }}
          />
          <div style={{
            position: 'absolute', inset: 0,
            background: 'rgba(0,0,0,0)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: 0, transition: 'opacity 0.15s',
          }}
            onMouseEnter={e => e.currentTarget.style.opacity = 1}
            onMouseLeave={e => e.currentTarget.style.opacity = 0}
          >
            <div style={{
              background: 'rgba(17,17,16,0.75)',
              color: '#fff',
              fontSize: '11px',
              letterSpacing: '0.06em',
              padding: '6px 12px',
              borderRadius: '2px',
            }}>변경하기</div>
          </div>
        </div>
      ) : (
        <div style={{
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: '10px',
          padding: compact ? '20px 16px' : '36px 16px',
          color: 'var(--text-3)',
        }}>
          <ImageIcon size={compact ? 24 : 28} />
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: '12px', color: 'var(--text-2)', fontWeight: 400 }}>{label}</p>
            <p style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '2px' }}>클릭 또는 드래그</p>
          </div>
        </div>
      )}
    </div>
  )
}

function GarmentRow({ garment, onTypeChange, onFile, onRemove }) {
  return (
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      background: 'var(--surface)',
      overflow: 'hidden',
    }}>
      {/* 타입 선택 탭 */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border)',
        background: '#FAFAF8',
      }}>
        {GARMENT_TYPES.map(t => (
          <button
            key={t.value}
            onClick={() => onTypeChange(t.value)}
            style={{
              flex: 1,
              padding: '8px 4px',
              fontSize: '11px',
              fontWeight: garment.type === t.value ? 500 : 400,
              color: garment.type === t.value ? 'var(--text-1)' : 'var(--text-3)',
              background: garment.type === t.value ? 'var(--surface)' : 'transparent',
              border: 'none',
              borderBottom: garment.type === t.value ? '1.5px solid var(--text-1)' : '1.5px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.12s',
              letterSpacing: '0.02em',
            }}
          >{t.label}</button>
        ))}
        <button
          onClick={onRemove}
          style={{
            padding: '8px 10px',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-3)',
            display: 'flex', alignItems: 'center',
            borderLeft: '1px solid var(--border)',
          }}
        ><TrashIcon /></button>
      </div>
      {/* 드롭존 */}
      <div style={{ padding: '8px' }}>
        <DropZone
          label={`${GARMENT_TYPES.find(t => t.value === garment.type)?.label} 이미지`}
          onFile={onFile}
          preview={garment.preview}
          compact
        />
      </div>
    </div>
  )
}

export default function UploadPanel({ onSubmit, loading, mode = 'generate' }) {
  const isGenerate = mode === 'generate'

  const [mannequinFile, setMannequinFile] = useState(null)
  const [mannequinPreview, setMannequinPreview] = useState(null)
  const [templateFile, setTemplateFile] = useState(null)
  const [templatePreview, setTemplatePreview] = useState(null)
  const [garments, setGarments] = useState([])

  const handleMannequin = (f) => {
    setMannequinFile(f)
    setMannequinPreview(URL.createObjectURL(f))
  }
  const handleTemplate = (f) => {
    setTemplateFile(f)
    setTemplatePreview(URL.createObjectURL(f))
  }

  const addGarment = () => setGarments(p => [...p, { id: Date.now(), file: null, preview: null, type: 'top' }])
  const updateGarment = (id, upd) => setGarments(p => p.map(g => g.id === id ? { ...g, ...upd } : g))
  const removeGarment = (id) => setGarments(p => p.filter(g => g.id !== id))
  const handleGarmentFile = (id, f) => updateGarment(id, { file: f, preview: URL.createObjectURL(f) })

  // 생성 모드: 마네킹 불필요(모델 템플릿 선택). 피팅 모드: 마네킹 필수.
  const garmentsReady = garments.length > 0 && garments.every(g => g.file)
  const canSubmit = isGenerate ? garmentsReady : (mannequinFile && garmentsReady)

  const handleClick = () => {
    if (!canSubmit || loading) return
    const garmentList = garments.map(({ file, type }) => ({ file, type }))
    if (isGenerate) {
      onSubmit({ garments: garmentList, modelTemplateFile: templateFile, mannequinFile })
    } else {
      onSubmit({ mannequinFile, garments: garmentList })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', height: '100%' }}>

      {/* 피팅 모드: 마네킹(필수) / 생성 모드: 모델 템플릿(선택) */}
      {isGenerate ? (
        <div>
          <span style={s.label}>모델 템플릿 <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>(선택)</span></span>
          <DropZone
            label="모델 사진 (미선택 시 기본 모델)"
            onFile={handleTemplate}
            preview={templatePreview}
            compact
          />
        </div>
      ) : (
        <div>
          <span style={s.label}>마네킹</span>
          <DropZone
            label="마네킹 이미지를 올려주세요"
            onFile={handleMannequin}
            preview={mannequinPreview}
          />
        </div>
      )}

      {/* 구분선 */}
      <div style={{ borderTop: '1px solid var(--border)' }} />

      {/* 의류 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={s.label}>의류</span>
          <button
            onClick={addGarment}
            style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              padding: '5px 10px',
              fontSize: '11px',
              fontWeight: 500,
              color: 'var(--text-1)',
              background: 'transparent',
              border: '1px solid var(--border-2)',
              borderRadius: 'var(--radius)',
              cursor: 'pointer',
              letterSpacing: '0.04em',
              transition: 'border-color 0.12s',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--text-1)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-2)'}
          >
            <PlusIcon /> 추가
          </button>
        </div>

        {garments.length === 0 ? (
          <div style={{
            border: '1px dashed var(--border)',
            borderRadius: 'var(--radius)',
            padding: '24px',
            textAlign: 'center',
            color: 'var(--text-3)',
            fontSize: '12px',
          }}>
            의류를 추가하세요
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {garments.map(g => (
              <GarmentRow
                key={g.id}
                garment={g}
                onTypeChange={type => updateGarment(g.id, { type })}
                onFile={f => handleGarmentFile(g.id, f)}
                onRemove={() => removeGarment(g.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* 실행 버튼 */}
      <button
        onClick={handleClick}
        disabled={!canSubmit || loading}
        style={{
          width: '100%',
          padding: '13px',
          fontSize: '12px',
          fontWeight: 500,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: canSubmit && !loading ? 'var(--accent-fg)' : 'var(--text-3)',
          background: canSubmit && !loading ? 'var(--accent)' : 'var(--border)',
          border: 'none',
          borderRadius: 'var(--radius)',
          cursor: canSubmit && !loading ? 'pointer' : 'not-allowed',
          transition: 'background 0.15s, opacity 0.15s',
        }}
        onMouseEnter={e => { if (canSubmit && !loading) e.currentTarget.style.background = '#333' }}
        onMouseLeave={e => { if (canSubmit && !loading) e.currentTarget.style.background = 'var(--accent)' }}
      >
        {loading ? '처리 중...' : isGenerate ? '모델 컷 생성' : '피팅 시작'}
      </button>
    </div>
  )
}
