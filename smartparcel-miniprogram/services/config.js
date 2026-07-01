/**
 * Application configuration.
 *
 * - Gateway provisioning runs on the device hotspot LAN and may use HTTP.
 * - Server API MUST use HTTPS in production.
 * - If serverBaseUrl is HTTP, it is rejected unless allowInsecureServerHttpInDev is true.
 */
const CONFIG = {
  serverBaseUrl: 'http://198.13.33.220:18000/api/v1',
  defaultGatewayProvisioningBaseUrl: 'http://192.168.4.1:19000',
  requestTimeoutMs: 12000,

  /** wx.storage key for the local gateway session (short-lived). */
  localSessionStorageKey: 'sps_gateway_local_session',

  /** Allow HTTP for gateway provisioning (LAN hotspot). */
  allowInsecureLocalHttp: true,

  /** Allow HTTP for server requests (development only). Set false in production. */
  allowInsecureServerHttpInDev: true
}

module.exports = CONFIG
