const KEYS = {
  token: 'sps_token',
  role: 'sps_role',
  userId: 'sps_user_id',
  displayName: 'sps_display_name',
  stationId: 'sps_station_id'
}

function saveSession(session) {
  wx.setStorageSync(KEYS.token, session.token || '')
  wx.setStorageSync(KEYS.role, session.role || '')
  wx.setStorageSync(KEYS.userId, session.user_id || session.userId || '')
  wx.setStorageSync(KEYS.displayName, session.display_name || session.displayName || '')
  wx.setStorageSync(KEYS.stationId, session.station_id || session.stationId || '')
}

function getSession() {
  return {
    token: wx.getStorageSync(KEYS.token) || '',
    role: wx.getStorageSync(KEYS.role) || '',
    userId: wx.getStorageSync(KEYS.userId) || '',
    displayName: wx.getStorageSync(KEYS.displayName) || '',
    stationId: wx.getStorageSync(KEYS.stationId) || ''
  }
}

function clearSession() {
  Object.keys(KEYS).forEach((key) => wx.removeStorageSync(KEYS[key]))
}

function isLoggedIn() {
  const session = getSession()
  return Boolean(session.token && session.role && session.userId)
}

function requireRole(role) {
  const session = getSession()
  if (!session.token || session.role !== role) {
    wx.redirectTo({ url: `/pages/login/login?role=${role}` })
    return null
  }
  return session
}

module.exports = { saveSession, getSession, clearSession, requireRole, isLoggedIn }
