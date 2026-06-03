function maskPhone(phone = '') { return phone ? phone.replace(/(\d{3})\d{4}(\d+)/, '$1****$2') : '' }
function nowText() { const d = new Date(); return d.getFullYear() + '-' + (d.getMonth()+1) + '-' + d.getDate() + ' ' + String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0') }
function sourceText(source) { return '数据来源：' + (source || 'mock') }
module.exports = { maskPhone, nowText, sourceText }
