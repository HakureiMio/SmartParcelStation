const gatewayApi = require('../../services/gateway-api')
const authService = require('../../services/auth-service')

Page({
  data:{ displayName:'', gateway:'未连接' },
  onLoad(){
    const session=authService.requireRole('staff')
    if(!session) return
    this.setData({displayName:session.displayName || '员工'})
    this.check()
  },
  check(){
    gatewayApi.getLocalHealth().then(res=>this.setData({gateway:res.source === 'real' ? '网关连接正常' : '演示模式'}))
  },
  go(e){ wx.navigateTo({url:`/pages/${e.currentTarget.dataset.page}/${e.currentTarget.dataset.page}`}) },
  logout(){ authService.clearSession(); wx.reLaunch({ url:'/pages/index/index' }) }
})
