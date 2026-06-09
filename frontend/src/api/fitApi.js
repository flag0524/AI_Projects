import axios from 'axios'

// 절차적 합성 (마네킹 위에 의류 와핑)
export async function submitFitting({ mannequinFile, garments }) {
  const formData = new FormData()
  formData.append('mannequin_image', mannequinFile)
  garments.forEach(({ file, type }) => {
    formData.append('garment_images', file)
    formData.append('garment_types', type)
  })

  const res = await axios.post('/api/v1/fit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

// 생성형 착용 컷 (Leffa/Higgsfield try-on) — 비동기 job: 제출 후 결과 폴링
// subject: 'model'(실제 모델) | 'mannequin'(마네킹 디스플레이)
export async function submitGenerate({ garments, modelTemplateFile, mannequinFile, subject = 'model' }) {
  const formData = new FormData()
  garments.forEach(({ file, type }) => {
    formData.append('garment_images', file)
    formData.append('garment_types', type)
  })
  if (modelTemplateFile) formData.append('model_template_image', modelTemplateFile)
  if (mannequinFile) formData.append('mannequin_image', mannequinFile)
  formData.append('subject', subject)

  // 1) 제출 → 202 { job_id }
  const submit = await axios.post('/api/v1/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  // 2) 완료까지 결과 폴링 (402/500은 axios 예외로 전파 → 호출부가 detail 처리)
  return pollGenerateResult(submit.data.job_id)
}

// 고정 간격 폴링: status==="completed"면 결과 반환, 상한 초과 시 타임아웃
async function pollGenerateResult(jobId, { intervalMs = 3000, maxAttempts = 80 } = {}) {
  for (let i = 0; i < maxAttempts; i++) {
    const res = await axios.get(`/api/v1/generate/result/${jobId}`)
    if (res.data.status === 'completed') return res.data
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error('생성 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.')
}

// 생성형 백엔드 상태
export async function fetchGenerateStatus() {
  const res = await axios.get('/api/v1/generate/status')
  return res.data
}
