from __future__ import annotations

from admin_console.api_client import ApiClient


def create_default_data(client: ApiClient) -> None:
    client.post('/dev/default-users', bootstrap=True)
    stations = client.get('/stations', auth=True)
    if not any(row.get('station_code') == 'ST001' for row in stations):
        client.post(
            '/stations',
            {'station_code': 'ST001', 'name': '主站点', 'address': '示例路 1 号', 'status': 'ACTIVE'},
            auth=True,
        )
    client.post('/gateways/register', {'gateway_code': 'GW001', 'station_id': 1, 'device_secret_hash': 'gw-secret-demo', 'status': 'ACTIVE'}, bootstrap=True)
