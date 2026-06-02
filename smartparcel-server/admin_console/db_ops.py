from __future__ import annotations

from admin_console.api_client import ApiClient

DEFAULT_GATEWAY_SECRET = 'gw-secret-demo'


def create_default_data(client: ApiClient, gateway_secret: str = DEFAULT_GATEWAY_SECRET) -> None:
    client.post('/dev/default-users', bootstrap=True)
    stations = client.get('/stations', auth=True)
    if not any(row.get('station_code') == 'ST001' for row in stations):
        client.post(
            '/stations',
            {'station_code': 'ST001', 'name': '主站点', 'address': '示例路 1 号', 'status': 'ACTIVE'},
            auth=True,
        )
    client.post(
        '/gateways/register',
        {'gateway_code': 'GW001', 'station_id': 1, 'device_secret_hash': gateway_secret, 'status': 'ACTIVE'},
        bootstrap=True,
    )
