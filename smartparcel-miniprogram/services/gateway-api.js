const CONFIG = require('./config')
const { request } = require('./request')
const mock = require('./mock-data')
function getLocalHealth() { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/health', mock: mock.health }) }
function gateAccessCard(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/gate/access-card', method: 'POST', data: payload, mock: () => mock.mockGatewayHint }) }
function inboundParcel(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/staff/inbound-parcel', method: 'POST', data: payload, mock: () => mock.inboundResult(payload) }) }
function bindTag(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/staff/tag/bind', method: 'POST', data: payload, mock: () => mock.bindResult(payload) }) }
function reportTagException(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/staff/tag/exception', method: 'POST', data: payload, mock: () => mock.exceptionResult(payload) }) }
function tagNfcFastPickup(payload) { return request({ baseUrl: CONFIG.gatewayBaseUrl, url: '/local/user/tag-nfc-fast-pickup', method: 'POST', data: payload, mock: () => mock.fastPickupResult(payload) }) }
module.exports = { getLocalHealth, gateAccessCard, inboundParcel, bindTag, reportTagException, tagNfcFastPickup }
