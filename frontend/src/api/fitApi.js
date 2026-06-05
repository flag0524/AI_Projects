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

// 생성형 모델 컷 (Leffa try-on)
export async function submitGenerate({ garments, modelTemplateFile, mannequinFile }) {
  const formData = new FormData()
  garments.forEach(({ file, type }) => {
    formData.append('garment_images', file)
    formData.append('garment_types', type)
  })
  if (modelTemplateFile) formData.append('model_template_image', modelTemplateFile)
  if (mannequinFile) formData.append('mannequin_image', mannequinFile)

  const res = await axios.post('/api/v1/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 240000, // 생성은 최대 4분
  })
  return res.data
}

// 생성형 백엔드 상태
export async function fetchGenerateStatus() {
  const res = await axios.get('/api/v1/generate/status')
  return res.data
}
