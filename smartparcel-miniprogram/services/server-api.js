const CONFIG = require('./config')
const { request } = require('./request')
const mock = require('./mock-data')
function getHealth() { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/health', mock: mock.health }) }
function getUserParcels(userId) { return request({ baseUrl: CONFIG.serverBaseUrl, url: `/users/${userId}/parcels`, mock: () => mock.parcels }) }
function getUserNotifications(userId) { return request({ baseUrl: CONFIG.serverBaseUrl, url: `/users/${userId}/notifications`, mock: () => mock.notifications }) }
function getPickupStatus(userId) { return request({ baseUrl: CONFIG.serverBaseUrl, url: `/users/${userId}/pickup-status`, mock: mock.pickupStatus }) }
function confirmTagNfcFastPickup(payload) { return request({ baseUrl: CONFIG.serverBaseUrl, url: '/pickup/tag-nfc-fast', method: 'POST', data: payload, mock: () => mock.fastPickupResult(payload) }) }
module.exports = { getHealth, getUserParcels, getUserNotifications, getPickupStatus, confirmTagNfcFastPickup }
