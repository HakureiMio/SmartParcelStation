const CONFIG = require('./config')
const MOCK_TAG = { type:'SPS_SMART_TAG', payload_version:1, station_id:'1', tag_id:'TAG001', tag_nfc_id:'NFC_TAG_001' }
function checkNfcAvailable() {
  if (typeof wx === 'undefined') return { available:false, reason:'非小程序环境' }
  if (!wx.getNFCAdapter) return { available:false, reason:'当前基础库未提供 NFC 能力' }
  return { available:true, reason:'检测到 NFC Adapter' }
}
function readTag() {
  const available = checkNfcAvailable()
  if (!available.available) return Promise.resolve(CONFIG.enableNfcMock ? mockReadTag() : { ok:false, reason:available.reason })
  return Promise.resolve(CONFIG.enableNfcMock ? mockReadTag() : { ok:false, reason:'真实 NFC 读取需在真机与权限环境中接入回调' })
}
function writeTag(payload) {
  const available = checkNfcAvailable()
  if (!available.available) return Promise.resolve({ ok:false, reason:'当前设备或小程序环境不支持 NFC 写入，请使用手动写入/外部 NFC 工具/预写标签。', payload })
  return Promise.resolve({ ok:false, reason:'NFC 写入能力依赖真机与标签类型，本原型保留 payload 预览与读取验证。', payload })
}
function parseTagPayload(raw) {
  if (!raw) return { ok:false, reason:'内容为空' }
  try { return { ok:true, parsed: typeof raw === 'string' ? JSON.parse(raw) : raw } } catch (err) {}
  if (typeof raw === 'string' && raw.indexOf('sps://tag?') === 0) {
    const parsed = { type:'SPS_SMART_TAG', payload_version:1 }
    ;(raw.split('?')[1] || '').split('&').forEach((pair) => { const [key, value] = pair.split('='); if (key) parsed[key] = decodeURIComponent(value || '') })
    return { ok:true, parsed }
  }
  return { ok:false, reason:'无法解析 NFC 标签内容' }
}
function mockReadTag() { const raw = JSON.stringify(MOCK_TAG); return { ok:true, raw, parsed:MOCK_TAG, source:'mock' } }
module.exports = { checkNfcAvailable, readTag, writeTag, parseTagPayload, mockReadTag }
