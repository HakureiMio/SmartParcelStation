/**
 * Staff Gateway Registration page.
 *
 * Full 8-step flow to register a new gateway from scratch:
 *   Step 1 — Check staff login & server connection
 *   Step 2 — Enter / confirm gateway info
 *   Step 3 — Request binding params from server
 *   Step 4 — Connect to gateway hotspot
 *   Step 5 — Read gateway provisioning status
 *   Step 6 — Write binding params to gateway
 *   Step 7 — Wait for gateway handshake (poll verify)
 *   Step 8 — Save local session & complete
 *
 * Two network scenarios:
 *   A — Hotspot has internet: do everything in one flow
 *   B — Hotspot no internet: prepare via server on cellular, then switch to hotspot
 *
 * SECURITY: gateway_secret is NEVER stored or displayed.
 * All debug output is redacted.
 */
const authService = require('../../services/auth-service')
const serverApi = require('../../services/server-api')
const gatewayProvisioningApi = require('../../services/gateway-provisioning-api')
const { saveLocalGatewaySession } = require('../../services/local-session-service')
const { redactSensitive, isHttpsUrl, isAllowedLocalHttpUrl } = require('../../services/security-utils')
const CONFIG = require('../../services/config')

// ── helpers ──────────────────────────────────────────────────────────

function unwrap(res) {
  return res && res.data ? res.data : res
}

const STEP_TITLES = [
  '',
  'Step 1：确认员工身份和服务器连接',
  'Step 2：填写网关信息',
  'Step 3：向服务器申请绑定参数',
  'Step 4：连接网关热点',
  'Step 5：读取网关本地状态',
  'Step 6：写入绑定参数到网关',
  'Step 7：等待网关握手',
  'Step 8：绑定完成'
]

const VERIFY_STATUS_MAP = {
  ACTIVATING: '正在激活',
  WRITING_CONFIG: '正在写入配置',
  HEARTBEAT_TO_SERVER: '正在向服务器发送心跳',
  BOUND: '已完成绑定',
  FAILED: '绑定失败'
}

