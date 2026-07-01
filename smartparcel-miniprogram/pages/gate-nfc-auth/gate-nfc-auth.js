const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')
const nfc = require('../../services/nfc-service')

const PENDING_GATE_NFC_AUTH_KEY = 'pending_gate_nfc_auth'

function hasGateNfcOptions(options) {
  const value = options || {}
  return ['gateway_code', 'reader_id', 'station_id', 'gate_nfc_tag_id']
    .every((key) => Boolean(value[key]))
}

Page({
  data: { raw: '', statusText: '请将手机贴近门禁 NFC 标签', submitting: false },
  onLoad(options) {
    this.autoSubmitting = false
    this.autoSubmitted = false
    if (hasGateNfcOptions(options)) {
      wx.setStorageSync(PENDING_GATE_NFC_AUTH_KEY, options)
      this.setData({ statusText: '已读取门禁标签，正在检查登录状态…' })
    }
    const session = authService.requireRole('client')
    if (session && hasGateNfcOptions(options)) this.submitOptions(options)
  },
  onShow() {
    if (this.autoSubmitting || this.autoSubmitted) return
    const session = authService.getSession()
    const pending = wx.getStorageSync(PENDING_GATE_NFC_AUTH_KEY)
    if (session.token && session.role === 'client' && hasGateNfcOptions(pending)) {
      this.submitOptions(pending)
    }
  },
  read() { nfc.readTag().then((res) => { if (res.ok) this.submitParsed(res.parsed); else this.setData({ statusText: res.reason }) }) },
  input(e) { this.setData({ raw: e.detail.value }) },
  submitInput() { const result = nfc.parseSpsPayload(this.data.raw); if (!result.ok) { this.setData({ statusText: result.reason }); return } this.submitParsed(result.parsed) },
  hasGateNfcOptions,
  submitOptions(options) {
    if (!hasGateNfcOptions(options) || this.autoSubmitting || this.autoSubmitted) return
    this.autoSubmitting = true
    this.setData({ submitting: true, statusText: '正在提交认证…' })
    serverApi.gateNfcConfirm({
      auth_method: 'GATE_NFC_TAG',
      gateway_code: options.gateway_code,
      reader_id: options.reader_id,
      station_id: Number(options.station_id),
      gate_nfc_tag_id: options.gate_nfc_tag_id
    }).then((res) => {
      const ok = res.ok && (!res.data || res.data.ok !== false)
      this.autoSubmitting = false
      this.autoSubmitted = ok
      if (ok) wx.removeStorageSync(PENDING_GATE_NFC_AUTH_KEY)
      this.setData({ submitting: false, statusText: ok ? '认证已提交，请查看门禁屏幕' : ((res.data || {}).detail || res.error || '认证提交失败') })
    }).catch(() => {
      this.autoSubmitting = false
      this.setData({ submitting: false, statusText: '认证提交失败，请稍后重试' })
    })
  },
  submitParsed(p) {
    if (p.type !== 'SPS_GATE_NFC' || !p.gateway_code || !p.reader_id || !p.station_id || !p.gate_nfc_tag_id) { this.setData({ statusText: '门禁 NFC payload 格式无效' }); return }
    this.setData({ submitting: true, statusText: '正在提交认证…' })
    serverApi.gateNfcConfirm({ auth_method: 'GATE_NFC_TAG', gateway_code: p.gateway_code, reader_id: p.reader_id,
      station_id: Number(p.station_id), gate_nfc_tag_id: p.gate_nfc_tag_id }).then((res) => {
      const ok = res.ok && (!res.data || res.data.ok !== false)
      this.setData({ submitting: false, statusText: ok ? '认证已提交，请查看门禁屏幕' : ((res.data || {}).detail || res.error || '认证提交失败') })
    })
  }
})
