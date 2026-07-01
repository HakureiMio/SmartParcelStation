const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')
const nfc = require('../../services/nfc-service')

Page({
  data: { raw: '', statusText: '请将手机贴近门禁 NFC 标签', submitting: false },
  onLoad() { authService.requireRole('client') },
  read() { nfc.readTag().then((res) => { if (res.ok) this.submitParsed(res.parsed); else this.setData({ statusText: res.reason }) }) },
  input(e) { this.setData({ raw: e.detail.value }) },
  submitInput() { const result = nfc.parseSpsPayload(this.data.raw); if (!result.ok) { this.setData({ statusText: result.reason }); return } this.submitParsed(result.parsed) },
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
