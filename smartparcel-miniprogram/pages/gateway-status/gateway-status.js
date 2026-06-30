/**
 * Gateway Status page — real status only.
 *
 * Shows:
 *   - serverOnline
 *   - gatewayReachable
 *   - bindingStatus
 *   - gatewayCode
 *   - stationId
 *   - gatewayBaseUrl
 *   - localSessionValid
 *   - lastCheckedAt
 *
 * NO demo mode. Clear statuses for every condition.
 */
const gatewayApi = require('../../services/gateway-api')
const serverApi = require('../../services/server-api')
const authService = require('../../services/auth-service')
const { nowText } = require('../../utils/format')
const {
  getLocalGatewaySession,
  isLocalGatewaySessionValid,
  clearLocalGatewaySession
} = require('../../services/local-session-service')

Page({
  data: {
    serverOnline: false,
    gatewayReachable: false,
    bindingStatus: 'UNKNOWN',
    gatewayCode: '',
    stationId: '',
    gatewayBaseUrl: '',
    localSessionValid: false,
    lastCheckedAt: '',
    loading: false,
    error: ''
  },

  onLoad() {
    authService.requireRole('staff')
    this.refreshAll()
  },

  onShow() {
    this.refreshAll()
  },

  refreshAll() {
    const session = getLocalGatewaySession()
    this.setData({
      localSessionValid: isLocalGatewaySessionValid(),
      gatewayCode: (session && session.gatewayCode) || '',
      stationId: (session && session.stationId) || '',
      gatewayBaseUrl: (session && session.gatewayBaseUrl) || '',
      bindingStatus: session ? 'BOUND' : 'UNBOUND'
    })
    this.checkAll()
  },

  checkAll() {
    this.setData({ loading: true, error: '' })

    Promise.all([
      serverApi.getServerHealth(),
      gatewayApi.getLocalHealth()
    ]).then(([server, gateway]) => {
      this.setData({
        serverOnline: server.ok,
        gatewayReachable: gateway.ok,
        lastCheckedAt: nowText(),
        loading: false,
        error: ''
      })
    }).catch(() => {
      this.setData({
        loading: false,
        error: '状态检查失败',
        lastCheckedAt: nowText()
      })
    })
  },

  checkServer() {
    this.setData({ loading: true })
    serverApi.getServerHealth().then((res) => {
      this.setData({
        serverOnline: res.ok,
        loading: false,
        lastCheckedAt: nowText()
      })
    }).catch(() => {
      this.setData({ serverOnline: false, loading: false })
    })
  },

  checkGateway() {
    this.setData({ loading: true })
    gatewayApi.getLocalHealth().then((res) => {
      this.setData({
        gatewayReachable: res.ok,
        loading: false,
        lastCheckedAt: nowText()
      })
    }).catch(() => {
      this.setData({ gatewayReachable: false, loading: false })
    })
  },

  goRegister() {
    wx.navigateTo({ url: '/pages/staff-gateway-register/staff-gateway-register' })
  },

  clearLocalAuth() {
    wx.showModal({
      title: '清除本地网关授权',
      content: '这将清除本地存储的网关会话。清除后需要重新完成网关注册流程才能使用 BLE 标签管理等功能。',
      success: (m) => {
        if (m.confirm) {
          clearLocalGatewaySession()
          this.setData({
            localSessionValid: false,
            gatewayCode: '',
            stationId: '',
            gatewayBaseUrl: '',
            bindingStatus: 'UNBOUND'
          })
          wx.showToast({ title: '已清除本地授权', icon: 'success' })
        }
      }
    })
  }
})
