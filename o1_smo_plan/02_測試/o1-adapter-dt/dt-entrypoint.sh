#!/bin/bash
# DT wrapper:若有 O1_NODE_ID 環境變數,就由 env 產生 /adapter/config/config.json;否則沿用掛進來的檔案。
set -e
if [ -n "${O1_NODE_ID}" ]; then
  : "${O1_UNIT_TYPE:=DU}"                 # CU-CP | DU
  : "${O1_HOST:=10.3.0.217}"              # SMO 反連得到的 IP
  : "${O1_NETCONF_PORT:=1830}"
  : "${O1_SFTP_PORT:=1222}"
  : "${O1_TELNET_HOST:=10.3.0.217}"
  : "${O1_TELNET_PORT:=9092}"
  : "${O1_GNB_DU_ID:=1}"
  : "${O1_GNB_CU_ID:=0}"
  : "${O1_PM_INTERVAL:=900}"
  : "${O1_HEARTBEAT:=30}"
  : "${O1_VES_URL:=http://10.3.0.204:30417/eventListener/v7}"
  : "${O1_MODEL:=ransim-dt}"
  : "${O1_LOCATION:=DT RAN sim host}"
  : "${O1_NETCONF_USER:=netconf}"
  : "${O1_NETCONF_PASS:=netconf!}"
  cat > /adapter/config/config.json <<JSON
{
  "log-level": 3,
  "software-version": "dt-0.1",
  "network": {"host": "${O1_HOST}", "username": "${O1_NETCONF_USER}", "password": "${O1_NETCONF_PASS}",
              "netconf-port": ${O1_NETCONF_PORT}, "sftp-port": ${O1_SFTP_PORT}},
  "ves": {
    "template": {"new-alarm": "/adapter/config/ves-new-alarm.json", "clear-alarm": "/adapter/config/ves-clear-alarm.json",
                 "pnf-registration": "/adapter/config/ves-pnf-registration.json", "file-ready": "/adapter/config/ves-file-ready.json",
                 "heartbeat": "/adapter/config/ves-heartbeat.json", "pm-data": "/adapter/config/pmData-measData.xml"},
    "pnf-registration": true, "heartbeat-interval": ${O1_HEARTBEAT},
    "url": "${O1_VES_URL}", "username": "sample1", "password": "sample1",
    "pm-data-interval": ${O1_PM_INTERVAL}, "file-expiry": 86400},
  "alarms": {"internal-connection-lost-timeout": 3, "load-downlink-exceeded-warning-threshold": 50, "load-downlink-exceeded-warning-timeout": 15},
  "telnet": {"host": "${O1_TELNET_HOST}", "port": ${O1_TELNET_PORT}},
  "info": {"gnb-cu-id": ${O1_GNB_CU_ID}, "gnb-du-id": ${O1_GNB_DU_ID}, "granularityPeriod": ${O1_PM_INTERVAL}, "fileReportingPeriod": ${O1_PM_INTERVAL},
           "cell-local-id": 0, "node-id": "${O1_NODE_ID}", "location-name": "${O1_LOCATION}",
           "managed-by": "ManagementSystem=O-RAN-SC-ONAP-based-SMO", "managed-element-type": "NodeB",
           "model": "${O1_MODEL}", "unit-type": "${O1_UNIT_TYPE}"}
}
JSON
  # ME 生命週期自動化(SMO 計畫 2026-09-30):pnfRegistration 的 additionalFields 多帶劇本資訊。
  # 只有 orchestrator 起的每 run 容器會給 O1_LIFECYCLE=ephemeral;常駐節點不給 → 不加欄位,SMO 永不自動清理。
  if [ -n "${O1_LIFECYCLE}" ] && ! grep -q '"lifecycle"' /adapter/config/ves-pnf-registration.json; then
    sed -i "s|\"keepaliveDelay\": \"120\"|\"keepaliveDelay\": \"120\",\n                \"scenarioId\": \"${O1_SCENARIO_ID:-unknown}\",\n                \"runId\": \"${O1_RUN_ID:-unknown}\",\n                \"role\": \"${O1_UNIT_TYPE}\",\n                \"lifecycle\": \"${O1_LIFECYCLE}\"|" /adapter/config/ves-pnf-registration.json
  fi
  echo "[dt-entrypoint] config.json generated for ${O1_NODE_ID} (${O1_UNIT_TYPE}) netconf:${O1_NETCONF_PORT} sftp:${O1_SFTP_PORT} telnet:${O1_TELNET_HOST}:${O1_TELNET_PORT}"
fi
exec /adapter/adapter_entrypoint.sh "$@"
