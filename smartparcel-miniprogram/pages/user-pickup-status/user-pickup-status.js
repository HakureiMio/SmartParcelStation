const CONFIG = require('../../services/config')
const serverApi = require('../../services/server-api')
const { PICKUP_STEPS } = require('../../utils/constants')
Page({ data:{ steps:PICKUP_STEPS, status:{}, shelvesText:'', source:'mock' }, onLoad(){ serverApi.getPickupStatus(CONFIG.demoUserId).then(res=>{ const hint=(res.data||{}).gateway_hint || {}; this.setData({status:res.data||{}, shelvesText:hint.shelves ? hint.shelves.join(' / ') : '', source:res.source}) }) } })
