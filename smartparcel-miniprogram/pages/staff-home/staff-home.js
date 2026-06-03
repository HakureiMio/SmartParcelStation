const CONFIG = require('../../services/config')
const gatewayApi = require('../../services/gateway-api')
const authService = require('../../services/auth-service')
Page({ data:{ displayName:'', stationId:'1', gateway:'未连接' }, onLoad(){ const session=authService.requireRole('staff'); if(!session) return; this.setData({displayName:session.displayName || '员工', stationId:session.stationId || CONFIG.stationId}); this.check() }, check(){ gatewayApi.getLocalHealth().then(res=>this.setData({gateway:res.source === 'real' ? '在线' : '演示模式'})) }, go(e){ const page=e.currentTarget.dataset.page; wx.navigateTo({url:`/pages/${page}/${page}`}) }, logout(){ authService.clearSession(); wx.reLaunch({ url:'/pages/index/index' }) } })
