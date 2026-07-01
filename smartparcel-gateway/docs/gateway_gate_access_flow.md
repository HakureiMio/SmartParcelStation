# Gateway gate-access flow

1. `sync-pull` applies server events to local credentials, parcels and bindings.
2. A gate reader authenticates with `X-Gate-Reader-Id` and `X-Gate-Reader-Token`.
3. `CARD_UID` resolves an ACTIVE local credential. QR and NFC confirmations arrive through
   `GATE_USER_AUTH_REQUESTED` and resolve the server-authenticated user ID.
4. `AccessControlService` checks local `WAITING_PICKUP` parcels, assigns one session color,
   wakes bound tags, records `gate_auth_sessions`, and queues a GRANTED or DENIED audit event.
5. Firmware polls the latest reader result or a specific QR session. Gateway—not server—makes
   the final local access decision.

Reader endpoints never accept the miniprogram/local-operator session token as reader credentials.
