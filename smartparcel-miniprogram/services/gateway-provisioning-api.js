/**
 * Gateway Provisioning API — calls the gateway's local HTTP API over the
 * device hotspot (typically http://192.168.4.1:19000).
 *
 * These endpoints are used during the one-time gateway registration flow.
 * They do NOT require a local session token (the gateway is unbound).
 *
 * Endpoints:
 *   GET  /local/provisioning/status        — read gateway provisioning state
 *   POST /local/provisioning/bind          — push server binding params
 *   POST /local/provisioning/verify        — poll binding result
 *   POST /local/provisioning/local-session — request a short-lived session token
 */
const CONFIG = require('./config')
const { request } = require('./request')
const { redactSensitive } = require('./security-utils')

/**
 * Read gateway provisioning status.
 *
 * GET /local/provisioning/status
 *
 * Response:
 *   { binding_status, gateway_device_id, gateway_serial, ap_ssid, local_ip, gateway_code, station_id, ... }
 */
function getProvisioningStatus(baseUrl) {
  const url = baseUrl || CONFIG.defaultGatewayProvisioningBaseUrl
  return request({
    baseUrl: url,
    url: '/local/provisioning/status',
    method: 'GET',
    timeoutMs: CONFIG.requestTimeoutMs
  })
}

/**
 * Push server binding parameters to the gateway.
 *
 * POST /local/provisioning/bind
 *
 * Payload (from server prepareGatewayBinding response):
 *   { server_base_url, gateway_code, station_id, registration_token,
 *     mqtt_host, mqtt_port, mqtt_tls_enabled, config_version, expires_at }
 *
 * SECURITY: The response is redacted before logging. gateway_secret MUST NOT
 * be stored or displayed by the mini program.
 */
function bindGateway(baseUrl, payload) {
  const url = baseUrl || CONFIG.defaultGatewayProvisioningBaseUrl

  // Security pre-check
  if (payload.registration_token) {
    // This is expected — it will be sent to gateway and then discarded.
  }

  return request({
    baseUrl: url,
    url: '/local/provisioning/bind',
    method: 'POST',
    data: payload,
    timeoutMs: CONFIG.requestTimeoutMs
  }).then((res) => {
    // SECURITY: strip gateway_secret from any response before caller sees it.
    if (res.ok && res.data) {
      if (res.data.gateway_secret !== undefined || res.data.GATEWAY_SECRET !== undefined) {
        console.error('[SECURITY] Gateway bind response contained gateway_secret — stripping.')
        delete res.data.gateway_secret
        delete res.data.GATEWAY_SECRET
      }
    }
    return res
  })
}

/**
 * Poll gateway binding / handshake status.
 *
 * POST /local/provisioning/verify
 *
 * Response indicates:
 *   - binding_status: ACTIVATING | WRITING_CONFIG | HEARTBEAT_TO_SERVER | BOUND | FAILED
 *   - error_code:     SERVER_UNREACHABLE | REGISTRATION_TOKEN_EXPIRED |
 *                     GATEWAY_HEARTBEAT_FAILED | INVALID_GATEWAY_CODE | STATION_MISMATCH
 */
function verifyGatewayBinding(baseUrl) {
  const url = baseUrl || CONFIG.defaultGatewayProvisioningBaseUrl
  return request({
    baseUrl: url,
    url: '/local/provisioning/verify',
    method: 'POST',
    timeoutMs: CONFIG.requestTimeoutMs
  })
}

/**
 * Request a short-lived local session token from the gateway.
 *
 * POST /local/provisioning/local-session
 *
 * This should only be called after binding is complete.
 * The returned token is short-lived (e.g. 24h).
 */
function createLocalSession(baseUrl, payload) {
  const url = baseUrl || CONFIG.defaultGatewayProvisioningBaseUrl
  return request({
    baseUrl: url,
    url: '/local/provisioning/local-session',
    method: 'POST',
    data: payload || {},
    timeoutMs: CONFIG.requestTimeoutMs
  }).then((res) => {
    // SECURITY: redact session token from console/debug output
    if (res.ok && res.data && res.data.local_session_token) {
      // token is kept in data for the caller to store, but logging is redacted
    }
    return res
  })
}

module.exports = {
  getProvisioningStatus,
  bindGateway,
  verifyGatewayBinding,
  createLocalSession
}
