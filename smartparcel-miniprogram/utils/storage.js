const KEY = 'sps_config'
function getConfig() { return wx.getStorageSync(KEY) || {} }
function setConfig(config) {
  const safe = { ...(config || {}) }
  ;['gateway_secret', 'GATEWAY_SECRET', 'reader_token', 'GATE_READER_TOKEN', 'ADMIN_BOOTSTRAP_TOKEN', 'server_secret', 'database_password'].forEach((key) => delete safe[key])
  wx.setStorageSync(KEY, { ...getConfig(), ...safe })
}
function getToken() { return wx.getStorageSync('sps_token') || '' }
function setToken(token) { wx.setStorageSync('sps_token', token || '') }
module.exports = { getConfig, setConfig, getToken, setToken }
