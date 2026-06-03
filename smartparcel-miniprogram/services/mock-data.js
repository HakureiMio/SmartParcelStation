const mockGatewayHint = { access:'GRANTED', gateway_code:'GW001', station_id:'1', pickup_count:3, session_color:'BLUE', color_display_name:'蓝色', shelves:['A03','B12','C07'], display_text:'待取3件｜蓝色闪烁｜A03 B12 C07', warnings:[] }
const parcels = [
  { parcel_code:'P20260602001', status:'WAITING_PICKUP', shelf_code:'A03', nfc_fast_pickup:true, tag_color:'蓝色', receiver_phone:'188****0002', receiver_name_masked:'张*' },
  { parcel_code:'P20260602002', status:'WAITING_PICKUP', shelf_code:'B12', nfc_fast_pickup:true, tag_color:'蓝色', receiver_phone:'188****0002', receiver_name_masked:'张*' },
  { parcel_code:'P20260602003', status:'ARRIVED_AT_STATION', shelf_code:'C07', nfc_fast_pickup:false, tag_color:'蓝色', receiver_phone:'188****0002', receiver_name_masked:'张*' }
]
const notifications = [
  { id:'N001', type:'ARRIVED', title:'包裹到站', content:'您的包裹 P20260602001 已到站，请及时取件。', time:'2026-06-03 10:20' },
  { id:'N002', type:'PICKUP', title:'取件成功', content:'包裹 P20260601008 已完成取件。', time:'2026-06-02 18:42' },
  { id:'N003', type:'EXCEPTION', title:'异常提醒', content:'某标签低电量，工作人员将人工核验。', time:'2026-06-02 09:15' }
]
function pickupStatus(){ return { step:'待 NFC 确认', gateway_hint:mockGatewayHint, parcels } }
function health(){ return { status:'ok', mode:'mock', gateway_code:'GW001', station_id:'1' } }
function inboundResult(payload){ return { ok:true, source:'mock', message:'mock 入库成功', parcel:payload } }
function bindResult(payload){ return { ok:true, source:'mock', message:'mock 绑定成功', shelf_code:'A03', ...payload } }
function exceptionResult(payload){ return { ok:true, source:'mock', message:'mock 异常已记录', ...payload } }
function fastPickupResult(payload){ return { ok:true, source:'mock', message:'mock NFC 快速取件确认成功', pickup_method:payload.pickupMethod || 'TAG_NFC_FAST' } }
module.exports = { mockGatewayHint, parcels, notifications, pickupStatus, health, inboundResult, bindResult, exceptionResult, fastPickupResult }
