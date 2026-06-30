/**
 * Staff NFC tag read/write page.
 *
 * NO mock button. NO demo reads. All operations use real NFC or manual input.
 */
const authService = require('../../services/auth-service')
const nfc = require('../../services/nfc-service')

function makePayloadText(payload) {
  return JSON.stringify(payload, null, 2)
}

Page({
  data: {
    available: null,
    payload: {
      type: 'SPS_SMART_TAG',
      payload_version: 1,
      station_id: '',
      tag_id: 'TAG001',
      tag_nfc_id: 'NFC_TAG_001'
    },
    summaryText: '',
    resultText: '',
    devOpen: false,
    devPayload: ''
  },

  onLoad() {
    const session = authService.requireRole('staff')
    if (session && session.stationId) {
      this.setData({ 'payload.station_id': session.stationId })
    }
    this.refreshText()
    this.setData({ available: nfc.checkNfcAvailable() })
  },

  refreshText() {
    const p = this.data.payload
    this.setData({
      summaryText: `站点 ${p.station_id || '?'} · 标签 ${p.tag_id} · NFC ${p.tag_nfc_id}`,
      devPayload: makePayloadText(p)
    })
  },

  input(e) {
    this.setData({
      [`payload.${e.currentTarget.dataset.key}`]: e.detail.value
    }, () => this.refreshText())
  },

  read() {
    nfc.readTag().then(res => {
      if (res.ok) {
        this.setData({
          resultText: `已读取标签 ${res.parsed.tag_id}`
        })
        wx.showToast({ title: '读取成功', icon: 'success' })
      } else {
        this.setData({ resultText: res.reason || '读取失败' })
        wx.showToast({ title: '读取失败', icon: 'none' })
      }
    })
  },

  write() {
    wx.showModal({
      title: '确认写入',
      content: this.data.summaryText,
      success: (m) => {
        if (m.confirm) {
          nfc.writeTag(this.data.payload).then(res => {
            this.setData({ resultText: res.ok ? '写入完成' : res.reason })
            wx.showToast({
              title: res.ok ? '写入完成' : '暂不支持写入',
              icon: res.ok ? 'success' : 'none'
            })
          })
        }
      }
    })
  },

  toggleDev() {
    this.setData({ devOpen: !this.data.devOpen })
  }
})
