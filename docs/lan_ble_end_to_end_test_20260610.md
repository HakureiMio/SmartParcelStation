# 局域网 BLE 标签闭环测试记录 2026-06-10

## 1. 测试目标

本次测试验证以下链路在同一局域网内可用：

```text
smartparcel-server
  -> smartparcel-miniprogram 登录与员工端页面
  -> smartparcel-gateway local API
  -> BLE_BACKEND=real
  -> nRF52810 智能寻物标签
  -> RGB LED / 蜂鸣器
```

## 2. 测试环境

```text
server：smartparcel-server，FastAPI，端口 18000
gateway：smartparcel-gateway local API，端口 19000
miniprogram：微信小程序员工端
tag：nRF52810 标签，BLE name = SPS-F01-20260610-0001
gateway 标签编号：SPS-TAG-0002
```

小程序、server、gateway 位于同一局域网环境。真实 BLE 控制使用：

```env
BLE_BACKEND=real
```

## 3. 成功证据

server 登录接口返回成功：

```text
127.0.0.1:8799 - "POST /api/v1/auth/login HTTP/1.1" 200 OK
```

gateway 标签详情接口返回成功：

```text
INFO:     127.0.0.1:14953 - "GET /local/tags/SPS-TAG-0002 HTTP/1.1" 200 OK
```

小程序员工端可以完成：

```text
登录
进入 BLE 标签管理
查看真实 gateway 状态
选择真实标签 SPS-TAG-0002
发送 wake
标签 RGB LED 亮灯
标签蜂鸣器发声
发送 stop
标签停止提醒
```

## 4. 本次遇到的问题与解决方式

### 4.1 nRF52810 BLE RAM 溢出

现象：

```text
region `RAM' overflowed by 2156 bytes
```

解决：

在 `clip-node-nrf52810/prj.conf` 中降低部分 RAM 占用，包括主线程栈、heap、日志缓冲、日志线程栈、系统工作队列栈，并关闭 `CONFIG_ASSERT`。修改后固件可编译和烧录。

注意：

```text
clip-node-nrf52810 必须使用 nRF Connect SDK / Nordic Toolchain Terminal 编译。
不要使用 smartparcel-gateway/.venv 中的 Python 或 west 编译 nRF 固件。
```

### 4.2 OpenOCD 烧录路径混淆

现象：

最初不确定应烧录 `build/zephyr/merged.hex` 还是 `build/merged.hex`。

解决：

当前 sysbuild 产物位于：

```text
clip-node-nrf52810/build/merged.hex
```

在 `clip-node-nrf52810` 目录下使用：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; program build/merged.hex verify reset; shutdown"
```

### 4.3 低电平有效蜂鸣器上电就叫

现象：

低电平有效蜂鸣器一插电就响。

原因：

固件原先按高电平有效无源蜂鸣器处理，同时保留了启动时拉低 P0.16 的烧录测试逻辑。

解决：

将 `buzzer_pwm` 改为反相 PWM：

```dts
PWM_POLARITY_INVERTED
```

并移除启动时强制拉低 P0.16 的测试代码。修改后逻辑为：

```text
空闲 / stop：非触发态
wake / alert：低电平有效 PWM
```

硬件建议：

低电平有效蜂鸣器控制脚建议增加上拉电阻，避免 MCU 复位和启动早期引脚悬空导致误响。

### 4.4 标签每次发送指令后需要重新上电

现象：

第一次 `wake` 有反应，后续再次发送指令需要重新上电才有反应。

原因：

gateway real BLE 当前采用短连接方式发送命令。标签断开连接后，固件没有显式重新启动可连接广播，导致下一次连接不稳定。

解决：

在 `ble_clip_service.c` 的 `disconnected` 回调中重新启动广播：

```c
disconnected -> start_advertising()
```

修改后应按以下顺序复测：

```text
wake -> stop -> wake -> stop
```

不再需要重新上电即为通过。

### 4.5 注册后真实标签编号变化导致控制错对象

现象：

注册真实标签后返回：

```text
tag_id = SPS-TAG-0002
ble_address = CB:D7:0B:75:B8:27
```

但测试时误调用了：

```text
/local/tags/SPS-TAG-0001/wake
```

结果控制的是旧 mock 标签记录，真实硬件无反应。

解决：

查看标签列表和详情，确认真实硬件对应：

```text
SPS-TAG-0002
```

真实控制命令应使用：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:19000/local/tags/SPS-TAG-0002/wake `
  -ContentType "application/json" `
  -Body '{"color":"BLUE","duration_sec":10}'
