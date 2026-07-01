package io.github.hakureimio.smartparcel.demo
import org.junit.Assert.assertEquals
import org.junit.Test
class SpsPayloadTest { @Test fun parsesGateNfc() { val p=SpsPayload.parse("sps://gate-nfc?v=1&gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001"); assertEquals(SpsPayload.Type.GATE_NFC,p.type); assertEquals("GW001",p.values["gateway_code"]) } }
