from __future__ import annotations

from typing import Any


USER_COLUMNS = {
    'id': '用户ID',
    'display_name': '显示名称',
    'phone': '手机号',
    'role': '角色',
    'is_active': '启用',
}

STATION_COLUMNS = {
    'id': '站点ID',
    'station_code': '站点编码',
    'name': '站点名称',
    'status': '状态',
}

GATEWAY_COLUMNS = {
    'id': '网关ID',
    'gateway_code': '网关编码',
    'station_id': '站点ID',
    'status': '状态',
    'last_seen_at': '最近心跳',
}

PARCEL_COLUMNS = {
    'id': '包裹ID',
    'parcel_code': '快递号',
    'status': '业务状态',
    'origin': '来源',
    'sync_status': '同步状态',
}

NOTIFICATION_COLUMNS = {
    'id': '通知ID',
    'user_id': '用户ID',
    'parcel_id': '包裹ID',
    'title': '标题',
    'status': '状态',
}

SYNC_COLUMNS = {
    'id': '事件ID',
    'event_type': '事件类型',
    'direction': '方向',
    'status': '状态',
    'created_at': '创建时间',
}


def format_system_status(api_base: str, health: dict[str, Any], version: dict[str, Any]) -> list[str]:
    status_text = '正常' if health.get('status') == 'ok' else f"异常：{health.get('status', '未知')}"
    return [
        f'服务端连接地址：{api_base}',
        f'服务状态：{status_text}',
        f"应用名称：{version.get('app', '-')}",
        f"当前版本：{version.get('version', '-')}",
    ]


def format_user_result(user: dict[str, Any], action: str) -> str:
    return f"{action}：{user.get('id', '-')} / {user.get('display_name', '-')} / {user.get('role', '-')}"


def format_station_result(station: dict[str, Any]) -> str:
    return f"站点创建成功：{station.get('station_code', '-')} / {station.get('name', '-')}"


def format_gateway_result(gateway: dict[str, Any]) -> str:
    return f"网关注册成功：{gateway.get('gateway_code', '-')}，当前状态：{gateway.get('status', '-')}"


def format_parcel_result(parcel: dict[str, Any], action: str = '包裹操作完成') -> str:
    return (
        f"{action}：{parcel.get('parcel_code', '-')}，"
        f"业务状态：{parcel.get('status', '-')}，来源：{parcel.get('origin', '-')}"
    )


def format_notification_result(notification: dict[str, Any]) -> str:
    return f"通知已标记为已读：通知ID {notification.get('id', '-')}，状态：{notification.get('status', '-')}"


def format_query_result(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'id': row.get('id'),
            'parcel_code': row.get('parcel_code'),
            'status': row.get('status'),
            'origin': row.get('origin'),
            'receiver_phone_masked': row.get('receiver_phone_masked'),
        }
        for row in rows
    ]


QUERY_COLUMNS = {
    'id': '包裹ID',
    'parcel_code': '快递号',
    'status': '业务状态',
    'origin': '来源',
    'receiver_phone_masked': '收件手机号',
}
