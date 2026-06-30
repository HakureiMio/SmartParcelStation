/**
 * Login page — real server auth only.
 *
 * NO default credentials. NO demo-mode toast. NO mock fallback.
 * If the server is unreachable the user sees a clear error.
 */
const authApi = require('../../services/auth-api')
const authService = require('../../services/auth-service')

const ROLE_META = {
  client: { title: '客户登录', accent: 'client' },
  staff:  { title: '员工登录', accent: 'staff' }
}

Page({
  data: {
    role: 'client',
    title: '客户登录',
    accent: 'client',
    username: '',
    password: '',
    loading: false,
    error: ''
  },

  onLoad(options) {
    const role = options.role === 'staff' ? 'staff' : 'client'
    const meta = ROLE_META[role]
    this.setData({
      role,
      title: meta.title,
      accent: meta.accent,
      username: '',
      password: ''
    })
  },

  inputUsername(e) {
    this.setData({ username: e.detail.value, error: '' })
  },

  inputPassword(e) {
    this.setData({ password: e.detail.value, error: '' })
  },

  submit() {
    const { role, username, password } = this.data
    if (!username || !password) {
      this.setData({ error: '请输入账号和密码' })
      return
    }

    this.setData({ loading: true, error: '' })

    authApi.login({ role, username, password }).then((res) => {
      if (!res.ok) {
        // Distinguish server-unreachable from bad credentials
        const msg = res.statusCode === 0
          ? '服务器连接失败，请检查网络'
          : (res.data && res.data.message) || '账号或密码错误'
        this.setData({ error: msg, loading: false })
        return
      }

      const data = res.data || {}
      if (!data.token) {
        this.setData({ error: '服务器返回异常，缺少认证令牌', loading: false })
        return
      }

      authService.saveSession(data)
      wx.showToast({ title: '登录成功', icon: 'success' })

      const target = data.role === 'staff'
        ? '/pages/staff-home/staff-home'
        : '/pages/user-home/user-home'

      setTimeout(() => wx.redirectTo({ url: target }), 250)
    }).catch(() => {
      this.setData({ error: '登录失败，请稍后再试', loading: false })
    })
  },

  forgot() {
    wx.navigateTo({
      url: `/pages/forgot-password/forgot-password?role=${this.data.role}`
    })
  },

  register() {
    wx.navigateTo({
      url: `/pages/register/register?role=${this.data.role}`
    })
  }
})
