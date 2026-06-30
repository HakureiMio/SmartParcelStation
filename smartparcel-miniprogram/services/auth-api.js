/**
 * Authentication API — real server calls only.
 *
 * NO mock accounts. NO demo login. NO fallback to fake data.
 * If the server is unreachable the caller receives { ok: false, error: ... }.
 */
const CONFIG = require('./config')
const { request } = require('./request')

/**
 * Login — calls POST /auth/login.
 *
 * @param {object} payload  { role, username, password }
 * @returns {Promise<object>}  { ok, statusCode, data: { token, role, user_id, display_name, station_id, expires_at } }
 */
function login(payload) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/auth/login',
    method: 'POST',
    data: payload
  })
}

/**
 * Register — calls POST /auth/register.
 * Currently a placeholder; server returns not-implemented until ready.
 *
 * @param {object} payload
 * @returns {Promise<object>}
 */
function register(payload) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/auth/register',
    method: 'POST',
    data: payload
  })
}

/**
 * Forgot password — calls POST /auth/forgot-password.
 *
 * @param {object} payload
 * @returns {Promise<object>}
 */
function forgotPassword(payload) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/auth/forgot-password',
    method: 'POST',
    data: payload
  })
}

module.exports = { login, register, forgotPassword }
