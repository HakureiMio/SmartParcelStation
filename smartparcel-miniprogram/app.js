App({
  globalData: { token: '', stationId: '1', gatewayReachable: false },
  onLaunch() {
    const stored = wx.getStorageSync('sps_config') || {}
    this.globalData.stationId = stored.stationId || '1'
  }
})
