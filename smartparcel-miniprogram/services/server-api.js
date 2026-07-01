/**
 * Server API — all calls go to the VPS backend.
 *
 * NO mock data. All requests carry the staff/client Bearer token.
 *
 * Provisioning endpoints:
 *   POST /gateways/provisioning/prepare   — request binding parameters
 *   POST /gateways/provisioning/confirm   — confirm binding completion
 *
 * Station endpoints:
 *   GET  /stations                        — list staff-accessible stations
 *
 * Registration token endpoints:
 *   POST /gateways/registration-tokens    — create a token
 *   GET  /gateways/registration-tokens    — list tokens
 *
 * Dev-mode note: If the current server still uses X-Dev-User-Id / X-Dev-Role
 * headers, they are encapsulated here and marked for removal — do NOT
 * scatter them across pages.
 */
const CONFIG = require('./config')
const { request } = require('./request')
const { getAuthHeader } = require('./auth-service')
const { isHttpsUrl } = require('./security-utils')

// ── helpers ──────────────────────────────────────────────────────────

function authHeaders(extraHeaders) {
  return { Authorization: getAuthHeader(), ...(extraHeaders || {}) }
}

/**
 * Warn if serverBaseUrl is not HTTPS.
 */
function checkServerUrl() {
  if (!isHttpsUrl(CONFIG.serverBaseUrl)) {
    if (!CONFIG.allowInsecureServerHttpInDev) {
      console.warn('[SECURITY] serverBaseUrl is not HTTPS — requests may be rejected')
      return false
    }
  }
  return true
}

// ── health ───────────────────────────────────────────────────────────

function getServerHealth() {
  checkServerUrl()
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/health'
  })
}

// ── auth (delegated to auth-api for login/register/forgot) ───────────

// ── parcels ──────────────────────────────────────────────────────────

function getUserParcels(userId) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: `/users/${userId}/parcels`,
    headers: authHeaders()
  })
}

function gateQrConfirm(payload) { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/gate/auth/qr-confirm', method: 'POST', data: payload, headers: authHeaders() }) }
function gateNfcConfirm(payload) { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/gate/auth/nfc-confirm', method: 'POST', data: payload, headers: authHeaders() }) }
function getMyCards() { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/users/me/cards', headers: authHeaders() }) }
function reportMyCardLost(payload) { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/users/me/cards/report-lost', method: 'POST', data: payload, headers: authHeaders() }) }
function getMyParcels() { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/users/me/parcels', headers: authHeaders() }) }
function manualConfirmPickup(payload) { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/pickup/manual-confirm', method: 'POST', data: payload, headers: authHeaders() }) }
function nfcConfirmPickup(payload) { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/pickup/nfc-confirm', method: 'POST', data: payload, headers: authHeaders() }) }

function getUserNotifications(userId) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: `/users/${userId}/notifications`,
    headers: authHeaders()
  })
}

function getPickupStatus(userId) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: `/users/${userId}/pickup-status`,
    headers: authHeaders()
  })
}

function confirmTagNfcFastPickup(payload) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/pickup/tag-nfc-fast',
    method: 'POST',
    data: payload,
    headers: authHeaders()
  })
}

// ── gateway provisioning ─────────────────────────────────────────────

/**
 * Request server to prepare gateway binding parameters.
 *
 * POST /gateways/provisioning/prepare
 *
 * Payload:
 *   { gateway_device_id, gateway_serial, station_id, requested_gateway_code }
 *
 * Response (server MUST NOT return gateway_secret):
 *   { ok, server_base_url, gateway_code, station_id, registration_token,
 *     mqtt_host, mqtt_port, mqtt_tls_enabled, config_version, expires_at }
 */
function prepareGatewayBinding(payload) {
  checkServerUrl()
  // SECURITY: strip any gateway_secret that might accidentally come back
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/gateways/provisioning/prepare',
    method: 'POST',
    data: payload,
    headers: authHeaders()
  }).then((res) => {
    if (res.ok && res.data) {
      // Defensive: strip gateway_secret from response
      if (res.data.gateway_secret || res.data.GATEWAY_SECRET) {
        console.error('[SECURITY] Server returned gateway_secret — this is a backend bug. Stripping.')
        delete res.data.gateway_secret
        delete res.data.GATEWAY_SECRET
      }
    }
    return res
  })
}

/**
 * Confirm gateway binding completion with the server.
 *
 * POST /gateways/provisioning/confirm
 */
function confirmGatewayBinding(payload) {
  checkServerUrl()
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/gateways/provisioning/confirm',
    method: 'POST',
    data: payload,
    headers: authHeaders()
  })
}

// ── stations ─────────────────────────────────────────────────────────

/**
 * List stations the current staff member has access to.
 *
 * GET /stations
 */
function listStaffStations() {
  checkServerUrl()
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/stations',
    headers: authHeaders()
  })
}

// ── registration tokens ──────────────────────────────────────────────

/**
 * Get gateway registration tokens.
 *
 * GET /gateways/registration-tokens
 */
function getGatewayRegistrationToken(params) {
  checkServerUrl()
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/gateways/registration-tokens',
    headers: authHeaders(),
    data: params || {}
  })
}

/**
 * Create a gateway registration token.
 *
 * POST /gateways/registration-tokens
 */
function createGatewayRegistrationToken(payload) {
  checkServerUrl()
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/gateways/registration-tokens',
    method: 'POST',
    data: payload,
    headers: authHeaders()
  })
}

module.exports = {
  getServerHealth,
  getUserParcels,
  gateQrConfirm,
  gateNfcConfirm,
  getMyCards,
  reportMyCardLost,
  getMyParcels,
  manualConfirmPickup,
  nfcConfirmPickup,
  getUserNotifications,
  getPickupStatus,
  confirmTagNfcFastPickup,
  prepareGatewayBinding,
  confirmGatewayBinding,
  listStaffStations,
  getGatewayRegistrationToken,
  createGatewayRegistrationToken
}
