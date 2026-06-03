const CONFIG = require('../../services/config')
const serverApi = require('../../services/server-api')
Page({ data:{ parcels:[], source:'mock' }, onLoad(){ this.load() }, load(){ serverApi.getUserParcels(CONFIG.demoUserId).then(res=>this.setData({parcels:res.data||[], source:res.source})) } })
