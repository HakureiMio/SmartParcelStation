const gatewayApi = require('../../services/gateway-api')
const authService = require('../../services/auth-service')

function unwrap(res) {
  return res && res.data ? res.data : res
}

function sourceText(source) {
  if (source === 'real') return '真实网关'
  if (source === 'mock') return 'Mock 演示'
  return '错误'
}

function showResultToast(res, title) {
  if (!res || res.ok === false) {
    wx.showToast({ title: '请求失败', icon: 'error' })
    return
  }
  wx.showToast({ title, icon: res.source === 'mock' ? 'none' : 'success' })
}

Page({
  data: {
    gatewayState: '检查中',
    gatewaySource: 'error',
    gatewaySourceText: '错误',
    lastError: '',
    scanning: false,
    loading: false,
    scanItems: [],
    tags: [],
    selectedTag: null,
    detailOpen: false,
    debugOpen: true,
    debugText: ''
  },

  onLoad() {
    authService.requireRole('staff')
    this.refreshAll()
  },

  refreshAll() {
    this.checkGateway()
    this.loadTags()
  },

  setDebug(res) {
    this.setData({ debugText: JSON.stringify(res, null, 2) })
  },

  markError(message, res) {
    this.setData({ lastError: message || '请求失败' })
    if (res) this.setDebug(res)
  },

  checkGateway() {
    gatewayApi.getLocalHealth().then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      this.setData({
        gatewayState: res.ok && res.source === 'real' ? '网关在线' : '网关不可用',
        gatewaySource: res.source || 'error',
        gatewaySourceText: sourceText(res.source),
        lastError: res.ok ? '' : (res.error || data.reason || 'local API 请求失败')
      })
    })
  },

  loadTags() {
    gatewayApi.listLocalTags().then(res => {
      const data = unwrap(res)
      if (!res.ok || !data.ok) {
        this.setData({ tags: [], lastError: res.error || data.detail || '标签列表读取失败' })
        this.setDebug(res)
        return
      }
      this.setData({
        tags: data.items || [],
        gatewaySource: res.source || this.data.gatewaySource,
        gatewaySourceText: sourceText(res.source || this.data.gatewaySource)
      })
      this.setDebug(res)
    })
  },

  scan() {
    this.setData({ scanning: true, lastError: '' })
    gatewayApi.scanBleTags({ timeout_sec: 5 }).then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (!res.ok || !data.ok) {
        this.setData({ scanItems: [], lastError: res.error || data.detail || '扫描失败' })
        wx.showToast({ title: '扫描失败', icon: 'error' })
      } else {
        this.setData({
          scanItems: data.items || [],
          gatewaySource: res.source || 'real',
          gatewaySourceText: sourceText(res.source || 'real')
        })
        showResultToast(res, '扫描完成')
      }
      this.setData({ scanning: false })
    }).catch(err => {
      this.setData({ scanning: false, lastError: err && err.message ? err.message : '扫描异常' })
    })
  },

  register(e) {
    const index = e.currentTarget.dataset.index
    const item = this.data.scanItems[index]
    if (!item) return
    this.setData({ loading: true, lastError: '' })
    gatewayApi.registerTagFromBle({ ble_name: item.ble_name, ble_address: item.ble_address }).then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (!res.ok || !data.ok) {
        this.setData({ lastError: res.error || data.detail || '注册失败' })
        wx.showToast({ title: '注册失败', icon: 'error' })
      } else {
        this.setData({ selectedTag: data.item || null, detailOpen: true })
        this.loadTags()
        showResultToast(res, '注册成功')
      }
      this.setData({ loading: false })
    }).catch(err => {
      this.setData({ loading: false, lastError: err && err.message ? err.message : '注册异常' })
    })
  },

  selectTag(e) {
    const tagId = e.currentTarget.dataset.id
    gatewayApi.getLocalTag(tagId).then(res => {
      const data = unwrap(res)
      this.setDebug(res)
      if (!res.ok || !data.ok) {
        this.setData({ lastError: res.error || data.detail || '详情读取失败' })
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
      if (!res.ok || !data.ok) {
        this.setData({ lastError: res.error || data.detail || '操作失败' })
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
          showResultToast(res, toastTitle)
        }
        this.loadTags()
      }
      this.setData({ loading: false })
    }).catch(err => {
      this.setData({ loading: false, lastError: err && err.message ? err.message : '操作异常' })
    })
  },

  toggleDebug() {
    this.setData({ debugOpen: !this.data.debugOpen })
  }
})
