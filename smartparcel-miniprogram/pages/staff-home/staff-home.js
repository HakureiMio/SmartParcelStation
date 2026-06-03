const CONFIG = require('../../services/config')
const gatewayApi = require('../../services/gateway-api')
Page({ data:{ staffId:CONFIG.demoStaffId, stationId:CONFIG.stationId, gateway:'未检查', source:'mock' }, onLoad(){ this.check() }, check(){ gatewayApi.getLocalHealth().then(res=>this.setData({gateway:res.ok ? '可达' : '不可达', source:res.source})) }, go(e){ const page=e.currentTarget.dataset.page; wx.navigateTo({url:`/pages/${page}/${page}`}) } })
