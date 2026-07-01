# Mini program gate authentication flow

## Three entry points

1. `CARD_UID`: the user presents a physical card or phone HCE card directly to the reader.
2. `GATE_QR`: `wx.scanCode()` reads the dynamic gate-screen QR payload, then the mini program
   calls `/gate/auth/qr-confirm` with the user Bearer token.
3. `GATE_NFC_TAG`: the phone reads the gate NFC NDEF payload, then calls
   `/gate/auth/nfc-confirm` with the user Bearer token.

The server submission is not an access-granted response. The UI always tells the user to check
the gate display because the gateway makes the final decision.

## NFC payload distinction

- Gate tag: `sps://gate-nfc?v=1&gateway_code=...&reader_id=...&station_id=...&gate_nfc_tag_id=...`
- Parcel pickup tag: `sps://pickup?v=1&tag_id=...&binding=...&token=...`

Unsupported NFC environments never return mock success. A manual payload can be supplied for
debugging, but it follows the same parser and real server request.

Users may report an ACTIVE card lost. Replacement issuance remains a staff operation, and the
old card becomes unusable after replacement.