```

### 4.6 小程序 mock fallback 干扰真实联调判断

现象：

小程序页面存在大量 mock fallback。gateway 或 server 请求失败时，页面仍可能显示 mock 成功，导致难以判断真实连接状态。

解决：

将全局配置改为：

```js
useMockWhenRequestFail: false
```

同时在 BLE 标签管理页明确显示：

```text
网关在线 / 网关不可用
真实网关 / Mock 演示 / 错误
lastError
完整调试 JSON
```

登录接口单独保留 mock fallback，避免 server 未启动时无法进入演示员工端；BLE 标签接口不再静默回退到 mock。

### 4.7 关闭 mock fallback 后员工账号登录失败

现象：

`staff001 / 123456` 显示账号密码错误。

原因：

全局关闭 mock fallback 后，如果 server 未启动、登录 API 不通，或 server 数据库未种默认账号，小程序不会再使用演示账号兜底。

解决：

为 `auth-api.js` 的登录、注册、忘记密码请求单独开启：

```js
useMockWhenRequestFail: true
```

BLE 标签接口继续保持真实失败可见。

### 4.8 SQLite 旧表结构缺少 local_tags.tag_uid

现象：

gateway 报错：

```text
sqlite3.OperationalError: no such column: local_tags.tag_uid
```

原因：

当前代码模型新增了 `tag_uid`、`local_no`、`display_name`、`ble_name`、`ble_address` 等字段，但旧 SQLite 数据库未执行兼容迁移。

解决：

`gateway.local_api` 启动时自动执行 `init_db()`，并对当前异常的 `gateway.db` 做备份、恢复和补列。修复后：

```text
GET /local/tags -> 200
SQLite quick_check -> ok
```

## 5. 当前推荐复测流程

### 5.1 启动 server

```powershell
cd smartparcel-server
.\.venv\Scripts\activate
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

### 5.2 启动 gateway real BLE

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
$env:BLE_BACKEND="real"
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

### 5.3 小程序配置

开发者工具运行在同一台电脑上时：

```js
gatewayBaseUrl: 'http://127.0.0.1:19000'
```

真机调试时：

```js
gatewayBaseUrl: 'http://网关局域网IP:19000'
```

真实联调建议：

```js
useMockWhenRequestFail: false
```

### 5.4 员工端操作

```text
员工登录 staff001 / 123456
进入 BLE 标签管理
确认数据来源为 真实网关
选择 SPS-TAG-0002
点击蓝色亮灯/蜂鸣
观察 RGB LED 与蜂鸣器
点击停止
重复 wake / stop
```

## 6. 当前结论

本次测试确认：

```text
server 登录接口可用
gateway local API 可用
小程序可访问 gateway
gateway 可通过 BLE_BACKEND=real 控制真实 nRF52810 标签
标签 RGB LED 和蜂鸣器可响应小程序操作
```

当前三端一标签闭环已经跑通。后续重点是稳定多次连接、完善小程序真实状态提示、补充多标签场景和门禁流程迁移到 real BLE。

## 7. 后续进展记录

### 7.1 小程序 BLE 页面操作后卡死

现象：

```text
小程序员工端进入 BLE 标签管理。
点击 wake / stop / status 等控制按钮后，当前页面按钮进入 loading/disabled 状态。
页面不再响应后续标签控制。
必须退回前一级，再重新进入 BLE 标签管理页面才能继续操作。
```

原因判断：

```text
1. BLE 控制请求可能耗时超过原先 requestTimeoutMs=1500。
2. 页面依赖 Promise.finally() 释放 loading/scanning 状态，在小程序运行环境或异常请求场景下不够稳。
3. wx.request 如果没有按预期进入 success/fail 分支，页面状态可能一直停在 loading=true。
```

解决：

```text
1. smartparcel-miniprogram/services/config.js
   将 requestTimeoutMs 从 1500 调整为 12000。

2. smartparcel-miniprogram/services/request.js
   增加请求兜底超时，保证请求最终 resolve。

3. smartparcel-miniprogram/pages/staff-ble-tags/staff-ble-tags.js
   移除对 Promise.finally() 的依赖。
   在 scan/register/runAction 的成功、失败和 catch 分支中显式恢复：
   loading=false
   scanning=false
```

验证结果：

```text
小程序重新编译后复测通过。
执行标签控制后页面没有再次卡死。
可以继续在同一页面重复执行 wake / stop / status。
```

### 7.2 BLE 连接稳定性继续观察

当前已做的稳定性处理：

```text
1. nRF52810 固件在 BLE disconnected 后延迟重启 advertising。
2. advertising 重启失败后每 500ms 自动重试。
3. gateway real BLE 写 GATT 命令改为 response=True。
4. gateway 写入命令后等待 0.2s 再退出连接上下文。
```

仍需继续观察：

```text
1. 连续多次 wake -> stop -> wake -> stop 是否稳定。
2. 小程序连续控制是否会导致标签再次进入 ERROR。
3. Windows BLE 栈是否偶发保留旧连接状态。
4. 是否需要后续把 gateway 改为短时保持 BLE 长连接，而不是每条命令都新建连接。
```

### 7.3 当前可视化状态改进

小程序 BLE 标签管理页当前已经明确显示：

```text
网关在线 / 网关不可用
真实网关 / Mock 演示 / 错误
lastError
完整调试 JSON
```

当前真实联调建议保持：

```js
useMockWhenRequestFail: false
```

登录接口单独允许 mock fallback，避免 server 未启动时无法进入演示员工端；BLE 标签管理接口不再静默回退到 mock，避免误判真实硬件状态。

## 8. 当前总体状态

截至本次记录，已确认：

```text
server 可完成员工登录。
gateway local API 可读取真实标签详情。
小程序可进入员工端 BLE 标签管理。
小程序可控制真实 nRF52810 标签亮灯和蜂鸣。
小程序连续操作后页面不再卡死。
```

仍需后续回归：

```text
1. 重新烧录包含 BLE advertising 重试逻辑和低电平有效蜂鸣器逻辑的最新固件。
2. 复测连续 wake / stop 多轮控制。
3. 验证标签断开后是否无需重新上电即可再次控制。
4. 记录真实标签 ERROR 的具体 gateway result.message 和 RTT 日志。
```
