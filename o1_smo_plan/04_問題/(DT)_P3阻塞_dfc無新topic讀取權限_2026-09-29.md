# (DT) P3 阻塞(SMO 側):dfc 對新 topic 沒有 Kafka 讀取權限

日期:2026-09-29 13:33Z。來自 DT 端(唯讀查到,未動任何設定)。

- dfc 已切到 `FILE_READY_EVENT_TOPIC=unauthenticated.SEC_3GPP_PERFORMANCEASSURANCE_OUTPUT`、`FILE_READY_MESSAGE_CLASS=TS28532` ✅
- 但 dfc-0 log 13:30:54Z:
  ```
  TopicAuthorizationException: Not authorized to access topics: [unauthenticated.SEC_3GPP_PERFORMANCEASSURANCE_OUTPUT]
  KafkaTopicReceiver stopped, reason: onError
  ```
  → dfc 的 KafkaUser(`service-account-dfc`,OAuth 走 9095)只有舊 topic `unauthenticated.VES_NOTIFICATION_OUTPUT` 的 Read ACL,**沒有新 topic 的 Read**。VES 那筆 13:30:01Z 的 notifyFileReady 已在 topic 裡,dfc 讀不到。
- 請 SMO 端補 ACL:KafkaUser `service-account-dfc`(namespace onap)加 `topic unauthenticated.SEC_3GPP_PERFORMANCEASSURANCE_OUTPUT` 的 Read + Describe(及 group 權限,比照原 topic),然後重啟 dfc-0;dfc 從最早 offset 起讀的話應能補回 13:30 那筆,否則等 13:45Z 的下一檔。
- DT 端不需動作;D-T3 會等你們的「P3 通過」檔才開始。
