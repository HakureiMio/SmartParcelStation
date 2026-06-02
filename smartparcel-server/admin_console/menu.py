from __future__ import annotations

import httpx

from admin_console.api_client import ApiClient
from admin_console.db_ops import create_default_data
from admin_console.formatters import (
    GATEWAY_COLUMNS,
    NOTIFICATION_COLUMNS,
    PARCEL_COLUMNS,
    QUERY_COLUMNS,
    STATION_COLUMNS,
    SYNC_COLUMNS,
    USER_COLUMNS,
    format_gateway_result,
    format_notification_result,
    format_parcel_result,
    format_query_result,
    format_station_result,
    format_system_status,
    format_user_result,
)
from admin_console.render import print_block, print_rows


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f' [{default}]' if default is not None else ''
    value = input(f'{prompt}{suffix}: ').strip()
    return value or (default or '')


def pause() -> None:
    input('\n按 Enter 返回...')


def print_http_error(exc: httpx.HTTPStatusError) -> None:
    status_code = exc.response.status_code
    detail = ''
    try:
        body = exc.response.json()
        detail = body.get('detail', '')
    except Exception:
        detail = exc.response.text
    suffix = f'，原因：{detail}' if detail else ''
    print(f'操作失败：接口返回 {status_code}{suffix}')


