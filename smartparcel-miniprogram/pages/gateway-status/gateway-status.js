const gatewayApi = require('../../services/gateway-api')
const serverApi = require('../../services/server-api')
const { nowText } = require('../../utils/format')
Page({ data:{ gatewayOnline:false, serverOnline:false, mode:'演示模式', checkedAt:'' }, onLoad(){ this.check() }, check(){ Promise.all([gatewayApi.getLocalHealth(), serverApi.getHealth()]).then(([g,s])=>{ const gatewayOnline = g.source === 'real'; const serverOnline = s.source === 'real'; const mode = gatewayOnline ? '本地网关可用' : (serverOnline ? '服务器可用' : '演示模式'); this.setData({gatewayOnline, serverOnline, mode, checkedAt:nowText()}); wx.showToast({ title:'检查完成', icon:'success' }) }) } })
