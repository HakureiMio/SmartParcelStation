const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')

Page({
  data: { parcels: [] },
  onLoad() {
    const session = authService.requireRole('client')
    if (!session) return
    serverApi.getUserParcels(session.userId).then((res) => {
      const parcels = (res.data || []).map((item) => ({
        ...item,
        statusText: item.status === 'PICKED_UP' ? '已取件' : '待取件',
        colorName: item.tag_color || '未分配'
      }))
      this.setData({ parcels })
    })
  }
})
