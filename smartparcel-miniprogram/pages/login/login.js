const authApi = require('../../services/auth-api')
const authService = require('../../services/auth-service')

const ROLE_META = {
  client: { title: '客户端登录', accent: 'client', username: 'user001' },
  staff: { title: '员工端登录', accent: 'staff', username: 'staff001' }
}

Page({
  data: {
    role: 'client',
    title: '客户端登录',
    accent: 'client',
    username: '',
    password: '',
    loading: false,
    error: ''
  },
  onLoad(options) {
    const role = options.role === 'staff' ? 'staff' : 'client'
    const meta = ROLE_META[role]
    this.setData({ role, title: meta.title, accent: meta.accent, username: meta.username, password: '123456' })
  },
  inputUsername(e) { this.setData({ username: e.detail.value, error: '' }) },
  inputPassword(e) { this.setData({ password: e.detail.value, error: '' }) },
  submit() {
    if (!this.data.username || !this.data.password) {
      this.setData({ error: '请输入账号和密码' })
      return
    }
    this.setData({ loading: true, error: '' })
    authApi.login({ role: this.data.role, username: this.data.username, password: this.data.password }).then((res) => {
      const data = res.data || {}
      if (!data.token || data.ok === false) {
        this.setData({ error: data.message || '账号或密码错误', loading: false })
        return
      }
      authService.saveSession(data)
      wx.showToast({ title: '登录成功', icon: 'success' })
      const target = data.role === 'staff' ? '/pages/staff-home/staff-home' : '/pages/user-home/user-home'
      setTimeout(() => wx.redirectTo({ url: target }), 250)
    }).catch(() => {
      this.setData({ error: '登录失败，请稍后再试', loading: false })
    })
  },
  forgot() { wx.navigateTo({ url: `/pages/forgot-password/forgot-password?role=${this.data.role}` }) },
  register() { wx.navigateTo({ url: `/pages/register/register?role=${this.data.role}` }) }
})
