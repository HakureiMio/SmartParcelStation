const authService = require('../../services/auth-service')
Page({
  onLoad() { authService.requireRole('client') },
  goQr() { wx.navigateTo({ url: '/pages/gate-qr-auth/gate-qr-auth' }) },
  goNfc() { wx.navigateTo({ url: '/pages/gate-nfc-auth/gate-nfc-auth' }) }
})
