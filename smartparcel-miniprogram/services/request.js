const CONFIG = require('./config')

function request({
  baseUrl = '',
  url,
  method = 'GET',
  data = {},
  headers = {},
  mock,
  useMockWhenRequestFail = CONFIG.useMockWhenRequestFail,
  timeoutMs = CONFIG.requestTimeoutMs
}) {
  return new Promise((resolve) => {
    let settled = false
    let timer = null

    function finish(value) {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      resolve(value)
    }

    timer = setTimeout(() => {
      finish(fallback(`request timeout after ${timeoutMs}ms`, mock, useMockWhenRequestFail))
    }, timeoutMs + 800)

    wx.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      timeout: timeoutMs,
      header: { 'Content-Type': 'application/json', ...headers },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          finish({ ok: true, source: 'real', data: res.data })
          return
        }
        finish(fallback(`HTTP ${res.statusCode}`, mock, useMockWhenRequestFail))
      },
      fail(err) {
        finish(fallback(err.errMsg || 'request fail', mock, useMockWhenRequestFail))
      },
      complete() {
        if (!settled) {
          finish(fallback('request completed without result', mock, useMockWhenRequestFail))
        }
      }
    })
  })
}

function fallback(reason, mock, useMockWhenRequestFail) {
  if (useMockWhenRequestFail && typeof mock === 'function') {
    try {
      return { ok: true, source: 'mock', data: mock(), reason }
    } catch (err) {
      return { ok: false, source: 'error', error: err && err.message ? err.message : reason }
    }
  }
  return { ok: false, source: 'error', error: reason }
}

module.exports = { request }
