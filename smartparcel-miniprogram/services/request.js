/**
 * Generic HTTP request wrapper.
 *
 * Returns a structured result — never falls back to mock data.
 *   Success: { ok: true,  statusCode: 200, data: res.data }
 *   Failure: { ok: false, statusCode,       error, data }
 *
 * Supports:
 *   - custom headers (including Authorization: Bearer <token>)
 *   - configurable timeout
 *   - 401 / 403 preserved for caller handling (no auto-redirect)
 */
const CONFIG = require('./config')
const { isAllowedLocalHttpUrl, isHttpsUrl } = require('./security-utils')

function request({
  baseUrl = '',
  url,
  method = 'GET',
  data = {},
  headers = {},
  timeoutMs = CONFIG.requestTimeoutMs
}) {
  // Safety: reject insecure server URLs unless explicitly allowed.
  if (baseUrl && !isAllowedLocalHttpUrl(baseUrl) && !isHttpsUrl(baseUrl)) {
    if (!CONFIG.allowInsecureServerHttpInDev) {
      return Promise.resolve({
        ok: false,
        statusCode: 0,
        error: 'SECURITY: serverBaseUrl must be HTTPS in production',
        data: null
      })
    }
  }

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
      finish({
        ok: false,
        statusCode: 0,
        error: `request timeout after ${timeoutMs}ms`,
        data: null
      })
    }, timeoutMs + 800)

    wx.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      timeout: timeoutMs,
      header: { 'Content-Type': 'application/json', ...headers },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          finish({ ok: true, statusCode: res.statusCode, data: res.data })
          return
        }
        // Preserve status code for 401/403 handling by callers.
        finish({
          ok: false,
          statusCode: res.statusCode,
          error: `HTTP ${res.statusCode}`,
          data: res.data
        })
      },
      fail(err) {
        finish({
          ok: false,
          statusCode: 0,
          error: err.errMsg || 'network request failed',
          data: null
        })
      },
      complete() {
        if (!settled) {
          finish({
            ok: false,
            statusCode: 0,
            error: 'request completed without result',
            data: null
          })
        }
      }
    })
  })
}

module.exports = { request }
