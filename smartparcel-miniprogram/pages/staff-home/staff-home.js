/**
 * Staff home — employee workbench.
 *
 * Shows gateway binding status and navigation cards.
 * NO demo mode display. All state is derived from real session / health checks.
 */
const gatewayApi = require('../../services/gateway-api')
const serverApi = require('../../services/server-api')
const authService = require('../../services/auth-service')
const { isLocalGatewaySessionValid } = require('../../services/local-session-service')

Page({
  data: {
    displayName: '',
    gatewayStatus: '检查中',
    gatewayStatusClass: '',
    serverOnline: false,
    gatewayReachable: false,
    localSessionValid: false
  },

  onLoad() {
    const session = authService.requireRole('staff')
    if (!session) return
    this.setData({ displayName: session.displayName || '员工' })
    this.refreshStatus()
  },

  onShow() {
    this.refreshStatus()
  },

  refreshStatus() {
    const sessionValid = isLocalGatewaySessionValid()
    this.setData({ localSessionValid: sessionValid })

    // Check server health
    serverApi.getServerHealth().then((res) => {
      this.setData({ serverOnline: res.ok })
    })

    // Check gateway health
    gatewayApi.getLocalHealth().then((res) => {
      const reachable = res.ok
      this.setData({ gatewayReachable: reachable })
      this._updateGatewayStatus(sessionValid, reachable)
    }).catch(() => {
      this.setData({ gatewayReachable: false })
      this._updateGatewayStatus(sessionValid, false)
    })
  },

  _updateGatewayStatus(sessionValid, reachable) {
    if (!sessionValid) {
      this.setData({
        gatewayStatus: '未绑定 / 未授权',
        gatewayStatusClass: 'warn'
      })
    } else if (!reachable) {
      this.setData({
        gatewayStatus: '网关离线 / 请连接站点网络',
        gatewayStatusClass: 'offline'
      })
    } else {
      this.setData({
        gatewayStatus: '运行正常',
        gatewayStatusClass: 'ok'
      })
    }
  },

  go(e) {
    const page = e.currentTarget.dataset.page
    wx.navigateTo({ url: `/pages/${page}/${page}` })
  },

  logout() {
    authService.clearSession()
    wx.reLaunch({ url: '/pages/index/index' })
  }
})
