from __future__ import annotations

import httpx

from admin_console.api_client import ApiClient
from admin_console.db_ops import create_default_data
from admin_console.render import print_rows


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f' [{default}]' if default is not None else ''
    value = input(f'{prompt}{suffix}: ').strip()
    return value or (default or '')


def pause() -> None:
    input('\nPress Enter to continue...')


class Menu:
    def __init__(self, client: ApiClient):
        self.client = client

    def run(self) -> None:
        while True:
            print(
                '\nSmartParcel Server Panel\n'
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
            except httpx.HTTPError as exc:
                print(f'API 调用失败: {exc}')
            except Exception as exc:
                print(f'操作失败: {exc}')

    def system_status(self) -> None:
        print(f'API_BASE_URL={self.client.api_base}')
        print(self.client.get('/health'))
        print(self.client.get('/version'))
        pause()

    def user_menu(self) -> None:
        print('\n1 查看用户列表\n2 创建默认测试用户\n3 创建单个用户\n4 启用/禁用用户\n5 修改用户角色\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get('/users'), ['id', 'display_name', 'phone', 'role', 'is_active'])
        elif choice == '2':
            print_rows(self.client.post('/dev/default-users'), ['id', 'display_name', 'phone', 'role', 'is_active'])
        elif choice == '3':
            payload = {
                'display_name': ask('display_name'),
                'phone': ask('phone', ''),
                'role': ask('role', 'USER'),
                'station_id': int(ask('station_id', '1')),
            }
            print(self.client.post('/users', payload, auth=True))
        elif choice == '4':
            user_id = ask('user_id')
            is_active = ask('is_active true/false', 'true').lower() == 'true'
            print(self.client.patch(f'/users/{user_id}', {'is_active': is_active}))
        elif choice == '5':
            user_id = ask('user_id')
            print(self.client.patch(f'/users/{user_id}', {'role': ask('role', 'USER')}))
        pause()

    def station_menu(self) -> None:
        print('\n1 查看站点\n2 创建默认站点 ST001\n3 创建站点\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get('/stations'), ['id', 'station_code', 'name', 'status'])
        elif choice == '2':
            print(self.client.post('/stations', {'station_code': 'ST001', 'name': '主站点', 'address': '示例路 1 号', 'status': 'ACTIVE'}, auth=True))
        elif choice == '3':
            payload = {'station_code': ask('station_code'), 'name': ask('name'), 'address': ask('address'), 'status': ask('status', 'ACTIVE')}
            print(self.client.post('/stations', payload, auth=True))
        pause()

    def gateway_menu(self) -> None:
        print('\n1 查看网关\n2 注册默认网关 GW001\n3 查看网关心跳状态\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get('/gateways'), ['id', 'gateway_code', 'station_id', 'status', 'last_seen_at'])
        elif choice == '2':
            print(self.client.post('/gateways/register', {'gateway_code': 'GW001', 'station_id': 1, 'device_secret_hash': 'gw-secret-demo', 'status': 'ACTIVE'}))
        elif choice == '3':
            print_rows(self.client.get('/gateways'), ['gateway_code', 'status', 'last_seen_at'])
        pause()

    def parcel_menu(self) -> None:
        print('\n1 服务器手动预录入快递\n2 查看包裹列表\n3 按 parcel_code 查询\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            payload = {
                'parcel_code': ask('parcel_code'),
                'pickup_code': ask('pickup_code', ''),
                'receiver_user_id': int(ask('receiver_user_id', '2')),
                'receiver_phone': ask('receiver_phone', ''),
                'receiver_name_masked': ask('receiver_name_masked', ''),
                'station_id': int(ask('station_id', '1')),
            }
            print(self.client.post('/parcels', payload, auth=True))
        elif choice == '2':
            print_rows(self.client.get('/parcels'), ['id', 'parcel_code', 'status', 'origin', 'sync_status'])
        elif choice == '3':
            print(self.client.get(f"/parcels/by-code/{ask('parcel_code')}"))
        pause()

    def query_menu(self) -> None:
        print('\n1 按用户查看待取件\n2 查看通知记录\n3 标记通知已读\n4 按快递号/取件信息查询\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            print_rows(self.client.get(f"/users/{ask('user_id', '2')}/pickup-list"), ['id', 'parcel_code', 'status', 'origin'])
        elif choice == '2':
            print_rows(self.client.get('/notifications'), ['id', 'user_id', 'parcel_id', 'title', 'status'])
        elif choice == '3':
            print(self.client.post(f"/notifications/{ask('notification_id')}/read"))
        elif choice == '4':
            key = ask('query string, example parcel_code=P001')
            print(self.client.get(f'/parcel-query?{key}'))
        pause()

    def sync_menu(self) -> None:
        print_rows(self.client.get('/sync-events'), ['id', 'event_type', 'direction', 'status', 'created_at'])
        pause()

    def exception_menu(self) -> None:
        rows = [row for row in self.client.get('/parcels') if row.get('status') in {'CONFLICT', 'EXCEPTION'} or row.get('sync_status') == 'CONFLICT']
        print_rows(rows, ['id', 'parcel_code', 'status', 'sync_status'])
        pause()

    def dev_menu(self) -> None:
        print('\n1 创建默认测试数据\n2 检查默认数据\n0 返回')
        choice = input('> ').strip()
        if choice == '1':
            create_default_data(self.client)
            print('default users, ST001 and GW001 checked')
        elif choice == '2':
            print_rows(self.client.get('/users'), ['id', 'display_name', 'role', 'is_active'])
            print_rows(self.client.get('/stations'), ['id', 'station_code', 'status'])
            print_rows(self.client.get('/gateways'), ['id', 'gateway_code', 'status'])
        pause()
