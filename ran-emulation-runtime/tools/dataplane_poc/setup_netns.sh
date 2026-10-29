#!/usr/bin/env bash
# P0 資料面 PoC:建立 UE 端與 DN 端兩個 netns,以一對 veth 相連,兩端出口各掛 htb + netem。
#
#   [netns dtpoc-ue1] veth-ue 10.250.0.1/30 ══ veth-dn 10.250.0.2/30 [netns dtpoc-dn]
#
# 下行(DN→UE)整形掛在 veth-dn 出口,上行(UE→DN)整形掛在 veth-ue 出口。
# 初始為 1 Gbit/s、0 ms,之後由 shaper.py 每次輪詢改寫。
# 不接 Docker bridge、不接實體網卡、不出網。需要 root:sudo ./setup_netns.sh
set -euo pipefail

UE_NS=${UE_NS:-dtpoc-ue1}
DN_NS=${DN_NS:-dtpoc-dn}
UE_IP=${UE_IP:-10.250.0.1/30}
DN_IP=${DN_IP:-10.250.0.2/30}

if [[ $EUID -ne 0 ]]; then
  echo "需要 root:sudo $0" >&2
  exit 1
fi

for ns in "$UE_NS" "$DN_NS"; do
  if ip netns list | grep -qw "$ns"; then
    echo "netns $ns 已存在,先執行 teardown_netns.sh" >&2
    exit 1
  fi
done

ip netns add "$UE_NS"
ip netns add "$DN_NS"
ip link add veth-ue type veth peer name veth-dn
ip link set veth-ue netns "$UE_NS"
ip link set veth-dn netns "$DN_NS"

ip -n "$UE_NS" addr add "$UE_IP" dev veth-ue
ip -n "$DN_NS" addr add "$DN_IP" dev veth-dn
for pair in "$UE_NS:veth-ue" "$DN_NS:veth-dn"; do
  ns=${pair%%:*}; dev=${pair##*:}
  ip -n "$ns" link set lo up
  ip -n "$ns" link set "$dev" up
  # 關掉 offload,讓 tc 看到的是實際大小的封包(GSO/TSO 會把多個封包併成 64KB 超級封包)
  ip netns exec "$ns" ethtool -K "$dev" gso off tso off gro off >/dev/null 2>&1 || true
  # htb 限速 → netem 延遲/丟包;netem limit 放大,避免高速率時 netem 自己先丟包
  ip netns exec "$ns" tc qdisc add dev "$dev" root handle 1: htb default 10
  ip netns exec "$ns" tc class add dev "$dev" parent 1: classid 1:10 htb rate 1000mbit ceil 1000mbit
  ip netns exec "$ns" tc qdisc add dev "$dev" parent 1:10 handle 10: netem delay 0ms limit 100000
done

echo "已建立 $UE_NS($UE_IP)↔ $DN_NS($DN_IP)"
ip netns exec "$UE_NS" ping -c 2 -W 1 "${DN_IP%/*}"
