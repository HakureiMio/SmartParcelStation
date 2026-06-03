const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')
Page({ data:{ parcels:[] }, onLoad(){ const session=authService.requireRole('client'); if(!session) return; serverApi.getUserParcels(session.userId).then(res=>this.setData({parcels:res.data||[]})) } })
