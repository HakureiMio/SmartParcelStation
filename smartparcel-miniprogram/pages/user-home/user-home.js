const serverApi = require('../../services/server-api')
const authService = require('../../services/auth-service')

function normalizeColorName(parcel, hint) {
  if (hint && hint.color_display_name) return hint.color_display_name
  return parcel.tag_color || '未分配'
}

function colorClass(colorName) {
  if (!colorName) return 'gray'
  if (colorName.indexOf('绿') >= 0) return 'green'
  if (colorName.indexOf('橙') >= 0 || colorName.indexOf('黄') >= 0) return 'orange'
  if (colorName.indexOf('蓝') >= 0) return ''
  return 'gray'
}

function statusText(status) {
  const map = { WAITING_PICKUP: '待取件', ARRIVED_AT_STATION: '已到站', PICKUP_VERIFYING: '待确认', PICKED_UP: '已取件' }
  return map[status] || '待取件'
}

Page({
  data:{ userId:'', parcels:[], filteredParcels:[], hint:null, searchText:'', shelvesText:'' },
  goGate(){ wx.navigateTo({ url:'/pages/gate-auth/gate-auth' }) },
  goCards(){ wx.navigateTo({ url:'/pages/user-card-manage/user-card-manage' }) },
  goParcels(){ wx.navigateTo({ url:'/pages/user-parcels/user-parcels' }) },
  onLoad(){ const session = authService.requireRole('client'); if (!session) return; this.setData({ userId:session.userId }); this.loadParcels() },
  loadParcels(){ Promise.all([serverApi.getUserParcels(this.data.userId), serverApi.getPickupStatus(this.data.userId)]).then(([p,s])=>{ const hint=(s.data||{}).gateway_hint || null; const parcels=(p.data||[]).map((item)=>{ const colorName=normalizeColorName(item, hint); return { ...item, colorName, colorClass: colorClass(colorName), statusText: statusText(item.status) } }); this.setData({ parcels, filteredParcels:parcels, hint, shelvesText: hint && hint.shelves ? hint.shelves.join('、') : '' }) }) },
  onSearch(e){ const text=e.detail.value.trim(); const lower=text.toLowerCase(); const filtered=this.data.parcels.filter((item)=>!lower || item.parcel_code.toLowerCase().indexOf(lower)>=0 || String(item.shelf_code || '').toLowerCase().indexOf(lower)>=0); this.setData({ searchText:text, filteredParcels:filtered }) },
  goNfc(e){ const code=e.currentTarget.dataset.code || ''; wx.navigateTo({ url:`/pages/user-nfc-fast-pickup/user-nfc-fast-pickup?parcelCode=${code}` }) }
})
