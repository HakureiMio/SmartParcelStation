/**
 * BLE Tag Management page.
 *
 * All gateway operations require a valid local session token.
 * If the session is missing or expired the page shows a prompt to
 * complete gateway registration first.
 *
 * NO mock data. NO mock toast. NO MOCK:TAG addresses.
 * All errors are real connectivity / auth / BLE errors.
 */
const gatewayApi = require('../../services/gateway-api')
const authService = require('../../services/auth-service')
const {
  isLocalGatewaySessionValid
} = require('../../services/local-session-service')
const { redactSensitive } = require('../../services/security-utils')

function unwrap(res) {
  return res && res.data ? res.data : res
}

/**
 * Return human-readable source description.
 * Only uses '真实网关', '未授权', '网关离线', 'BLE 不可用'.
 */
function sourceText(source) {
  if (source === 'real') return '真实网关'
  if (source === 'unauthorized') return '未授权'
  if (source === 'offline') return '网关离线'
  if (source === 'ble_unavailable') return 'BLE 不可用'
  return '未知'
}

Page({
  data: {
    localSessionValid: false,
    gatewayState: '检查中',
    gatewaySource: '',
    gatewaySourceText: '未知',
    lastError: '',
    scanning: false,
    loading: false,
    scanItems: [],
    tags: [],
    selectedTag: null,
    detailOpen: false,
    debugOpen: false,
    debugText: ''
  },

  onLoad() {
    authService.requireRole('staff')
    this.checkAuthAndRefresh()
  },

  onShow() {
    this.checkAuthAndRefresh()
  },

  checkAuthAndRefresh() {
    const valid = isLocalGatewaySessionValid()
    this.setData({ localSessionValid: valid })
    if (valid) {
      this.refreshAll()
    } else {
      this.setData({
        gatewayState: '未授权 — 请先完成网关注册',
        gatewaySource: 'unauthorized',
        gatewaySourceText: '未授权',
        tags: [],
        scanItems: []
      })
    }
  },

  refreshAll() {
    this.checkGateway()
    this.loadTags()
  },

  setDebug(res) {
    // SECURITY: redact sensitive fields before showing debug output.
    this.setData({
      debugText: JSON.stringify(redactSensitive(res), null, 2)
    })
  },

  markError(message, res) {
    this.setData({ lastError: message || '请求失败' })
    if (res) this.setDebug(res)
  },

  checkGateway() {
    gatewayApi.getLocalHealth().then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (res.ok) {
        this.setData({
          gatewayState: '网关在线',
          gatewaySource: 'real',
          gatewaySourceText: sourceText('real'),
          lastError: ''
        })
      } else if (res.error === 'LOCAL_SESSION_MISSING') {
        this.setData({
          gatewayState: '未授权',
          gatewaySource: 'unauthorized',
          gatewaySourceText: sourceText('unauthorized'),
          lastError: '本地会话缺失或已过期'
        })
      } else {
        this.setData({
          gatewayState: '网关离线',
          gatewaySource: 'offline',
          gatewaySourceText: sourceText('offline'),
          lastError: res.error || data.reason || 'local API 请求失败'
        })
      }
    }).catch(err => {
      this.setData({
        gatewayState: '网关不可达',
        gatewaySource: 'offline',
        gatewaySourceText: sourceText('offline'),
        lastError: (err && err.message) || '网络错误'
      })
    })
  },

  loadTags() {
    gatewayApi.listLocalTags().then(res => {
      const data = unwrap(res)
      if (!res.ok) {
        this.setData({
          tags: [],
          lastError: res.error === 'LOCAL_SESSION_MISSING'
            ? '请先完成网关注册 / 授权'
            : (res.error || data.detail || '标签列表读取失败')
        })
        this.setDebug(res)
        return
      }
      this.setData({
        tags: data.items || [],
        gatewaySource: 'real',
        gatewaySourceText: sourceText('real')
      })
      this.setDebug(res)
    }).catch(err => {
      this.setData({
        tags: [],
        lastError: (err && err.message) || '请求异常'
      })
    })
  },

  scan() {
    this.setData({ scanning: true, lastError: '' })
    gatewayApi.scanBleTags({ timeout_sec: 5 }).then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (!res.ok) {
        const errorMsg = res.error === 'LOCAL_SESSION_MISSING'
          ? '请先完成网关注册 / 授权'
          : (res.error || data.detail || '扫描失败')
        this.setData({ scanItems: [], lastError: errorMsg })
        wx.showToast({ title: '扫描失败', icon: 'error' })
      } else {
        this.setData({
          scanItems: data.items || [],
          gatewaySource: 'real',
          gatewaySourceText: sourceText('real')
        })
        wx.showToast({ title: '扫描完成', icon: 'success' })
      }
      this.setData({ scanning: false })
    }).catch(err => {
      this.setData({
        scanning: false,
        lastError: (err && err.message) || '扫描异常'
      })
    })
  },

  register(e) {
    const index = e.currentTarget.dataset.index
    const item = this.data.scanItems[index]
    if (!item) return
    this.setData({ loading: true, lastError: '' })
    gatewayApi.registerTagFromBle({
      ble_name: item.ble_name,
      ble_address: item.ble_address
    }).then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (!res.ok) {
        this.setData({
          lastError: res.error === 'LOCAL_SESSION_MISSING'
            ? '请先完成网关注册 / 授权'
            : (res.error || data.detail || '注册失败')
        })
        wx.showToast({ title: '注册失败', icon: 'error' })
      } else {
        this.setData({ selectedTag: data.item || null, detailOpen: true })
        this.loadTags()
        wx.showToast({ title: '注册成功', icon: 'success' })
      }
      this.setData({ loading: false })
    }).catch(err => {
      this.setData({
        loading: false,
        lastError: (err && err.message) || '注册异常'
      })
    })
  },

  selectTag(e) {
    const tagId = e.currentTarget.dataset.id
    gatewayApi.getLocalTag(tagId).then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (!res.ok) {
        this.setData({
          lastError: res.error === 'LOCAL_SESSION_MISSING'
            ? '请先完成网关注册 / 授权'
            : (res.error || data.detail || '详情读取失败')
        })
        return
      }
      this.setData({ selectedTag: data.item, detailOpen: true, lastError: '' })
    })
  },

  connect() { this.runAction('connectLocalTag', '连接完成') },
  wake() { this.runAction('wakeLocalTag', '已发送亮灯/蜂鸣', { color: 'BLUE', duration_sec: 30 }) },
  stop() { this.runAction('stopLocalTag', '已停止') },
  readStatus() { this.runAction('readLocalTagStatus', '状态已读取') },

  runAction(method, toastTitle, payload) {
    const tag = this.data.selectedTag
    if (!tag || this.data.loading) return
    this.setData({ loading: true, lastError: '' })
    gatewayApi[method](tag.tag_id, payload).then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (!res.ok) {
        const errorMsg = res.error === 'LOCAL_SESSION_MISSING'
          ? '请先完成网关注册 / 授权'
          : (res.error || data.detail || '操作失败')
        this.setData({ lastError: errorMsg })
        wx.showToast({ title: '操作失败', icon: 'error' })
      } else {
        const result = data.result || {}
        if (result.ok === false) {
          this.setData({
            selectedTag: data.item || tag,
            lastError: result.message || result.error || 'BLE 操作失败'
          })
          wx.showToast({ title: 'BLE 失败', icon: 'error' })
        } else {
          this.setData({ selectedTag: data.item || tag })
          wx.showToast({ title: toastTitle, icon: 'success' })
        }
        this.loadTags()
      }
      this.setData({ loading: false })
    }).catch(err => {
      this.setData({
        loading: false,
        lastError: (err && err.message) || '操作异常'
      })
    })
  },

  goRegister() {
    wx.navigateTo({ url: '/pages/staff-gateway-register/staff-gateway-register' })
  },

  toggleDebug() {
    this.setData({ debugOpen: !this.data.debugOpen })
  }
})
