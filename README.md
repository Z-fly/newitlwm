# AirportItlwm for Tahoe

适用于 **macOS Tahoe 26.x（x86_64）** 的 Intel Wi-Fi 驱动，基于 [OpenIntelWireless/itlwm](https://github.com/OpenIntelWireless/itlwm)。通过 macOS 原生 Wi-Fi 菜单扫描和连接网络，无需 HeliPort。

本分支只编译、发布 **Tahoe** 版本。

## 下载与安装

从[本仓库 Releases](https://github.com/laobamac/itlwm/releases) 下载 `AirportItlwm-Tahoe-…-RELEASE-…zip`。日常使用选 **Release**，排查问题选 **Debug**。

1. 解压得到 `AirportItlwm.kext`，放入 `EFI/OC/Kexts/`。
2. 在 OpenCore `config.plist` 的 `Kernel → Add` 中添加或更新对应条目并启用。
3. 替换旧版本，确保只启用这一份 AirportItlwm，且不同时加载 `itlwm.kext`；重启后通过系统 Wi-Fi 菜单连接。

**Wi-Fi 6 默认开启，不需要添加 `itlwm_he=1`。**

## 功能与限制

- 支持系统 Wi-Fi 列表、连接、网络切换和私有 Wi-Fi 地址。
- 支持兼容网卡的 802.11ax（HE / Wi-Fi 6）；频宽、空间流和速率由网卡与路由器共同决定。系统显示的 Tx Rate 是无线连接速率，不等于文件下载速度。
- 支持 WPA2-Personal，以及允许 WPA2 且 PMF 可选的 WPA2/WPA3 混合网络。
- 尚不支持 WPA3-only、强制 PMF、AWDL / AirDrop 和 MLO。

网卡型号可参考[上游兼容列表](https://openintelwireless.github.io/itlwm/Compat)。设备表沿用上游，但不代表每款网卡都已在 Tahoe 上完成实机验证。

## 可选启动参数

| 参数 | 作用 |
| --- | --- |
| `itlwm_he=0` | 关闭 Wi-Fi 6，用于兼容性排查 |
| `-novht` | 关闭 802.11ac 和 802.11ax |
| `-noht40` | 禁用 HT 40 MHz |

通常无需添加这些参数。

## 本地编译

需要 Xcode、Python 3，以及放在仓库根目录 `MacKernelSDK/` 下的 [MacKernelSDK](https://github.com/acidanthera/MacKernelSDK/tree/3f750085caa17ec3a7880f11c11bf4f48cd6a164)（版本与 [CI](.github/workflows/main.yml) 一致）。在仓库根目录执行：

```sh
xcodebuild -project itlwm.xcodeproj -scheme AirportItlwm-Tahoe \
  -configuration Release -jobs 3 ARCHS=x86_64 \
  SYMROOT="$PWD/build/products" OBJROOT="$PWD/build/obj" \
  CODE_SIGNING_ALLOWED=NO GIT_COMMIT="_$(git rev-parse --short HEAD)" build
```

产物：`build/products/Release/Tahoe/AirportItlwm.kext`。调试版将 `Release` 换为 `Debug`。

CI 只构建 Tahoe 的 Debug / Release；`main` 通过检查后自动更新 alpha 发布。

## 问题反馈

请在[本仓库 Issues](https://github.com/laobamac/itlwm/issues) 提供网卡型号、macOS 版本、驱动版本或提交号、复现步骤和日志。连接问题请注明频段及加密方式；掉速问题请注明下载来源与速度单位。

HE 日志可用 [scripts/collect_he.command](scripts/collect_he.command) 采集。它会查询 Wi-Fi 状态，可能触发扫描，测吞吐量时请在测速结束后运行。

## 来源与许可

感谢 [OpenIntelWireless 及其贡献者](https://github.com/OpenIntelWireless/itlwm#credits)、[OpenBSD](https://www.openbsd.org/)、Intel / Linux iwlwifi 和 [Acidanthera](https://github.com/acidanthera/MacKernelSDK)。

项目采用 [GPL-2.0](LICENSE)；第三方代码及固件遵循各自许可。
