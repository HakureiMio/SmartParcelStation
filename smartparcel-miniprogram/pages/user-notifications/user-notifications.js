const CONFIG = require('../../services/config')
const serverApi = require('../../services/server-api')
Page({ data:{ notifications:[], source:'mock' }, onLoad(){ serverApi.getUserNotifications(CONFIG.demoUserId).then(res=>this.setData({notifications:res.data||[], source:res.source})) } })
