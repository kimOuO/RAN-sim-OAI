#!/usr/bin/env bash
# P0 資料面 PoC:移除 setup_netns.sh 建立的一切。netns 刪除時,裡面的 veth 與 tc 一併消失。
# 需要 root:sudo ./teardown_netns.sh
set -uo pipefail

UE_NS=${UE_NS:-dtpoc-ue1}
DN_NS=${DN_NS:-dtpoc-dn}

if [[ $EUID -ne 0 ]]; then
  echo "需要 root:sudo $0" >&2
  exit 1
fi

for ns in "$UE_NS" "$DN_NS"; do
  # 先結束 netns 裡殘留的程序(iperf3 server 等),否則 netns 掛載點會被佔住
  pids=$(ip netns pids "$ns" 2>/dev/null || true)
  [[ -n "$pids" ]] && kill $pids 2>/dev/null || true
  ip netns del "$ns" 2>/dev/null && echo "已刪除 $ns" || echo "$ns 不存在"
done

if ip link show veth-ue >/dev/null 2>&1 || ip link show veth-dn >/dev/null 2>&1; then
  echo "警告:主機上仍有 veth-ue / veth-dn" >&2
  exit 1
fi
echo "還原完成"
