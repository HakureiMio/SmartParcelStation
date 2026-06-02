from datetime import datetime, timedelta, timezone

from admin_console.formatters import format_gateway_rows, gateway_display_status


def test_gateway_display_status_online_when_heartbeat_is_fresh():
    last_seen_at = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    assert gateway_display_status({'status': 'ONLINE', 'last_seen_at': last_seen_at}, timeout_seconds=120) == '在线'


def test_gateway_display_status_offline_when_heartbeat_is_stale():
    last_seen_at = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    assert gateway_display_status({'status': 'ONLINE', 'last_seen_at': last_seen_at}, timeout_seconds=120) == '离线（心跳超时）'


def test_gateway_rows_only_change_display_status():
    rows = [{'gateway_code': 'GW001', 'status': 'ACTIVE', 'last_seen_at': None}]
    formatted = format_gateway_rows(rows, timeout_seconds=120)
    assert formatted[0]['status'] == '未连接'
    assert rows[0]['status'] == 'ACTIVE'
