const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')

Page({
  data: { parcels: [], confirmingId: null },
  onLoad() {
    const session = authService.requireRole('client')
    if (!session) return
    this.loadParcels()
  },
  loadParcels() {
    return serverApi.getMyParcels().then((res) => {
      const source = res.ok && Array.isArray(res.data) ? res.data : []
      if (!res.ok) wx.showToast({ title: (res.data || {}).detail || '包裹加载失败', icon: 'none' })
      const parcels = source.map((item) => ({
        ...item,
        statusText: item.status === 'PICKED_UP' ? '已取件' : '待取件',
        colorName: item.tag_color || '未分配'
      }))
      this.setData({ parcels })
    })
  },
  confirmPickup(e) {
    const parcelId = Number(e.currentTarget.dataset.id)
    if (!parcelId || this.data.confirmingId) return
    this.setData({ confirmingId: parcelId })
    serverApi.manualConfirmPickup({ parcel_id: parcelId, confirm_method: 'MANUAL_BUTTON' }).then((res) => {
      this.setData({ confirmingId: null })
      if (res.ok) { wx.showToast({ title: '取件已确认', icon: 'success' }); this.loadParcels() }
      else wx.showToast({ title: (res.data || {}).detail || '确认失败', icon: 'none' })
    })
  }
})
