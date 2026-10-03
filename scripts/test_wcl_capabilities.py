#!/usr/bin/env python3
"""Compile the production capability getter with a minimal HAL for regression checks."""

from pathlib import Path
import re
import subprocess
import tempfile


root = Path(__file__).resolve().parents[1]
source = (root / "AirportItlwm/AirportItlwmV2.cpp").read_text()
apple = (root / "include/Airport/apple80211_var.h").read_text()
ioctl = (root / "include/Airport/apple80211_ioctl.h").read_text()
net = (root / "itl80211/openbsd/net80211/ieee80211_var.h").read_text()


def extract(pattern, text):
    match = re.search(pattern, text, re.S)
    if not match:
        raise RuntimeError(f"Production declaration not found: {pattern}")
    return match.group(0)


getter = extract(r"IOReturn AirportItlwm::\s*getCARD_CAPABILITIES\(.*?\n\}", source)
cap_enum = extract(r"enum apple80211_card_capability\s*\{.*?\};", apple)
cap_struct = extract(r"struct apple80211_capability_data\s*\{.*?\};", ioctl)
net_caps = "\n".join(re.findall(r"^#define\s+IEEE80211_C_\w+[^\n]*", net, re.M))
version = re.search(r"^#define APPLE80211_VERSION[^\n]*", ioctl, re.M).group(0)

harness = r"""
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <sys/types.h>
#define AIRPORT_WCL 1
using IOReturn = unsigned;
constexpr IOReturn kIOReturnSuccess = 0;
struct OSObject {};
""" + cap_enum + "\n" + cap_struct + "\n" + net_caps + "\n" + version + r"""
struct Controller { uint32_t ic_caps; };
struct HAL {
    Controller controller;
    Controller *get80211Controller() { return &controller; }
};
struct AirportItlwm {
    HAL *fHalService;
    IOReturn getCARD_CAPABILITIES(OSObject *, apple80211_capability_data *);
};
""" + getter + r"""
static bool bit(const apple80211_capability_data &data, unsigned n) {
    return data.capabilities[n / 8] & (1U << (n % 8));
}
int main() {
    HAL hal = {};
    AirportItlwm driver = {&hal};
    apple80211_capability_data data;
    // Exercise reuse of the same output buffer as capabilities disappear.
    const uint32_t cases[] = {IEEE80211_C_RSN, 0xffffffffU, 0, IEEE80211_C_WEP};
    for (uint32_t caps : cases) {
        hal.controller.ic_caps = caps;
        memset(&data, 0xff, sizeof(data));
        assert(driver.getCARD_CAPABILITIES(nullptr, &data) == kIOReturnSuccess);
        assert(data.version == APPLE80211_VERSION);
        bool rsn = caps & IEEE80211_C_RSN;
        // Apple80211 checks the group cipher even with CCMP unicast traffic.
        assert(bit(data, APPLE80211_CAP_TKIP) == rsn);
        assert(bit(data, APPLE80211_CAP_TKIPMIC) == rsn);
        assert(bit(data, APPLE80211_CAP_AES_CCM) == rsn);
        assert(bit(data, APPLE80211_CAP_WPA2) == rsn);
        assert(!bit(data, APPLE80211_CAP_WPA1));
        assert(!bit(data, APPLE80211_CAP_WEP));
        // The fix must not advertise PMF or SAE.
        assert(data.capabilities[6] == 0);
        assert(data.capabilities[9] == 0);
    }
    puts("WCL cipher capability regression checks passed (4 HAL configurations)");
}
"""

with tempfile.TemporaryDirectory(prefix="itlwm-wcl-caps-") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(harness)
    subprocess.run(["xcrun", "clang++", "-std=c++11", "-Wall", "-Wextra",
                    "-Wno-unused-parameter", str(path / "test.cpp"),
                    "-o", str(path / "test")], check=True)
    subprocess.run([str(path / "test")], check=True)
