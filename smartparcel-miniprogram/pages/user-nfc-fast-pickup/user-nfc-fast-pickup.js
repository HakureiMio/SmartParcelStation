const authService = require('../../services/auth-service')
const nfc = require('../../services/nfc-service')
const serverApi = require('../../services/server-api')
Page({
  data: { session: null, raw: '', parsed: null, tagText: '尚未读取包裹标签', resultText: '', submitting: false },
  onLoad() { const session = authService.requireRole('client'); if (session) this.setData({ session }) },
  read() { nfc.readTag().then((res) => { if (res.ok) this.setData({ raw: res.raw, parsed: res.parsed, tagText: `已读取标签 ${res.parsed.tag_id || ''}` }); else this.setData({ tagText: res.reason }) }) },
  input(e) { const raw = e.detail.value; const result = nfc.parseSpsPayload(raw); this.setData({ raw, parsed: result.ok ? result.parsed : null, tagText: result.ok ? `已识别标签 ${result.parsed.tag_id || ''}` : result.reason }) },
  confirmServer() {
    const p = this.data.parsed || {}; const binding = p.pickup_binding_id || p.binding; const token = p.encrypted_token || p.token
    if (!p.tag_id || !binding || !token) { wx.showToast({ title: '标签 payload 不完整', icon: 'none' }); return }
    this.setData({ submitting: true })
    serverApi.nfcConfirmPickup({ event_id: `mp_nfc_${Date.now()}`, tag_id: p.tag_id, pickup_binding_id: binding, encrypted_token: token }).then((res) => {
      const ok = res.ok && (!res.data || res.data.ok !== false)
      this.setData({ submitting: false, resultText: ok ? '取件已确认' : ((res.data || {}).detail || res.error || '确认失败') })
      wx.showToast({ title: ok ? '取件已确认' : '确认失败', icon: ok ? 'success' : 'none' })
    })
  }
})
