const CONFIG = require('../../services/config')
Page({ data: { CONFIG }, go(e) { const page = e.currentTarget.dataset.page; wx.navigateTo({ url: `/pages/${page}/${page}` }) } })
