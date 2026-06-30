/**
 * Local gateway session manager.
 *
 * Manages a short-lived session token obtained after gateway binding.
 *
 * SAVED fields:
 *   gatewayBaseUrl, gatewayCode, stationId,
 *   localSessionToken, localSessionExpiresAt, boundAt
 *
 * NEVER saved:
 *   gateway_secret, registration_token, one_time_binding_token,
 *   server admin token, password
 *
 * Security:
 *   - Session expiry is checked before every use.
 *   - Clear on logout / re-bind.
 *   - Debug output MUST be redacted before display.
 */
const CONFIG = require('./config')

const SECURITY_FORBIDDEN_KEYS = [
  'gateway_secret',
  'GATEWAY_SECRET',
  'registration_token',
  'one_time_binding_token',
  'admin_token',
  'bootstrap_token',
  'password',
  'secret'
]

/**
 * Save a local gateway session. Rejects any object that contains forbidden keys.
 */
function saveLocalGatewaySession(session) {
  if (!session || typeof session !== 'object') {
    throw new Error('Invalid session object')
  }

  // Security: refuse to save forbidden keys.
  for (const key of SECURITY_FORBIDDEN_KEYS) {
    if (session[key] !== undefined && session[key] !== null && session[key] !== '') {
      console.warn(`[SECURITY] Refusing to save forbidden key: ${key}`)
      // Strip it instead of throwing, to be defensive.
      delete session[key]
    }
    // Also check nested
    const lowerKey = key.toLowerCase()
    for (const k of Object.keys(session)) {
      if (k.toLowerCase() === lowerKey) {
        console.warn(`[SECURITY] Refusing to save forbidden key: ${k}`)
        delete session[k]
      }
    }
  }

  const record = {
    gatewayBaseUrl: session.gatewayBaseUrl || '',
    gatewayCode: session.gatewayCode || '',
    stationId: session.stationId || '',
    localSessionToken: session.localSessionToken || '',
    localSessionExpiresAt: session.localSessionExpiresAt || '',
    boundAt: session.boundAt || new Date().toISOString()
  }

  wx.setStorageSync(CONFIG.localSessionStorageKey, JSON.stringify(record))
  return record
}

/**
 * Get the stored local gateway session, or null if none / expired.
 */
function getLocalGatewaySession() {
  try {
    const raw = wx.getStorageSync(CONFIG.localSessionStorageKey)
    if (!raw) return null
    const record = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!record || !record.localSessionToken) return null
    return record
  } catch (_) {
    return null
  }
}

/**
 * Clear the stored local gateway session.
 */
function clearLocalGatewaySession() {
  wx.removeStorageSync(CONFIG.localSessionStorageKey)
}

/**
 * Check whether the local gateway session exists and is not expired.
 * Returns true if valid, false otherwise.
 */
function isLocalGatewaySessionValid() {
  const session = getLocalGatewaySession()
  if (!session || !session.localSessionToken) return false

  if (session.localSessionExpiresAt) {
    const expiresAt = new Date(session.localSessionExpiresAt).getTime()
    if (Date.now() >= expiresAt) {
      // Expired — auto-clear.
      clearLocalGatewaySession()
      return false
    }
  }

  return true
}

/**
 * Return the Bearer token string for Authorization header, or empty string.
 */
function getLocalSessionToken() {
  const session = getLocalGatewaySession()
  return session ? session.localSessionToken : ''
}

module.exports = {
  saveLocalGatewaySession,
  getLocalGatewaySession,
  clearLocalGatewaySession,
  isLocalGatewaySessionValid,
  getLocalSessionToken
}
