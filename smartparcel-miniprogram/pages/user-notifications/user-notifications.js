const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')
Page({ data:{ notifications:[] }, onLoad(){ const session=authService.requireRole('client'); if(!session) return; serverApi.getUserNotifications(session.userId).then(res=>this.setData({notifications:res.data||[]})) } })
