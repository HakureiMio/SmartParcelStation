/**
 * Session manager for server authentication.
 *
 * Storage keys:
 *   sps_token        — Bearer access token
 *   sps_role         — client | staff
 *   sps_user_id      — user ID from server
 *   sps_display_name — display name
 *   sps_station_id   — primary station
 *   sps_expires_at   — token expiry ISO string
 *
 * clearSession() also clears the local gateway session.
 */
const { clearLocalGatewaySession } = require('./local-session-service')

const KEYS = {
  token: 'sps_token',
  role: 'sps_role',
  userId: 'sps_user_id',
  displayName: 'sps_display_name',
  stationId: 'sps_station_id',
  expiresAt: 'sps_expires_at'
}

/**
 * Persist server session.
 *
 * @param {object} session  { token, role, user_id, userId, display_name, displayName, station_id, stationId, expires_at, expiresAt }
 */
function saveSession(session) {
  wx.setStorageSync(KEYS.token, session.token || '')
  wx.setStorageSync(KEYS.role, session.role || '')
  wx.setStorageSync(KEYS.userId, session.user_id || session.userId || '')
  wx.setStorageSync(KEYS.displayName, session.display_name || session.displayName || '')
  wx.setStorageSync(KEYS.stationId, session.station_id || session.stationId || '')
  wx.setStorageSync(KEYS.expiresAt, session.expires_at || session.expiresAt || '')
}

/**
 * Read the current server session from storage.
 */
function getSession() {
  return {
    token: wx.getStorageSync(KEYS.token) || '',
    role: wx.getStorageSync(KEYS.role) || '',
    userId: wx.getStorageSync(KEYS.userId) || '',
    displayName: wx.getStorageSync(KEYS.displayName) || '',
    stationId: wx.getStorageSync(KEYS.stationId) || '',
    expiresAt: wx.getStorageSync(KEYS.expiresAt) || ''
  }
}

/**
 * Clear server session AND local gateway session.
 */
function clearSession() {
  Object.keys(KEYS).forEach((key) => wx.removeStorageSync(KEYS[key]))
  clearLocalGatewaySession()
}

/**
 * True if a token, role, and userId are present.
 */
function isLoggedIn() {
  const session = getSession()
  return Boolean(session.token && session.role && session.userId)
}

/**
 * Return the Bearer Authorization header value.
 */
function getAuthHeader() {
  const session = getSession()
  return session.token ? `Bearer ${session.token}` : ''
}

/**
 * Guard: redirect to login if the session is missing or the role doesn't match.
 * Returns the session object or null.
 *
 * Role mapping:
 *   'staff'  — employee (maps to server role 'staff')
 *   'client' — parcel recipient (maps to server role 'client')
 */
function requireRole(role) {
  const session = getSession()
  if (!session.token || session.role !== role) {
    wx.redirectTo({ url: `/pages/login/login?role=${role}` })
    return null
  }

  // Check expiry
  if (session.expiresAt) {
    const expiresAt = new Date(session.expiresAt).getTime()
    if (Date.now() >= expiresAt) {
      clearSession()
      wx.redirectTo({ url: `/pages/login/login?role=${role}` })
      return null
    }
  }

  return session
}

module.exports = {
  saveSession,
  getSession,
  clearSession,
  isLoggedIn,
  requireRole,
  getAuthHeader
}
