const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')

Page({
  data: { activeCards: [], historyCards: [], loading: false, errorText: '' },
  onLoad() { if (authService.requireRole('client')) this.loadCards() },
  onPullDownRefresh() { this.loadCards().then(() => wx.stopPullDownRefresh()) },
  loadCards() {
    this.setData({ loading: true, errorText: '' })
    return serverApi.getMyCards().then((res) => {
      if (!res.ok) {
        const unavailable = res.statusCode === 404 || res.statusCode === 405
        this.setData({ loading: false, activeCards: [], historyCards: [], errorText: unavailable ? '后端 GET /users/me/cards 接口尚未实现，无法读取卡片列表。' : ((res.data || {}).detail || res.error || '门禁卡加载失败') })
        return
      }
      const cards = Array.isArray(res.data) ? res.data : ((res.data || {}).items || [])
      this.setData({ loading: false, activeCards: cards.filter((item) => item.status === 'ACTIVE'), historyCards: cards.filter((item) => item.status !== 'ACTIVE') })
    })
  },
  reportLost(e) {
    const cardId = Number(e.currentTarget.dataset.id)
    wx.showModal({ title: '确认报失', content: '报失后该卡将不能再开门。', success: (choice) => {
      if (!choice.confirm) return
      serverApi.reportMyCardLost({ card_id: cardId, reason: '用户遗忘或丢失' }).then((res) => {
        if (res.ok) { wx.showToast({ title: '已报失', icon: 'success' }); this.loadCards() }
        else wx.showToast({ title: (res.data || {}).detail || '报失失败', icon: 'none' })
      })
    } })
  }
})
