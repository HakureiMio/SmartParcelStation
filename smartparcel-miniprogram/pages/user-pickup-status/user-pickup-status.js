const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')
const { PICKUP_STEPS } = require('../../utils/constants')
Page({ data:{ steps:PICKUP_STEPS, status:{}, shelvesText:'' }, onLoad(){ const session=authService.requireRole('client'); if(!session) return; serverApi.getPickupStatus(session.userId).then(res=>{ const hint=(res.data||{}).gateway_hint || {}; this.setData({status:res.data||{}, shelvesText:hint.shelves ? hint.shelves.join('、') : ''}) }) } })
