const KEY = 'sps_config'
function getConfig() { return wx.getStorageSync(KEY) || {} }
function setConfig(config) { wx.setStorageSync(KEY, { ...getConfig(), ...config }) }
function getToken() { return wx.getStorageSync('sps_token') || '' }
function setToken(token) { wx.setStorageSync('sps_token', token || '') }
module.exports = { getConfig, setConfig, getToken, setToken }
