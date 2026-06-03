const gatewayApi = require('../../services/gateway-api')
const nfc = require('../../services/nfc-service')
function pretty(value){ return value ? JSON.stringify(value, null, 2) : '' }
Page({ data:{ form:{ parcelCode:'P20260602001', tagId:'TAG001', tagNfcId:'NFC_TAG_001' }, resultText:'', source:'mock' }, input(e){ this.setData({[`form.${e.currentTarget.dataset.key}`]: e.detail.value}) }, read(){ nfc.readTag().then(res=>this.setData({'form.tagId':res.parsed.tag_id, 'form.tagNfcId':res.parsed.tag_nfc_id, resultText:pretty(res)})) }, submit(){ gatewayApi.bindTag(this.data.form).then(res=>this.setData({resultText:pretty(res.data), source:res.source})) } })
