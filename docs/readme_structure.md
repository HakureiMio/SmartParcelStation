# README 结构说明

## 1. 文档分层原则

根 `README.md` 只作为项目总入口，负责说明当前主线、项目结构、职责边界、最短启动流程和文档索引。

子项目 README 负责各自运行和调试：

```text
smartparcel-server/README.md：中心服务端、账号、站点、网关注册和同步审计。
smartparcel-gateway/README.md：本地网关、SQLite、local API、BLE_BACKEND=mock/real。
smartparcel-miniprogram/README.md：小程序页面、gatewayBaseUrl、真机调试。
clip-node-nrf52810/README.md：nRF52810 固件、GATT、编译、烧录和硬件联调。
```

`docs/` 存放细分流程和历史归档：

```text
docs/tag_ble_gateway_flow.md：当前 BLE 标签闭环详细流程。
docs/legacy_stage_a_mock_flow.md：历史阶段 A 和 mock NFC 流程。
docs/gateway_gate_access_flow.md：门禁读卡流程设计与当前状态。
```

## 2. 当前主线

当前主线固定为：

```text
员工微信小程序
  -> 局域网调用 smartparcel-gateway local API
  -> gateway 通过 BLE_BACKEND=mock/real 控制智能寻物标签
  -> nRF52810 标签 GATT Service
  -> RGB LED / 蜂鸣器
```

后续新增文档时，应先判断内容属于当前主线、子项目手册还是历史归档，避免根 README 再次变成混合手册。

## 3. 环境隔离原则

```text
smartparcel-gateway/.venv 只用于 gateway Python 项目。
clip-node-nrf52810 必须使用 nRF Connect SDK / Nordic Toolchain Terminal 编译。
不要使用 gateway .venv 中的 Python 或 west 编译 nRF 固件。
```

## 4. server 与 BLE 标签边界

server 不直接扫描、连接或控制 BLE 标签。标签注册、本地编号、BLE 地址、电量、最后连接时间和实时状态由 gateway 本地保存。

server 只接收：

```text
标签异常摘要
取件审计
门禁审计
网关同步审计
```
