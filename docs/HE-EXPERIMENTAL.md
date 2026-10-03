# Tahoe HE / Wi-Fi 6 实验支持

仅 AirportItlwm-Tahoe（WCL）支持通过 OpenCore 的 `boot-args` 添加
`itlwm_he=1` 启用实验性 802.11ax。默认关闭；`-novht` 优先于该参数。
移除 `itlwm_he=1` 并重启即可恢复原有行为。

## 范围

- iwx 后端、NVM 明确声明 11ax 能力、HE station context 命令 v1/v2 的 Intel 网卡。
  仓库内 12 个 68 系列固件均声明此命令 v2。AC8265 等 ac 网卡不会启用 HE。
- 2.4 GHz / 5 GHz，20/40/80 MHz；160 MHz 还要求硬件、对端能力和 MCS 交集允许。
- 单/双空间流由实际天线和 MIMO 限制决定。协商、TLC 速率和固件 HE context 都使用对端信息。
- 未实现 6 GHz、TWT 会话、OMI、Multi-BSSID、MLO 或 WPA3 新功能；本改动不宣称支持它们。
  TWT-required BSS、无共同 HE MCS 或缺少有效 HE 信息时不发送 HE capability IE。
- 保留原 HT/VHT 协商。只有发送过 HE capability、收到有效响应并完成 HE 协商后，才设置 HE 节点状态。
- Tahoe 当前 PHY 模式与扩展 BSS HE MCS 映射来自连接状态。HE SU 速率来自固件选定的
  MCS/NSS/BW/GI；缺少 RU 分配的 MU/TB 通知暂报速率未知。
- 原生 `getHE_CAPABILITY` 私有 ioctl 的完整字段布局尚未核实，继续返回 unsupported；
  本实验使用驱动自身的管理帧协商和 WCL 扩展 BSS 状态，不伪造该接口的数据。

## 实机验证

1. 保留可用的原 kext 和启动项。使用正常工作的 AX 网卡，先测试 Debug 版。
2. 替换 `AirportItlwm.kext`，添加 `itlwm_he=1`，重启。
3. 先连接 5 GHz、80 MHz、启用 Wi-Fi 6 的 WPA2-AES 网络。在路由器客户端页面核对
   802.11ax/HE，并产生持续收发流量（例如局域网 iperf3），观察断流/重连。
4. 再测试 2.4 GHz、160 MHz、普通 ac 路由器、关闭再打开 Wi-Fi、睡眠唤醒。
5. 出现无法加入或掉线时运行 `scripts/collect_he.command`。移除启动参数并重启，
   对比相同网络的 ac 行为。

完整 HE 证据链（Debug 日志）：

- `Experimental HE enabled: context-v2 ...`：硬件、参数、命令版本通过检查。
- `HE negotiated: ...`：协议层选中 HE。
- `HE context: version=2 ... result=0`：同步固件配置调用成功。
- `HE TLC: mode=3 ...`：速率控制配置为 HE。
- `iwx_rs_update new rate: ... HE ...`：固件实际报告 HE 发送速率。

仅出现“enabled”或系统显示 ax 不足以证明完整工作。80 MHz、2SS、MCS11、0.8 μs GI 的
理论 PHY 速率约 1201 Mbps；这不是实际吞吐量承诺，也不是 HE 成功的必要门槛。

## 已验证与未验证

`python3 scripts/test_he.py` 编译并运行生产函数，启用 AddressSanitizer / UndefinedBehaviorSanitizer，
检查所有 IE 截断点、随机输入、可选 MCS/PPE 字段、硬件/参数门控、加密限制、ac 回退、
对端速率交集、固件结构布局和已知 HE 速率。`scripts/test_wcl_capabilities.py` 保留 TKIP 回归。

本地编译和自动化测试不能证明无线电行为正确。连接稳定性、固件运行结果及系统界面展示仍需实机回报。

参考固件 ABI：Intel iwlwifi Linux v5.15 的 `fw/api/mac.h` / `mvm/mac80211.c`，
其中 HE context v1 为 80 字节，v2 为 88 字节。更多版本不会自动按已知布局下发。
