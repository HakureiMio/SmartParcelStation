const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')
const nfc = require('../../services/nfc-service')

Page({
  data: { raw: '', statusText: '请扫描门禁屏幕二维码', submitting: false },
  onLoad() { authService.requireRole('client') },
  scan() {
    wx.scanCode({ onlyFromCamera: true, success: (res) => this.submitRaw(res.result || res.path || ''), fail: (err) => this.setData({ statusText: err.errMsg || '扫码已取消' }) })
  },
  input(e) { this.setData({ raw: e.detail.value }) },
  submitInput() { this.submitRaw(this.data.raw) },
  submitRaw(raw) {
    const result = nfc.parseSpsPayload(raw)
    const p = result.parsed || {}
    const required = ['gateway_code', 'reader_id', 'station_id', 'session_id', 'nonce', 'expires_at', 'signature']
    if (!result.ok || p.type !== 'SPS_GATE_QR' || required.some((key) => !p[key])) { this.setData({ statusText: '二维码格式无效' }); return }
    if (Number(p.expires_at) <= Math.floor(Date.now() / 1000)) { this.setData({ statusText: '二维码已过期，请刷新门禁屏幕' }); return }
    this.setData({ submitting: true, statusText: '正在提交认证…' })
    serverApi.gateQrConfirm({ auth_method: 'GATE_QR', gateway_code: p.gateway_code, reader_id: p.reader_id,
      station_id: Number(p.station_id), session_id: p.session_id, nonce: p.nonce,
      expires_at: Number(p.expires_at), signature: p.signature }).then((res) => {
      const ok = res.ok && (!res.data || res.data.ok !== false)
      this.setData({ submitting: false, statusText: ok ? '认证已提交，请查看门禁屏幕' : ((res.data || {}).detail || res.error || '认证提交失败') })
    })
  }
})
