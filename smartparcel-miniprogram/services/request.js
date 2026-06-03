const CONFIG = require('./config')

function request({ baseUrl = '', url, method = 'GET', data = {}, headers = {}, mock }) {
  return new Promise((resolve) => {
    wx.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      timeout: CONFIG.requestTimeoutMs,
      header: { 'Content-Type': 'application/json', ...headers },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve({ ok: true, source: 'real', data: res.data })
        else resolve(fallback(`HTTP ${res.statusCode}`, mock))
      },
      fail(err) { resolve(fallback(err.errMsg || 'request fail', mock)) }
    })
  })
}
function fallback(reason, mock) {
  if (typeof mock === 'function') return { ok: true, source: 'mock', data: mock(), reason }
  return { ok: false, source: 'error', error: reason }
}
module.exports = { request }
