#!/usr/bin/env python3
"""補送 internalConnectionLoss 的 notifyClearedAlarm(stndDefined, TS 28.111 Rel-18),ME 不需在線。
用法: send_clears.py <ME 名稱> [<ME 名稱> …]      事件內容與 orchestrator o1_spawner._send_clears 相同。"""
import json, sys, time, urllib.request

VES = "http://10.3.0.204:30417/eventListener/v7"
seq = int(time.time()) % 100000
for me in sys.argv[1:]:
    now = int(time.time() * 1e6); iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    ev = {"event": {"commonEventHeader": {
        "domain": "stndDefined", "stndDefinedNamespace": "3GPP-FaultSupervision",
        "eventId": f"ManagedElement={me}_internalConnectionLoss_manualclear_{seq}",
        "eventName": "stndDefined_3GPP-FaultSupervision_NotifyClearedAlarm", "eventType": "3GPP-FaultSupervision",
        "sequence": seq, "priority": "Normal", "reportingEntityId": "", "reportingEntityName": me,
        "sourceId": me, "sourceName": me, "startEpochMicrosec": now, "lastEpochMicrosec": now,
        "nfNamingCode": "001", "nfVendorName": "MITLAB RANsim-DT", "timeZoneOffset": "+00:00",
        "version": "4.1", "vesEventListenerVersion": "7.2.1"},
        "stndDefinedFields": {"stndDefinedFieldsVersion": "1.0",
            "schemaReference": "https://forge.3gpp.org/rep/sa5/MnS/blob/Rel-18/OpenAPI/TS28111_FaultNrm.yaml#components/schemas/NotifyClearedAlarm",
            "data": {"href": f"/ManagedElement={me}", "notificationId": seq, "notificationType": "notifyClearedAlarm",
                     "eventTime": iso, "systemDN": f"ManagedElement={me}",
                     "alarmId": f"ManagedElement={me}-internalConnectionLoss",
                     "alarmType": "COMMUNICATIONS_ALARM", "probableCause": "internalConnectionLoss",
                     "perceivedSeverity": "CLEARED", "clearUserId": "MITLAB RANsim-DT", "clearSystemId": "run-orchestrator"}}}}
    req = urllib.request.Request(VES, data=json.dumps(ev).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        print(iso, me, r.status)
    time.sleep(0.2)