class Menu:
    def __init__(self, client: ApiClient):
        self.client = client

    def run(self) -> None:
        while True:
            print(
                '\nSmartParcel 服务器终端面板\n'
                '1 系统状态\n'
                '2 用户管理\n'
                '3 站点管理\n'
                '4 网关管理\n'
                '5 中心包裹记录\n'
                '6 用户查询与通知记录\n'
                '7 同步事件审计\n'
                '8 异常处理\n'
                '9 开发测试工具\n'
                '0 主面板 / 返回上一级\n'
                'exit 退出面板'
            )
            choice = input('> ').strip().lower()
            try:
                if choice == 'exit':
                    return
                if choice == '1':
                    self.system_status()
                elif choice == '2':
                    self.user_menu()
                elif choice == '3':
                    self.station_menu()
                elif choice == '4':
                    self.gateway_menu()
                elif choice == '5':
                    self.parcel_menu()
                elif choice == '6':
                    self.query_menu()
                elif choice == '7':
                    self.sync_menu()
                elif choice == '8':
                    self.exception_menu()
                elif choice == '9':
                    self.dev_menu()
                elif choice == '0':
                    continue
                else:
                    print('请输入有效数字，或输入 exit 退出。')
            except httpx.HTTPStatusError as exc:
                print_http_error(exc)
            except httpx.HTTPError as exc:
                print(f'操作失败：无法连接服务端或请求超时。{exc}')
            except Exception as exc:
                print(f'操作失败：{exc}')

    def system_status(self) -> None:
        lines = format_system_status(self.client.api_base, self.client.get('/health'), self.client.get('/version'))
        print_block('系统状态', lines)
        pause()

    def user_menu(self) -> None:
        print('\n1 查看用户列表\n2 创建默认测试用户\n3 创建单个用户\n4 启用/禁用用户\n5 修改用户角色\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get('/users', auth=True), ['id', 'display_name', 'phone', 'role', 'is_active'], USER_COLUMNS)
        elif choice == '2':
            rows = self.client.post('/dev/default-users', bootstrap=True)
            print('默认测试用户创建完成。')
            print_rows(rows, ['id', 'display_name', 'phone', 'role', 'is_active'], USER_COLUMNS)
        elif choice == '3':
            payload = {
                'display_name': ask('显示名称'),
                'phone': ask('手机号', ''),
                'role': ask('角色', 'USER'),
                'station_id': int(ask('站点ID', '1')),
            }
            user = self.client.post('/users', payload, auth=True)
            print(format_user_result(user, '用户创建成功'))
        elif choice == '4':
            user_id = ask('用户ID')
            is_active = ask('是否启用 true/false', 'true').lower() == 'true'
            user = self.client.patch(f'/users/{user_id}', {'is_active': is_active})
            action = '用户已启用' if is_active else '用户已禁用'
            print(format_user_result(user, action))
        elif choice == '5':
            user_id = ask('用户ID')
            user = self.client.patch(f'/users/{user_id}', {'role': ask('角色', 'USER')})
            print(format_user_result(user, '用户角色已更新'))
        pause()

    def station_menu(self) -> None:
        print('\n1 查看站点\n2 创建默认站点 ST001\n3 创建站点\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get('/stations', auth=True), ['id', 'station_code', 'name', 'status'], STATION_COLUMNS)
        elif choice == '2':
            station = self.client.post('/stations', {'station_code': 'ST001', 'name': '主站点', 'address': '示例路 1 号', 'status': 'ACTIVE'}, auth=True)
            print(format_station_result(station))
        elif choice == '3':
            payload = {'station_code': ask('站点编码'), 'name': ask('站点名称'), 'address': ask('站点地址'), 'status': ask('状态', 'ACTIVE')}
            station = self.client.post('/stations', payload, auth=True)
            print(format_station_result(station))
        pause()

    def gateway_menu(self) -> None:
        print('\n1 查看网关\n2 注册默认网关 GW001\n3 查看网关心跳状态\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get('/gateways', auth=True), ['id', 'gateway_code', 'station_id', 'status', 'last_seen_at'], GATEWAY_COLUMNS)
        elif choice == '2':
            gateway = self.client.post('/gateways/register', {'gateway_code': 'GW001', 'station_id': 1, 'device_secret_hash': 'gw-secret-demo', 'status': 'ACTIVE'}, bootstrap=True)
            print(format_gateway_result(gateway))
        elif choice == '3':
            print_rows(self.client.get('/gateways', auth=True), ['gateway_code', 'status', 'last_seen_at'], GATEWAY_COLUMNS)
        pause()

    def parcel_menu(self) -> None:
        print('\n1 服务器手动预录入快递\n2 查看包裹列表\n3 按快递号查询\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            payload = {
                'parcel_code': ask('快递号'),
                'pickup_code': ask('取件码', ''),
                'receiver_user_id': int(ask('收件用户ID', '2')),
                'receiver_phone': ask('收件手机号', ''),
                'receiver_name_masked': ask('收件人脱敏名称', ''),
                'station_id': int(ask('站点ID', '1')),
            }
            parcel = self.client.post('/parcels', payload, auth=True)
            print(format_parcel_result(parcel, '快递预录入成功'))
        elif choice == '2':
            print_rows(self.client.get('/parcels', auth=True), ['id', 'parcel_code', 'status', 'origin', 'sync_status'], PARCEL_COLUMNS)
        elif choice == '3':
            parcel = self.client.get(f"/parcels/by-code/{ask('快递号')}", auth=True)
            print(format_parcel_result(parcel, '查询到快递'))
        pause()

    def query_menu(self) -> None:
        print('\n1 按用户查看待取件\n2 查看通知记录\n3 标记通知已读\n4 按快递号/取件信息查询\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get(f"/users/{ask('用户ID', '2')}/pickup-list"), ['id', 'parcel_code', 'status', 'origin'], PARCEL_COLUMNS)
        elif choice == '2':
            print_rows(self.client.get('/notifications', auth=True), ['id', 'user_id', 'parcel_id', 'title', 'status'], NOTIFICATION_COLUMNS)
        elif choice == '3':
            notification = self.client.post(f"/notifications/{ask('通知ID')}/read", auth=True)
            print(format_notification_result(notification))
        elif choice == '4':
            key = ask('查询条件，例如 parcel_code=P001')
            rows = format_query_result(self.client.get(f'/parcel-query?{key}'))
            print_rows(rows, ['id', 'parcel_code', 'status', 'origin', 'receiver_phone_masked'], QUERY_COLUMNS)
        pause()

    def sync_menu(self) -> None:
        print_rows(self.client.get('/sync-events', auth=True), ['id', 'event_type', 'direction', 'status', 'created_at'], SYNC_COLUMNS)
        pause()

    def exception_menu(self) -> None:
        rows = [row for row in self.client.get('/parcels', auth=True) if row.get('status') in {'CONFLICT', 'EXCEPTION'} or row.get('sync_status') == 'CONFLICT']
        print_rows(rows, ['id', 'parcel_code', 'status', 'sync_status'], PARCEL_COLUMNS)
        pause()

    def dev_menu(self) -> None:
        print('\n1 创建默认测试数据\n2 检查默认数据\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            create_default_data(self.client)
            print('默认测试数据初始化完成：默认用户、站点 ST001、网关 GW001 已检查。')
        elif choice == '2':
            print('\n默认用户：')
            print_rows(self.client.get('/users', auth=True), ['id', 'display_name', 'role', 'is_active'], USER_COLUMNS)
            print('\n默认站点：')
            print_rows(self.client.get('/stations', auth=True), ['id', 'station_code', 'status'], STATION_COLUMNS)
            print('\n默认网关：')
            print_rows(self.client.get('/gateways', auth=True), ['id', 'gateway_code', 'status'], GATEWAY_COLUMNS)
        pause()
