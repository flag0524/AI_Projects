import { useRef, useState } from 'react'

const GARMENT_TYPES = [
  { value: 'top', label: '상의' },
  { value: 'bottom', label: '하의' },
  { value: 'dress', label: '원피스' },
  { value: 'accessory', label: '액세서리' },
]

function ImageDropZone({ label, onFile, preview, accept = 'image/*' }) {
  const inputRef = useRef()
  const [dragging, setDragging] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onFile(file)
  }

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors
        ${dragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400 bg-gray-50'}`}
      onClick={() => inputRef.current.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => e.target.files[0] && onFile(e.target.files[0])}
      />
      {preview ? (
        <img src={preview} alt={label} className="mx-auto max-h-40 object-contain rounded-lg" />
      ) : (
        <div className="py-6">
          <div className="text-3xl mb-2">📁</div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-xs text-gray-400 mt-1">클릭 또는 드래그&드롭</p>
        </div>
      )}
    </div>
  )
}

export default function UploadPanel({ onSubmit, loading }) {
  const [mannequinFile, setMannequinFile] = useState(null)
  const [mannequinPreview, setMannequinPreview] = useState(null)
  const [garments, setGarments] = useState([])

  const handleMannequin = (file) => {
    setMannequinFile(file)
    setMannequinPreview(URL.createObjectURL(file))
  }

  const addGarment = () => {
    setGarments((prev) => [...prev, { file: null, preview: null, type: 'top', id: Date.now() }])
  }

  const updateGarment = (id, updates) => {
    setGarments((prev) => prev.map((g) => (g.id === id ? { ...g, ...updates } : g)))
  }

  const removeGarment = (id) => {
    setGarments((prev) => prev.filter((g) => g.id !== id))
  }

  const handleGarmentFile = (id, file) => {
    updateGarment(id, { file, preview: URL.createObjectURL(file) })
  }

  const canSubmit = mannequinFile && garments.length > 0 && garments.every((g) => g.file)

  const handleSubmit = () => {
    if (!canSubmit) return
    onSubmit({ mannequinFile, garments: garments.map(({ file, type }) => ({ file, type })) })
  }

  return (
    <div className="flex flex-col gap-5">
      {/* 마네킹 업로드 */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">마네킹 이미지</h2>
        <ImageDropZone
          label="마네킹 이미지를 업로드하세요"
          onFile={handleMannequin}
          preview={mannequinPreview}
        />
      </div>

      {/* 의류 업로드 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-700">의류 이미지</h2>
          <button
            onClick={addGarment}
            className="text-xs bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full hover:bg-indigo-200 transition-colors"
          >
            + 추가
          </button>
        </div>

        {garments.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4 border border-dashed border-gray-200 rounded-xl">
            의류 추가 버튼을 눌러 시작하세요
          </p>
        )}

        <div className="flex flex-col gap-3">
          {garments.map((g) => (
            <div key={g.id} className="border border-gray-200 rounded-xl p-3 bg-white">
              <div className="flex items-center justify-between mb-2">
                <select
                  value={g.type}
                  onChange={(e) => updateGarment(g.id, { type: e.target.value })}
                  className="text-xs border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                >
                  {GARMENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <button
                  onClick={() => removeGarment(g.id)}
                  className="text-xs text-red-400 hover:text-red-600"
                >
                  삭제
                </button>
              </div>
              <ImageDropZone
                label={`${GARMENT_TYPES.find((t) => t.value === g.type)?.label} 이미지`}
                onFile={(file) => handleGarmentFile(g.id, file)}
                preview={g.preview}
              />
            </div>
          ))}
        </div>
      </div>

      {/* 제출 버튼 */}
      <button
        onClick={handleSubmit}
        disabled={!canSubmit || loading}
        className={`w-full py-3 rounded-xl font-semibold text-white transition-all
          ${canSubmit && !loading
            ? 'bg-indigo-600 hover:bg-indigo-700 shadow-md hover:shadow-lg'
            : 'bg-gray-300 cursor-not-allowed'}`}
      >
        {loading ? '처리 중...' : '피팅 시작'}
      </button>
    </div>
  )
}
