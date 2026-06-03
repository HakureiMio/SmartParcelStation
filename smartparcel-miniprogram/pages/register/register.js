const authApi = require('../../services/auth-api')
Page({ data:{ role:'client' }, onLoad(options){ this.setData({ role: options.role || 'client' }) }, submit(){ authApi.register({ role:this.data.role }).then((res)=>{ wx.showModal({ title:'功能预留', content:(res.data && res.data.message) || '注册功能暂未开放', showCancel:false }) }) } })
