Page({
  goLogin(e) {
    wx.navigateTo({ url: `/pages/login/login?role=${e.currentTarget.dataset.role}` })
  }
})
