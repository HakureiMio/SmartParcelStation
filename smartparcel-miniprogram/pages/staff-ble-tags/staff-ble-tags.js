const gatewayApi = require('../../services/gateway-api')
const authService = require('../../services/auth-service')

function unwrap(res){
  return res && res.data ? res.data : res
}

function messageFrom(res, fallback){
  if (!res) return fallback
  if (res.source === 'mock') return `${fallback}（演示）`
  return fallback
}

Page({
  data:{
    gatewayState:'检查中',
    gatewaySource:'mock',
    scanning:false,
    loading:false,
    scanItems:[],
    tags:[],
    selectedTag:null,
    detailOpen:false,
    debugOpen:false,
    debugText:''
  },
  onLoad(){
    authService.requireRole('staff')
    this.refreshAll()
  },
  refreshAll(){
    this.checkGateway()
    this.loadTags()
  },
  checkGateway(){
    gatewayApi.getLocalHealth().then(res=>{
      this.setData({
        gatewayState:res.source === 'real' ? '网关在线' : '演示模式',
        gatewaySource:res.source || 'mock'
      })
    })
  },
  loadTags(){
    gatewayApi.listLocalTags().then(res=>{
      const data = unwrap(res)
      this.setData({ tags:data.items || [] })
    })
  },
  scan(){
    this.setData({ scanning:true })
    gatewayApi.scanBleTags({ timeout_sec:5 }).then(res=>{
      const data = unwrap(res)
      this.setData({
        scanItems:data.items || [],
        debugText:JSON.stringify(data, null, 2)
      })
      wx.showToast({ title:messageFrom(res, '扫描完成'), icon:'success' })
    }).finally(()=>this.setData({ scanning:false }))
  },
  register(e){
    const index = e.currentTarget.dataset.index
    const item = this.data.scanItems[index]
    if (!item) return
    this.setData({ loading:true })
    gatewayApi.registerTagFromBle({ ble_name:item.ble_name, ble_address:item.ble_address }).then(res=>{
      const data = unwrap(res)
      this.setData({ selectedTag:data.item || null, detailOpen:true, debugText:JSON.stringify(data, null, 2) })
      this.loadTags()
      wx.showToast({ title:messageFrom(res, '注册成功'), icon:'success' })
    }).finally(()=>this.setData({ loading:false }))
  },
  selectTag(e){
    const tagId = e.currentTarget.dataset.id
    gatewayApi.getLocalTag(tagId).then(res=>{
      const data = unwrap(res)
      this.setData({ selectedTag:data.item, detailOpen:true, debugText:JSON.stringify(data, null, 2) })
    })
  },
  connect(){ this.runAction('connectLocalTag', '连接完成') },
  wake(){ this.runAction('wakeLocalTag', '已发送亮灯蜂鸣', { color:'BLUE', duration_sec:30 }) },
  stop(){ this.runAction('stopLocalTag', '已停止') },
  readStatus(){ this.runAction('readLocalTagStatus', '状态已读取') },
  runAction(method, toastTitle, payload){
    const tag = this.data.selectedTag
    if (!tag) return
    this.setData({ loading:true })
    gatewayApi[method](tag.tag_id, payload).then(res=>{
      const data = unwrap(res)
      this.setData({ selectedTag:data.item || tag, debugText:JSON.stringify(data, null, 2) })
      this.loadTags()
      wx.showToast({ title:messageFrom(res, toastTitle), icon:'success' })
    }).finally(()=>this.setData({ loading:false }))
  },
  toggleDebug(){ this.setData({ debugOpen:!this.data.debugOpen }) }
})
