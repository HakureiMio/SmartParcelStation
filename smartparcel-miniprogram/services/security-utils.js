/**
 * Security utilities.
 *
 * - URL safety checks (HTTPS enforcement, local HTTP allowlist)
 * - Sensitive field redaction for debug output
 * - Lightweight SHA-256 (when available; otherwise degrade gracefully)
 */

const SENSITIVE_FIELDS = [
  'gateway_secret',
  'GATEWAY_SECRET',
  'registration_token',
  'one_time_binding_token',
  'local_session_token',
  'Authorization',
  'token',
  'password',
  'appsecret',
  'secret',
  'signature',
  'access_token',
  'refresh_token',
  'api_key',
  'private_key'
]

/**
 * Returns true if url starts with https://.
 */
function isHttpsUrl(url) {
  return typeof url === 'string' && url.indexOf('https://') === 0
}

/**
 * Returns true if url is an allowed local HTTP URL (e.g. gateway hotspot).
 * Currently allows http://192.168.4.1:* and http://localhost:*.
 */
function isAllowedLocalHttpUrl(url) {
  if (typeof url !== 'string') return false
  if (url.indexOf('http://') !== 0) return false
  // Allow standard gateway provisioning address
  if (url.indexOf('http://192.168.4.1') === 0) return true
  // Allow localhost for development
  if (url.indexOf('http://127.0.0.1') === 0 || url.indexOf('http://localhost') === 0) return true
  return false
}

/**
 * Redact sensitive fields from an object or string for safe logging / display.
 * Returns a deep copy with sensitive values replaced by '***REDACTED***'.
 */
function redactSensitive(input) {
  if (input === null || input === undefined) return input
  if (typeof input === 'string') {
    // Try parsing as JSON and redact
    try {
      const parsed = JSON.parse(input)
      return JSON.stringify(redactSensitive(parsed), null, 2)
    } catch (_) {
      return input
    }
  }
  if (Array.isArray(input)) {
    return input.map(redactSensitive)
  }
  if (typeof input === 'object') {
    const result = {}
    for (const key of Object.keys(input)) {
      const lowerKey = key.toLowerCase()
      const shouldRedact = SENSITIVE_FIELDS.some(
        (f) => lowerKey === f.toLowerCase() || lowerKey.indexOf(f.toLowerCase()) >= 0
      )
      if (shouldRedact) {
        result[key] = '***REDACTED***'
      } else {
        result[key] = redactSensitive(input[key])
      }
    }
    return result
  }
  return input
}

/**
 * Lightweight SHA-256 hex digest.
 *
 * On WeChat Mini Program this requires a JS implementation; the built-in
 * wx.getCryptoManager() may not be available on all base library versions.
 *
 * Returns a Promise that resolves with the hex string, or rejects with an
 * error that callers should handle gracefully (e.g. skip HMAC in dev).
 */
function sha256Hex(input) {
  return new Promise((resolve, reject) => {
    if (typeof input !== 'string') {
      return reject(new Error('sha256Hex expects a string'))
    }
    // Attempt to use wx API if available
    if (typeof wx !== 'undefined' && wx.getCryptoManager && typeof wx.getCryptoManager === 'function') {
      try {
        const crypto = wx.getCryptoManager()
        if (crypto && crypto.sha256) {
          crypto.sha256({
            text: input,
            success(res) {
              resolve(res.digest || '')
            },
            fail(err) {
              reject(new Error(err.errMsg || 'wx crypto sha256 failed'))
            }
          })
          return
        }
      } catch (_) { /* fall through */ }
    }

    // Fallback: lightweight pure-JS SHA-256 (for environments without crypto API)
    try {
      const hex = _jsSha256(input)
      resolve(hex)
    } catch (err) {
      reject(new Error('SHA-256 not available: ' + (err.message || 'unknown')))
    }
  })
}

/**
 * Pure-JS SHA-256 implementation (public domain).
 * Used as fallback when wx.getCryptoManager is unavailable.
 */
function _jsSha256(message) {
  function rightRotate(value, amount) {
    return (value >>> amount) | (value << (32 - amount))
  }

  const mathPow = Math.pow
  const maxWord = mathPow(2, 32)
  let i, j
  let result = ''

  const words = []
  const asciiBitLength = message.length * 8
  let hash = []

  const k = []
  let primeCounter = 0
  const isComposite = {}
  for (let candidate = 2; primeCounter < 64; candidate++) {
    if (!isComposite[candidate]) {
      for (i = 0; i < 313; i += candidate) {
        isComposite[i] = true
      }
      hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0
      k[primeCounter++] = (mathPow(candidate, 1 / 3) * maxWord) | 0
    }
  }

  message += '\x80'
  while ((message.length % 64) - 56) message += '\x00'
  for (i = 0; i < message.length; i++) {
    j = message.charCodeAt(i)
    if (j >> 8) return ''
    words[i >> 2] |= j << (((3 - i) % 4) * 8)
  }
  words[words.length] = (asciiBitLength / maxWord) | 0
  words[words.length] = asciiBitLength

  for (j = 0; j < words.length;) {
    const w = words.slice(j, (j += 16))
    const oldHash = hash
    hash = hash.slice(0, 8)

    for (i = 0; i < 64; i++) {
      const w15 = w[i - 15], w2 = w[i - 2]
      const a = hash[0], e = hash[4]
      const temp1 =
        hash[7] +
        (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25)) +
        ((e & hash[5]) ^ (~e & hash[6])) +
        k[i] +
        (w[i] =
          i < 16
            ? w[i]
            : (w[i - 16] +
                (rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3)) +
                w[i - 7] +
                (rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10))) |
              0)
      const temp2 =
        (rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22)) +
        ((a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]))
      hash = [(temp1 + temp2) | 0].concat(hash)
      hash[4] = (hash[4] + temp1) | 0
    }

    for (i = 0; i < 8; i++) {
      hash[i] = (hash[i] + oldHash[i]) | 0
    }
  }

  for (i = 0; i < 8; i++) {
    for (j = 3; j + 1; j--) {
      const b = (hash[i] >> (j * 8)) & 255
      result += ((b < 16) ? '0' : '') + b.toString(16)
    }
  }
  return result
}

/**
 * Build proof headers for local gateway API calls.
 *
 * When a local session key is available, builds a lightweight proof header.
 * This is NOT full HMAC — it is a placeholder until the backend HMAC spec
 * is finalized. The actual HMAC-SHA256 signing will be implemented once
 * the gateway firmware defines the exact signing protocol.
 *
 * @param {string} method   - HTTP method
 * @param {string} path     - Request path
 * @param {object} body     - Request body (nullable)
 * @param {string} optionalSessionKey - Local session token (optional)
 * @returns {Promise<object>} Headers object
 */
function buildLocalProofHeaders(method, path, body, optionalSessionKey) {
  const headers = {}
  if (!optionalSessionKey) return Promise.resolve(headers)

  // Placeholder: full HMAC signing will be added once gateway spec is finalized.
  // For now we include the session token as Bearer auth.
  headers['Authorization'] = `Bearer ${optionalSessionKey}`
  return Promise.resolve(headers)
}

module.exports = {
  SENSITIVE_FIELDS,
  isHttpsUrl,
  isAllowedLocalHttpUrl,
  redactSensitive,
  sha256Hex,
  buildLocalProofHeaders
}
