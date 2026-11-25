export const acceptFor = (type) =>
  type?.formats?.length === 1 && type.formats[0] === '.pdf'
    ? '.pdf,application/pdf'
    : 'image/png,image/jpeg,.pdf,application/pdf'

export const formatsLabel = (type) =>
  type?.formats?.map((format) => format.slice(1).toUpperCase()).filter((f) => f !== 'JPEG').join(' / ')

export const isAllowedFile = (type, file) => {
  const extension = `.${file.name.split('.').pop().toLowerCase()}`
  return Boolean(type?.formats?.includes(extension))
}
