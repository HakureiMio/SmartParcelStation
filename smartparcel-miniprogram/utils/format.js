/**
 * Display formatting helpers.
 *
 * NO mock defaults. sourceText() returns '未知' when source is absent.
 */
function maskPhone(phone) {
  if (!phone) return ''
  return phone.replace(/(\d{3})\d{4}(\d+)/, '$1****$2')
}

function nowText() {
  const d = new Date()
  return d.getFullYear() + '-' +
    String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0') + ' ' +
    String(d.getHours()).padStart(2, '0') + ':' +
    String(d.getMinutes()).padStart(2, '0') + ':' +
    String(d.getSeconds()).padStart(2, '0')
}

function sourceText(source) {
  if (!source) return '未知'
  return '数据来源：' + source
}

module.exports = { maskPhone, nowText, sourceText }
