const serverApi = require('../../services/server-api')
const gatewayApi = require('../../services/gateway-api')
const authService = require('../../services/auth-service')

Page({
  data:{ userId:'', displayName:'', stationId:'', parcels:[], noticeCount:0, hint:null, shelvesText:'', updatedText:'' },
  onLoad(){ const session = authService.requireRole('client'); if (!session) return; this.setData({ userId:session.userId, displayName:session.displayName || '用户', stationId:session.stationId || '1' }); this.refresh() },
  refresh(){ Promise.all([serverApi.getUserParcels(this.data.userId), serverApi.getUserNotifications(this.data.userId), serverApi.getPickupStatus(this.data.userId)]).then(([p,n,s])=>{ const hint=(s.data||{}).gateway_hint; this.setData({ parcels:p.data||[], noticeCount:(n.data||[]).length, hint, shelvesText: hint && hint.shelves ? hint.shelves.join('、') : '', updatedText:'数据已更新' }); wx.showToast({ title:'更新成功', icon:'success' }) }) },
  readGateway(){ gatewayApi.gateAccessCard({reader_id:'MINI_USER', credential_type:'CARD_UID', credential_value:'CARD_UID_001'}).then((res)=>{ const hint=res.data; this.setData({hint, shelvesText:hint.shelves ? hint.shelves.join('、') : '', updatedText:'已获取取件提示'}); wx.showToast({ title:'提示已更新', icon:'success' }) }) },
  go(e){ const page=e.currentTarget.dataset.page; wx.navigateTo({url:`/pages/${page}/${page}`}) },
  logout(){ authService.clearSession(); wx.reLaunch({ url:'/pages/index/index' }) }
})
