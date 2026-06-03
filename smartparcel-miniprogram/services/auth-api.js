const CONFIG = require('./config')
const { request } = require('./request')

const DEMO_ACCOUNTS = {
  client: { username: 'user001', password: '123456', user_id: '2', role: 'client', display_name: '用户 002', station_id: '1' },
  staff: { username: 'staff001', password: '123456', user_id: '3', role: 'staff', display_name: '员工 001', station_id: '1' }
}

function mockLogin(payload) {
  const account = DEMO_ACCOUNTS[payload.role]
  if (!account || payload.username !== account.username || payload.password !== account.password) {
    return { ok: false, message: '账号或密码错误' }
  }
  return { ok: true, token: `mock-token-${account.role}-${Date.now()}`, ...account }
}

function login(payload) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/auth/login',
    method: 'POST',
    data: payload,
    mock: () => mockLogin(payload)
  })
}

function register(payload) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/auth/register',
    method: 'POST',
    data: payload,
    mock: () => ({ ok: false, message: '注册功能暂未开放' })
  })
}

function forgotPassword(payload) {
  return request({
    baseUrl: CONFIG.serverBaseUrl,
    url: '/auth/forgot-password',
    method: 'POST',
    data: payload,
    mock: () => ({ ok: false, message: '忘记密码功能暂未开放' })
  })
}

module.exports = { login, register, forgotPassword }
