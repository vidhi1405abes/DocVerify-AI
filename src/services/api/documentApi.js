import { apiRequest } from './client'

export const getDocumentTypes = () => apiRequest('/documents/types')

export const verifyDocument = (formData) =>
  apiRequest('/documents/verify', { method: 'POST', form: formData })

export const getVerificationResult = (id) => apiRequest(`/documents/result/${encodeURIComponent(id)}`)

export const deleteVerificationResult = (id) =>
  apiRequest(`/documents/result/${encodeURIComponent(id)}`, { method: 'DELETE' })

export const getHistory = (scope) =>
  apiRequest(`/documents/history${scope === 'all' ? '?scope=all' : ''}`)

export const getReferenceDocuments = () => apiRequest('/documents/references')

export const uploadReferenceDocument = (formData) =>
  apiRequest('/documents/references', { method: 'POST', form: formData })

export const deleteReferenceDocument = (documentType, filename) =>
  apiRequest(
    `/documents/references/${encodeURIComponent(documentType)}/${encodeURIComponent(filename)}`,
    { method: 'DELETE' }
  )

export const getRecords = () => apiRequest('/records')

export const createRecord = (record) => apiRequest('/records', { method: 'POST', json: record })

export const importRecords = (formData) =>
  apiRequest('/records/import', { method: 'POST', form: formData })

export const deleteRecord = (id) => apiRequest(`/records/${id}`, { method: 'DELETE' })
