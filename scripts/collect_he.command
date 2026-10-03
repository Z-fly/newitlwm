#!/bin/bash
# Read-only collection for the experimental HE build. Run after the test.
set -u
out_dir="$HOME/Desktop/airport-he-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out_dir" || exit 1
printf '收集 HE 测试日志，需要管理员权限读取内核日志。\n'
sudo -v || exit 1
sw_vers > "$out_dir/system.txt" 2>&1
sysctl kern.bootargs > "$out_dir/boot-args.txt" 2>&1
sudo kmutil showloaded > "$out_dir/loaded-kexts.txt" 2>&1
system_profiler SPAirPortDataType -detailLevel basic > "$out_dir/wifi-status.txt" 2>&1
sudo dmesg > "$out_dir/dmesg.txt" 2>&1
sudo log show --last 15m --style compact --info --debug --predicate \
  'process == "kernel" AND (eventMessage CONTAINS[c] "itlwm" OR eventMessage CONTAINS[c] "HE negotiated:" OR eventMessage CONTAINS[c] "HE context:" OR eventMessage CONTAINS[c] "HE TLC:" OR eventMessage CONTAINS[c] "Experimental HE" OR eventMessage CONTAINS[c] "iwx_rs_update")' \
  > "$out_dir/kernel-he.log" 2>&1
/usr/bin/grep -E 'Experimental HE|HE negotiated:|HE context:|HE TLC:|iwx_rs_update' \
  "$out_dir/dmesg.txt" "$out_dir/kernel-he.log" > "$out_dir/he-summary.txt" || true
ditto -c -k --keepParent "$out_dir" "$out_dir.zip"
printf '\n报告：%s.zip\n' "$out_dir"
open -R "$out_dir.zip"
