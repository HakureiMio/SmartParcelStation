const authService = require('../../services/auth-service')
const gatewayApi = require('../../services/gateway-api')
const nfc = require('../../services/nfc-service')

Page({
  data:{
    step:1,
    parcel:{ parcelCode:'P20260602001', receiverPhone:'18800000002', pickupCode:'123456', receiverUserId:'2', receiverNameMasked:'张*', shelfCode:'A03' },
    tag:{ tagId:'', tagNfcId:'' },
    readText:'尚未读取标签',
    resultText:'',
    submitting:false
  },
  onLoad(){ authService.requireRole('staff') },
  inputParcel(e){ this.setData({[`parcel.${e.currentTarget.dataset.key}`]: e.detail.value}) },
  inputTag(e){ this.setData({[`tag.${e.currentTarget.dataset.key}`]: e.detail.value}) },
  nextToTag(){ const p=this.data.parcel; if(!p.parcelCode || !p.receiverPhone || !p.pickupCode || !p.receiverUserId || !p.shelfCode){ wx.showToast({ title:'请补全包裹信息', icon:'none' }); return } this.setData({ step:2 }) },
  readTag(){ nfc.readTag().then((res)=>{ if(res.ok){ this.setData({ tag:{ tagId:res.parsed.tag_id || '', tagNfcId:res.parsed.tag_nfc_id || '' }, readText:`已读取标签 ${res.parsed.tag_id || ''}` }); wx.showToast({ title:'读取成功', icon:'success' }) } else { this.setData({ readText:res.reason || '读取失败，可手动输入' }); wx.showToast({ title:'读取失败', icon:'none' }) } }) },
  nextToConfirm(){ if(!this.data.tag.tagId || !this.data.tag.tagNfcId){ wx.showToast({ title:'请读取或输入标签', icon:'none' }); return } this.setData({ step:3 }) },
  prev(){ this.setData({ step: Math.max(1, this.data.step - 1) }) },
  confirm(){ if(this.data.submitting) return; this.setData({ submitting:true, resultText:'' }); gatewayApi.inboundParcel(this.data.parcel).then((inbound)=>{ if((inbound.data||{}).ok === false) throw new Error('inbound failed'); return gatewayApi.bindTag({ parcelCode:this.data.parcel.parcelCode, tagId:this.data.tag.tagId, tagNfcId:this.data.tag.tagNfcId }) }).then((bind)=>{ if((bind.data||{}).ok === false) throw new Error('bind failed'); this.setData({ resultText:'入库完成，标签已绑定', submitting:false }); wx.showToast({ title:'操作完成', icon:'success' }) }).catch(()=>{ this.setData({ resultText:'操作失败，请检查信息后重试', submitting:false }); wx.showToast({ title:'操作失败', icon:'none' }) }) }
})
