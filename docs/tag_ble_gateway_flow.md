# 标签 BLE 与网关闭环流程

## 第一阶段链路

```text
smartparcel-miniprogram 员工端
  -> wx.request 局域网调用
  -> smartparcel-gateway FastAPI local API
  -> BLE_BACKEND mock/real 服务
  -> nRF52810 标签 GATT Service
  -> RGB LED / buzzer
```

本阶段只验证“员工小程序 -> 局域网 gateway -> BLE 标签 -> RGB LED / buzzer”的最小硬件闭环，不实现云端远程控制、完整取件流程、生产 HTTPS 或小程序正式发布域名配置。

## 标签命名规范

真实标签推荐使用出厂 BLE 名称作为唯一识别信息：

```text
SPS-F01-20260610-0001
```

格式为：

```text
SPS-{factory_code}-{production_date}-{serial_no}
```

示例：

```text
SPS-F01-20260610-0001
SPS-F01-20260610-0002
SPS-F02-20260611-0001
```

gateway 第一阶段同时兼容旧测试名称 `SPS-TAG-0001`。标签注册到某个 gateway 后，再由 gateway 分配本地编号：

```text
tag_id = SPS-TAG-0001
display_name = 标签 001
```

员工端普通列表显示 `标签 001`；详情页显示本地编码 `SPS-TAG-0001`、出厂唯一名称、BLE 地址、状态、电池电压、最后发现时间和最后连接时间。

## gateway 启动命令

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main init-db
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

没有硬件时使用：

```env
BLE_BACKEND=mock
```

真实 BLE 联调时使用：

```env
BLE_BACKEND=real
```

`real` 后端通过 `bleak` 扫描标签，并向 `CMD_WRITE` characteristic 写入 `WAKE_TAG`、`STOP_ALERT`、`READ_STATUS` 协议帧。

## 小程序真机局域网调试

`services/config.js` 默认配置为：

```js
gatewayBaseUrl: 'http://127.0.0.1:19000'
```

在真机上，`127.0.0.1` 是手机本机，不是电脑或 gateway。真机调试时需要改为 gateway 的局域网 IP：

```js
gatewayBaseUrl: 'http://192.168.x.x:19000'
```

员工手机和 gateway 必须连接同一 Wi-Fi 或同一局域网。

## 固件烧录后检查

烧录 nRF52810 标签固件后，在日志中确认 BLE 广播名称：

```text
BLE name: SPS-F01-20260610-0001
```

第一阶段先写死一个测试名称。后续真实批量生产时，每个标签应烧录不同的出厂 BLE 名称，或通过 NVS/产测工具写入唯一出厂信息。

## 最小测试流程

1. 启动 `smartparcel-gateway` local API。
2. 设置 `BLE_BACKEND=mock`，打开小程序员工端 -> BLE 标签管理。
3. 执行 扫描 -> 注册 -> 连接 -> 蓝色亮灯/蜂鸣 -> 停止 -> 读取状态。
4. 设置 `BLE_BACKEND=real`，烧录并上电真实标签。
5. 将小程序 `gatewayBaseUrl` 指向 gateway 局域网 IP。
6. 重复 扫描附近标签 -> 注册标签 -> 连接 -> 亮灯/蜂鸣 -> 停止 -> 读取状态。

`WAKE_TAG` 会让 RGB LED 和 buzzer 进入寻物提醒；`STOP_ALERT` 会立即停止提醒。没有真实硬件时，mock 后端仍能完整演示页面和 API 流程。
