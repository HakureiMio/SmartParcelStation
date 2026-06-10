const CONFIG = require('./config')
const { request } = require('./request')
const mock = require('./mock-data')

function getLocalHealth() { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/health', mock: mock.health }) }
function gateAccessCard(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/gate/access-card', method: 'POST', data: payload, mock: () => mock.mockGatewayHint }) }
function inboundParcel(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/staff/inbound-parcel', method: 'POST', data: payload, mock: () => mock.inboundResult(payload) }) }
function bindTag(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/staff/tag/bind', method: 'POST', data: payload, mock: () => mock.bindResult(payload) }) }
function reportTagException(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/staff/tag/exception', method: 'POST', data: payload, mock: () => mock.exceptionResult(payload) }) }
function tagNfcFastPickup(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/user/tag-nfc-fast-pickup', method: 'POST', data: payload, mock: () => mock.fastPickupResult(payload) }) }

function scanBleTags(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/tags/scan', method: 'POST', data: payload, mock: () => mock.scanBleTags(payload) }) }
function registerTagFromBle(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/tags/register-from-ble', method: 'POST', data: payload, mock: () => mock.registerTagFromBle(payload) }) }
function listLocalTags() { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/tags', mock: mock.listLocalTags }) }
function getLocalTag(tagId) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: `/local/tags/${tagId}`, mock: () => mock.getLocalTag(tagId) }) }
function connectLocalTag(tagId) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: `/local/tags/${tagId}/connect`, method: 'POST', mock: () => mock.localTagAction(tagId, 'connect') }) }
function wakeLocalTag(tagId, payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: `/local/tags/${tagId}/wake`, method: 'POST', data: payload, mock: () => mock.localTagAction(tagId, 'wake') }) }
function stopLocalTag(tagId) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: `/local/tags/${tagId}/stop`, method: 'POST', mock: () => mock.localTagAction(tagId, 'stop') }) }
function readLocalTagStatus(tagId) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: `/local/tags/${tagId}/status`, mock: () => mock.localTagStatus(tagId) }) }

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
