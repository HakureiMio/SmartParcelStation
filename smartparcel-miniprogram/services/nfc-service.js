/**
 * NFC service — real NFC operations only.
 *
 * NO mock tag data. NO demo reads. NO fallback to fake tag payloads.
 *
 * When real NFC hardware is not available, readTag / writeTag return
 * { ok: false, reason: '...' } with a clear explanation.
 *
 * Pages should offer a "manual input" alternative when NFC is unavailable.
 */
const CONFIG = require('./config')

/**
 * Check whether the current device / base library supports NFC.
 */
function checkNfcAvailable() {
  if (typeof wx === 'undefined') {
    return { available: false, reason: '非小程序环境' }
  }
  if (!wx.getNFCAdapter) {
    return { available: false, reason: '当前基础库未提供 NFC 能力' }
  }
  return { available: true, reason: '检测到 NFC Adapter' }
}

/**
 * Read an NFC tag.
 *
 * Currently returns a clear "not yet integrated" message because real
 * NFC reading requires an on-device test environment with permission
 * callbacks.  This is NOT a mock — it returns { ok: false }.
 */
function readTag() {
  const available = checkNfcAvailable()
  if (!available.available) return Promise.resolve({ ok: false, reason: available.reason })
  return new Promise((resolve) => {
    const adapter = wx.getNFCAdapter()
    const ndef = adapter.getNdef ? adapter.getNdef() : null
    if (!ndef || !ndef.onNdefMessage) {
      resolve({ ok: false, reason: '当前环境无法读取 NFC，请使用真机或手动输入 NFC payload。' })
      return
    }
    let done = false
    const finish = (value) => { if (!done) { done = true; resolve(value) } }
    ndef.onNdefMessage((message) => {
      const record = (message.message || [])[0] || {}
      const raw = ndefRecordToText(record)
      const parsed = parseSpsPayload(raw)
      finish(parsed.ok ? { ok: true, raw, parsed: parsed.parsed } : parsed)
    })
    adapter.startDiscovery({ fail: (err) => finish({ ok: false, reason: err.errMsg || 'NFC 读取启动失败' }) })
    setTimeout(() => finish({ ok: false, reason: 'NFC 读取超时，请重试或手动输入 payload。' }), 15000)
  })
}

function arrayBufferToUtf8(buffer) {
  if (!buffer) return ''
  const bytes = new Uint8Array(buffer)
  let encoded = ''
  bytes.forEach((byte) => { encoded += `%${byte.toString(16).padStart(2, '0')}` })
  try { return decodeURIComponent(encoded) } catch (_) { return String.fromCharCode.apply(null, bytes) }
}

function ndefRecordToText(record) {
  const bytes = new Uint8Array(record.payload || new ArrayBuffer(0))
  const type = arrayBufferToUtf8(record.type || new ArrayBuffer(0))
  let offset = 0
  if (type === 'T' && bytes.length) offset = 1 + (bytes[0] & 0x3f)
  if (type === 'U' && bytes.length && bytes[0] === 0) offset = 1
  return arrayBufferToUtf8(bytes.slice(offset).buffer)
}

function parseQueryUri(raw, prefix, type) {
  if (typeof raw !== 'string' || raw.indexOf(prefix) !== 0) return null
  const parsed = { type }
  ;(raw.split('?')[1] || '').split('&').forEach((pair) => {
    const index = pair.indexOf('=')
    const key = index >= 0 ? pair.slice(0, index) : pair
    const value = index >= 0 ? pair.slice(index + 1) : ''
    if (key) parsed[decodeURIComponent(key)] = decodeURIComponent(value)
  })
  return parsed
}

function parseSpsPayload(raw) {
  if (!raw) return { ok: false, reason: 'payload 为空' }
  if (typeof raw !== 'string') return { ok: true, parsed: raw }
  if (/^https:\/\//i.test(raw.trim())) {
    return {
      ok: false,
      reason: '检测到 HTTPS/微信 URL Link 标签。请直接用手机系统触碰标签打开小程序，或将标签改写为 sps://gate-nfc 演示格式。'
    }
  }
  try { return { ok: true, parsed: JSON.parse(raw) } } catch (_) {}
  const parsed = parseQueryUri(raw, 'sps://gate-qr?', 'SPS_GATE_QR') ||
    parseQueryUri(raw, 'sps://gate-nfc?', 'SPS_GATE_NFC') ||
    parseQueryUri(raw, 'sps://pickup?', 'SPS_PICKUP_TAG') ||
    parseQueryUri(raw, 'sps://tag?', 'SPS_SMART_TAG')
  return parsed ? { ok: true, parsed } : { ok: false, reason: '无法解析 SPS payload' }
}

/**
 * Write an NFC tag.
 *
 * Also returns a clear "not yet integrated" message.
 */
function writeTag(payload) {
  const available = checkNfcAvailable()
  if (!available.available) {
    return Promise.resolve({
      ok: false,
      reason: '当前设备或小程序环境不支持 NFC 写入，请使用手动写入或外部 NFC 工具。',
      payload
    })
  }
  return Promise.resolve({
    ok: false,
    reason: 'NFC 写入能力依赖真机与标签类型，当前尚未接入真实写入流程。',
    payload
  })
}

/**
 * Parse a raw NFC payload string (JSON or sps://tag? URI format).
 */
function parseTagPayload(raw) {
  const modern = parseSpsPayload(raw)
  if (modern.ok) return modern
  if (!raw) return { ok: false, reason: '内容为空' }
  try {
    return { ok: true, parsed: typeof raw === 'string' ? JSON.parse(raw) : raw }
  } catch (_) { /* not JSON, try URI */ }

  if (typeof raw === 'string' && raw.indexOf('sps://tag?') === 0) {
    const parsed = { type: 'SPS_SMART_TAG', payload_version: 1 }
    ;(raw.split('?')[1] || '').split('&').forEach((pair) => {
      const [key, value] = pair.split('=')
      if (key) parsed[key] = decodeURIComponent(value || '')
    })
    return { ok: true, parsed }
  }

  return { ok: false, reason: '无法解析 NFC 标签内容' }
}

module.exports = { checkNfcAvailable, readTag, writeTag, parseTagPayload, parseSpsPayload, arrayBufferToUtf8, ndefRecordToText }
