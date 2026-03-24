import CryptoJS from 'crypto-js'

// 原密钥 'ChatBI123456789' 仅15字节，CryptoJS sigBytes=15 产生非标准 AES key schedule
// PyCryptodome 无法解密。补齐到16字节确保标准 AES-128
const key = CryptoJS.enc.Utf8.parse('ChatBI1234567890')

export const encrypted = (str: string) => {
  return CryptoJS.AES.encrypt(str, key, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7,
  }).toString()
}

export const decrypted = (str: string) => {
  const bytes = CryptoJS.AES.decrypt(str, key, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7,
  })
  return bytes.toString(CryptoJS.enc.Utf8)
}
