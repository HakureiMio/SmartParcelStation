Page({
  goLogin(e) {
    const role = e.currentTarget.dataset.role
    wx.navigateTo({ url: `/pages/login/login?role=${role}` })
  }
})
