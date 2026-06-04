import axios from 'axios'

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
