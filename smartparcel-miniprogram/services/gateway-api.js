/**
 * Gateway local business API.
 *
 * All protected endpoints require Authorization: Bearer <local_session_token>.
 * If the local session is missing or expired the call returns
 * { ok: false, error: 'LOCAL_SESSION_MISSING' }.
 *
 * NO mock data. NO fallback to fake responses.
 */
const CONFIG = require('./config')
const { request } = require('./request')
const { getLocalSessionToken } = require('./local-session-service')

// ── helpers ──────────────────────────────────────────────────────────

/**
 * Build headers with the local session token if available.
 * Returns null if the session is required but missing.
 */
function localAuthHeaders(required) {
  const token = getLocalSessionToken()
  if (!token && required) return null
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Resolve gatewayBaseUrl: prefer from local session, fall back to config.
 */
function gwBaseUrl() {
  const { getLocalGatewaySession } = require('./local-session-service')
  const session = getLocalGatewaySession()
  return (session && session.gatewayBaseUrl) || CONFIG.defaultGatewayProvisioningBaseUrl
}

/**
 * Wrap a request so that if local session is missing it returns a clear error.
 */
function withLocalAuth(fn, required) {
  return function (...args) {
    const headers = localAuthHeaders(required)
    if (required && !headers) {
      return Promise.resolve({
        ok: false,
        statusCode: 0,
        error: 'LOCAL_SESSION_MISSING',
        data: null
      })
    }
    return fn(headers, ...args)
  }
}

// ── health (no auth required) ────────────────────────────────────────

function getLocalHealth() {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/health'
  })
}

// ── door / gate (requires local auth) ────────────────────────────────

const gateAccessCard = withLocalAuth(function (headers, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/gate/access-card',
    method: 'POST',
    data: payload,
    headers
  })
}, true)

// ── staff inbound / bind / exception (requires local auth) ───────────

const inboundParcel = withLocalAuth(function (headers, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/staff/inbound-parcel',
    method: 'POST',
    data: payload,
    headers
  })
}, true)

const bindTag = withLocalAuth(function (headers, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/staff/tag/bind',
    method: 'POST',
    data: payload,
    headers
  })
}, true)

const reportTagException = withLocalAuth(function (headers, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/staff/tag/exception',
    method: 'POST',
    data: payload,
    headers
  })
}, true)

// ── user NFC pickup (requires local auth) ────────────────────────────

const tagNfcFastPickup = withLocalAuth(function (headers, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/user/tag-nfc-fast-pickup',
    method: 'POST',
    data: payload,
    headers
  })
}, true)

// ── BLE tag management (requires local auth) ─────────────────────────

const scanBleTags = withLocalAuth(function (headers, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/tags/scan',
    method: 'POST',
    data: payload,
    headers
  })
}, true)

const registerTagFromBle = withLocalAuth(function (headers, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/tags/register-from-ble',
    method: 'POST',
    data: payload,
    headers
  })
}, true)

const listLocalTags = withLocalAuth(function (headers) {
  return request({
    baseUrl: gwBaseUrl(),
    url: '/local/tags',
    headers
  })
}, true)

const getLocalTag = withLocalAuth(function (headers, tagId) {
  return request({
    baseUrl: gwBaseUrl(),
    url: `/local/tags/${tagId}`,
    headers
  })
}, true)

const connectLocalTag = withLocalAuth(function (headers, tagId) {
  return request({
    baseUrl: gwBaseUrl(),
    url: `/local/tags/${tagId}/connect`,
    method: 'POST',
    headers
  })
}, true)

const wakeLocalTag = withLocalAuth(function (headers, tagId, payload) {
  return request({
    baseUrl: gwBaseUrl(),
    url: `/local/tags/${tagId}/wake`,
    method: 'POST',
    data: payload,
    headers
  })
}, true)

const stopLocalTag = withLocalAuth(function (headers, tagId) {
  return request({
    baseUrl: gwBaseUrl(),
    url: `/local/tags/${tagId}/stop`,
    method: 'POST',
    headers
  })
}, true)

const readLocalTagStatus = withLocalAuth(function (headers, tagId) {
  return request({
    baseUrl: gwBaseUrl(),
    url: `/local/tags/${tagId}/status`,
    headers
  })
}, true)

module.exports = {
  getLocalHealth,
  gateAccessCard,
  inboundParcel,
  bindTag,
  reportTagException,
  tagNfcFastPickup,
  scanBleTags,
  registerTagFromBle,
  listLocalTags,
  getLocalTag,
  connectLocalTag,
  wakeLocalTag,
  stopLocalTag,
  readLocalTagStatus
}
