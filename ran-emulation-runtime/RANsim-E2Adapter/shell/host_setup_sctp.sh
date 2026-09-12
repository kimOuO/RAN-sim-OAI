#!/usr/bin/env bash
# SCTP multi-homing self-ABORT 修復 — host-side (sim 端 root 一次性套用)。
#
# 必須做完三件事 OSC RIC 才不會在 ~3-30s 後主動 ABORT：
#   1. SCTP socket bind 10.3.0.217（已在 adapter env SCTP_BIND_IP 處理）
#   2. iptables 阻 SCTP 出站到 docker/k8s 內網（這個 script 處理）
#   3. sysctl SCTP path/association max_retrans 拉到 99999（這個 script 處理）
#
# Reference: RIC team BuildNote 5.4
#
# 使用：sudo bash shell/host_setup_sctp.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Must run as root (sudo)" >&2
  exit 1
fi

echo "=== 2. iptables 阻 SCTP 出站到 docker/k8s 內網 ==="
# 多次跑這 script 不會重複加 rule（先 -D delete，失敗 ignore）
# 2026-08-07:172.17/16 擴成 172.16/12 — RIC 重部署後 bridge 挪到 172.18.0.1,
# 我們本機也有同名 bridge,HB 走 lo 繞回自己觸發 OOTB ABORT self-kill(pcap 實錘)。
# 一次涵蓋所有 RFC1918 Docker/K8s 可能網段。
for cidr in 172.16.0.0/12 192.168.0.0/16 10.0.0.0/24 10.244.0.0/16 10.96.0.0/12; do
  iptables -D OUTPUT -p sctp -d "$cidr" -j DROP 2>/dev/null || true
  iptables -A OUTPUT -p sctp -d "$cidr" -j DROP
  echo "  iptables OUTPUT DROP sctp -d $cidr"
done

echo
echo "=== 3. sysctl SCTP retrans 拉到 99999（不殺主 path） ==="
sysctl -w net.sctp.path_max_retrans=99999
sysctl -w net.sctp.association_max_retrans=99999

# 持久化（reboot 後保留）
SYSCTL_FILE=/etc/sysctl.d/99-ransim-sctp.conf
cat > "$SYSCTL_FILE" <<EOF
# RANsim E2 Adapter SCTP multi-homing self-ABORT workaround
# (RIC team BuildNote 5.4)
net.sctp.path_max_retrans = 99999
net.sctp.association_max_retrans = 99999
EOF
echo "  wrote $SYSCTL_FILE"

echo
echo "=== verify ==="
sysctl net.sctp.path_max_retrans net.sctp.association_max_retrans
echo
iptables -L OUTPUT -n --line-numbers 2>/dev/null | grep -i sctp || echo "  (no sctp rule visible — check iptables -S OUTPUT | grep sctp)"
echo
echo "✓ host setup done. 重啟 e2-adapter 套用 SCTP_BIND_IP env：docker compose up -d e2adapter"
