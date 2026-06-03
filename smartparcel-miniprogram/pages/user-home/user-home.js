const CONFIG = require('../../services/config')
const serverApi = require('../../services/server-api')
const gatewayApi = require('../../services/gateway-api')
Page({
  data:{ userId:CONFIG.demoUserId, stationId:CONFIG.stationId, parcels:[], noticeCount:0, hint:null, shelvesText:'', source:'mock' },
  onLoad(){ this.refresh() },
  refresh(){ Promise.all([serverApi.getUserParcels(this.data.userId), serverApi.getUserNotifications(this.data.userId), serverApi.getPickupStatus(this.data.userId)]).then(([p,n,s])=>{ const hint=(s.data||{}).gateway_hint; this.setData({ parcels:p.data||[], noticeCount:(n.data||[]).length, hint, shelvesText: hint && hint.shelves ? hint.shelves.join(' / ') : '', source:p.source }) }) },
  readGateway(){ gatewayApi.gateAccessCard({reader_id:'MINI_USER', credential_type:'CARD_UID', credential_value:'CARD_UID_001'}).then((res)=>{ const hint=res.data; this.setData({hint, shelvesText:hint.shelves ? hint.shelves.join(' / ') : '', source:res.source}) }) },
  go(e){ const page=e.currentTarget.dataset.page; wx.navigateTo({url:`/pages/${page}/${page}`}) }
})
