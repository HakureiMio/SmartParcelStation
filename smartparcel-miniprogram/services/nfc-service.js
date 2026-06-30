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
  if (!available.available) {
    return Promise.resolve({ ok: false, reason: available.reason })
  }
  return Promise.resolve({
    ok: false,
    reason: '真实 NFC 读取尚未接入，请使用真机 NFC 能力或手动输入标签信息'
  })
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

module.exports = { checkNfcAvailable, readTag, writeTag, parseTagPayload }