Page({
  data: {
    // Flow
    step: 1,
    stepTitle: STEP_TITLES[1],
    totalSteps: 8,
    scenario: 'A',  // 'A' = hotspot has internet, 'B' = two-phase

    // Status
    serverOnline: false,
    gatewayReachable: false,
    loading: false,
    error: '',

    // Staff session
    staffSession: null,

    // URLs
    serverBaseUrl: CONFIG.serverBaseUrl,
    gatewayProvisioningBaseUrl: CONFIG.defaultGatewayProvisioningBaseUrl,

    // Gateway info (Step 2 + Step 5)
    gatewayDeviceId: '',
    gatewaySerial: '',
    apSsid: '',
    localIp: '192.168.4.1',
    bindingStatus: 'UNKNOWN',
    gatewayStatus: null,

    // Station & code (Step 2)
    stationId: '',
    requestedGatewayCode: '',

    // Server response (Step 3)
    serverBindingParams: null,
    registrationToken: '',

    // Bind result (Step 6)
    bindResult: null,

    // Verify result (Step 7)
    verifyResult: null,
    verifyPollCount: 0,
    verifyStatusText: '',

    // Local session (Step 8)
    localSessionToken: '',
    localSessionExpiresAt: '',

    // Debug
    debugOpen: false,
    debugText: ''
  },

  // ── lifecycle ────────────────────────────────────────────────

  onLoad() {
    const session = authService.requireRole('staff')
    if (!session) return
    this.setData({
      staffSession: session,
      stationId: session.stationId || ''
    })
  },

  // ── step navigation ──────────────────────────────────────────

  goStep(n) {
    this.setData({
      step: n,
      stepTitle: STEP_TITLES[n] || '',
      error: ''
    })
    // Auto-run step actions
    if (n === 1) this._doStep1()
  },

  nextStep() {
    if (this.data.step < 8) {
      this.goStep(this.data.step + 1)
    }
  },

  prevStep() {
    if (this.data.step > 1) {
      this.goStep(this.data.step - 1)
    }
  },

  // ── Step 1: Check staff login & server connection ────────────

  _doStep1() {
    this.setData({ loading: true, error: '' })
    serverApi.getServerHealth().then((res) => {
      this.setData({
        serverOnline: res.ok,
        loading: false,
        error: res.ok ? '' : '服务器不可达，请检查网络连接'
      })
      if (!res.ok) {
        this.setDebug(res)
      }
    }).catch(() => {
      this.setData({
        serverOnline: false,
        loading: false,
        error: '服务器连接失败，请确认手机网络正常'
      })
    })
  },

  // ── Step 2: Enter gateway info ───────────────────────────────

  inputField(e) {
    this.setData({ [e.currentTarget.dataset.key]: e.detail.value })
  },

  fillFromStatus() {
    const s = this.data.gatewayStatus
    if (!s) return
    this.setData({
      gatewayDeviceId: s.gateway_device_id || this.data.gatewayDeviceId,
      gatewaySerial: s.gateway_serial || this.data.gatewaySerial,
      apSsid: s.ap_ssid || this.data.apSsid,
      stationId: s.station_id || this.data.stationId,
      bindingStatus: s.binding_status || this.data.bindingStatus
    })
    wx.showToast({ title: '已自动填充', icon: 'success' })
  },

  // ── Step 3: Request binding params from server ───────────────

  requestBindingParams() {
    const { gatewayDeviceId, gatewaySerial, stationId, requestedGatewayCode } = this.data
    if (!gatewaySerial) {
      this.setData({ error: '请输入网关序列号' })
      return
    }
    if (!stationId) {
      this.setData({ error: '请输入或选择站点' })
      return
    }

    this.setData({ loading: true, error: '' })

    serverApi.prepareGatewayBinding({
      gateway_device_id: gatewayDeviceId,
      gateway_serial: gatewaySerial,
      station_id: stationId,
      requested_gateway_code: requestedGatewayCode || undefined
    }).then((res) => {
      this.setDebug(res)
      if (!res.ok) {
        this.setData({
          loading: false,
          error: res.error || '服务器返回错误，请确认员工权限和站点信息'
        })
        return
      }

      const data = res.data || {}
      // SECURITY: refuse gateway_secret
      if (data.gateway_secret || data.GATEWAY_SECRET) {
        console.error('[SECURITY] Server returned gateway_secret in prepare — this is a backend error.')
        delete data.gateway_secret
        delete data.GATEWAY_SECRET
        this.setData({
          error: '安全错误：服务器不应返回 gateway_secret，请联系管理员',
          loading: false
        })
        return
      }

      // Validate server_base_url is HTTPS
      if (data.server_base_url && !isHttpsUrl(data.server_base_url) && !CONFIG.allowInsecureServerHttpInDev) {
        this.setData({
          error: '安全错误：服务器返回的 server_base_url 不是 HTTPS',
          loading: false
        })
        return
      }

      this.setData({
        serverBindingParams: data,
        registrationToken: data.registration_token || '',
        loading: false,
        error: ''
      })

      wx.showToast({ title: '绑定参数已就绪', icon: 'success' })
    }).catch(() => {
      this.setData({
        loading: false,
        error: '请求绑定参数失败，请检查网络'
      })
    })
  },

  // ── Step 4: Connect to gateway hotspot ───────────────────────

  // (User manually connects via system Wi-Fi settings)
  // Optionally attempt to read current Wi-Fi SSID via wx API

  // ── Step 5: Read gateway provisioning status ─────────────────

  readGatewayStatus() {
    this.setData({ loading: true, error: '' })
    const url = this.data.gatewayProvisioningBaseUrl

    gatewayProvisioningApi.getProvisioningStatus(url).then((res) => {
      this.setDebug(res)
      if (!res.ok) {
        this.setData({
          loading: false,
          gatewayReachable: false,
          error: '无法连接网关。请确认：\n1. 手机已连接网关热点\n2. 网关地址为 ' + url
        })
        return
      }

      const data = res.data || {}
      this.setData({
        gatewayReachable: true,
        gatewayStatus: data,
        gatewayDeviceId: data.gateway_device_id || this.data.gatewayDeviceId,
        gatewaySerial: data.gateway_serial || this.data.gatewaySerial,
        apSsid: data.ap_ssid || this.data.apSsid,
        localIp: data.local_ip || this.data.localIp,
        bindingStatus: data.binding_status || 'UNKNOWN',
        loading: false,
        error: ''
      })

      wx.showToast({ title: '网关状态已读取', icon: 'success' })
    }).catch(() => {
      this.setData({
        loading: false,
        gatewayReachable: false,
        error: '读取网关状态失败，请确认已连接网关热点'
      })
    })
  },

  // ── Step 6: Write binding params to gateway ──────────────────

  writeBindingParams() {
    const params = this.data.serverBindingParams
    if (!params) {
      this.setData({ error: '缺少服务器绑定参数，请先完成 Step 3' })
      return
    }
    if (!params.registration_token) {
      this.setData({ error: '服务器未返回 registration_token，无法继续' })
      return
    }

    // Security pre-checks
    if (params.server_base_url && !isHttpsUrl(params.server_base_url) && !CONFIG.allowInsecureServerHttpInDev) {
      this.setData({ error: 'server_base_url 必须为 HTTPS' })
      return
    }

    this.setData({ loading: true, error: '' })

    const url = this.data.gatewayProvisioningBaseUrl
    const payload = {
      server_base_url: params.server_base_url,
      gateway_code: params.gateway_code,
      station_id: params.station_id,
      registration_token: params.registration_token,
      mqtt_host: params.mqtt_host,
      mqtt_port: params.mqtt_port,
      mqtt_tls_enabled: params.mqtt_tls_enabled,
      config_version: params.config_version,
      expires_at: params.expires_at
    }

    gatewayProvisioningApi.bindGateway(url, payload).then((res) => {
      this.setDebug(res)
      if (!res.ok) {
        this.setData({
          loading: false,
          error: '网关绑定请求失败：' + (res.error || '未知错误'),
          bindResult: null
        })
        return
      }

      const data = res.data || {}

      // SECURITY: Gateway response MUST NOT be stored if it contains gateway_secret
      if (data.gateway_secret || data.GATEWAY_SECRET) {
        console.error('[SECURITY] Gateway bind response contained gateway_secret — stripped before storage.')
        delete data.gateway_secret
        delete data.GATEWAY_SECRET
      }

      this.setData({
        bindResult: data,
        loading: false,
        error: ''
      })

      wx.showToast({ title: '绑定参数已写入网关', icon: 'success' })
    }).catch(() => {
      this.setData({
        loading: false,
        error: '写入绑定参数失败，请确认网关可达'
      })
    })
  },

  // ── Step 7: Poll gateway verify ──────────────────────────────

  pollVerify() {
    this.setData({ loading: true, error: '', verifyPollCount: 0 })

    const poll = () => {
      const count = this.data.verifyPollCount + 1
      this.setData({ verifyPollCount: count })

      gatewayProvisioningApi.verifyGatewayBinding(this.data.gatewayProvisioningBaseUrl)
        .then((res) => {
          this.setDebug(res)
          const data = res.data || {}

          if (!res.ok) {
            this.setData({
              loading: false,
              error: '验证请求失败：' + (res.error || '网关不可达'),
              verifyStatusText: '验证请求失败'
            })
            return
          }

          const bindingStatus = data.binding_status || ''
          const statusText = VERIFY_STATUS_MAP[bindingStatus] || bindingStatus
          this.setData({ verifyResult: data, verifyStatusText: statusText })

          if (bindingStatus === 'BOUND') {
            // Success!
            this.setData({ loading: false, error: '' })
            wx.showToast({ title: '网关绑定成功！', icon: 'success' })
            // Auto-advance to Step 8
            this.goStep(8)
          } else if (bindingStatus === 'FAILED') {
            const errorCode = data.error_code || ''
            this.setData({
              loading: false,
              error: `网关握手失败${errorCode ? '：' + errorCode : ''}`,
              verifyStatusText: '绑定失败 — ' + (errorCode || '未知错误')
            })
          } else if (bindingStatus === 'ACTIVATING' || bindingStatus === 'WRITING_CONFIG' ||
                     bindingStatus === 'HEARTBEAT_TO_SERVER') {
            // Still in progress — poll again after delay
            this.setData({ loading: true })
            setTimeout(poll, 2000)
          } else {
            // Unknown status — stop polling
            this.setData({
              loading: false,
              error: '未知状态：' + bindingStatus + '，请检查网关日志'
            })
          }
        })
        .catch(() => {
          this.setData({
            loading: false,
            error: '验证轮询失败，请手动检查网关状态'
          })
        })
    }

    poll()
  },

  // ── Step 8: Save local session & complete ────────────────────

  completeBinding() {
    this.setData({ loading: true, error: '' })

    const bindData = this.data.bindResult || {}
    const serverParams = this.data.serverBindingParams || {}
    const localToken = bindData.local_session_token || ''

    if (localToken) {
      // Gateway returned a session token directly — save it
      this._saveAndFinish({
        gatewayBaseUrl: this.data.gatewayProvisioningBaseUrl,
        gatewayCode: serverParams.gateway_code || '',
        stationId: serverParams.station_id || this.data.stationId,
        localSessionToken: localToken,
        localSessionExpiresAt: bindData.local_session_expires_at || ''
      })
    } else {
      // Request a local session token explicitly
      gatewayProvisioningApi.createLocalSession(
        this.data.gatewayProvisioningBaseUrl,
        { gateway_code: serverParams.gateway_code }
      ).then((res) => {
        this.setDebug(res)
        const data = res.data || {}
        if (!res.ok || !data.local_session_token) {
          this.setData({
            loading: false,
            error: '获取本地会话令牌失败，请重试或联系管理员'
          })
          return
        }
        this._saveAndFinish({
          gatewayBaseUrl: this.data.gatewayProvisioningBaseUrl,
          gatewayCode: serverParams.gateway_code || '',
          stationId: serverParams.station_id || this.data.stationId,
          localSessionToken: data.local_session_token,
          localSessionExpiresAt: data.local_session_expires_at || ''
        })
      }).catch(() => {
        this.setData({
          loading: false,
          error: '请求本地会话失败'
        })
      })
    }
  },

  _saveAndFinish(session) {
    try {
      saveLocalGatewaySession(session)
      this.setData({
        loading: false,
        localSessionToken: session.localSessionToken,
        localSessionExpiresAt: session.localSessionExpiresAt,
        error: ''
      })
      wx.showToast({ title: '网关已就绪', icon: 'success' })

      // Navigate to gateway status page after a short delay
      setTimeout(() => {
        wx.redirectTo({ url: '/pages/gateway-status/gateway-status' })
      }, 800)
    } catch (err) {
      this.setData({
        loading: false,
        error: '保存会话失败：' + (err.message || '未知错误')
      })
    }
  },

  // ── scenario toggle ──────────────────────────────────────────

  setScenario(e) {
    this.setData({ scenario: e.currentTarget.dataset.scenario || 'A' })
  },

  // ── debug ────────────────────────────────────────────────────

  setDebug(res) {
    // SECURITY: always redact before displaying
    this.setData({
      debugText: JSON.stringify(redactSensitive(res), null, 2)
    })
  },

  toggleDebug() {
    this.setData({ debugOpen: !this.data.debugOpen })
  },

  // ── misc ─────────────────────────────────────────────────────

  goGatewayStatus() {
    wx.navigateTo({ url: '/pages/gateway-status/gateway-status' })
  }
})
