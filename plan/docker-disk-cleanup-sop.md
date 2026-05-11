# Docker 磁碟清理 SOP

## 本次救援結果（2026-05-08）

```
Before:    266 GB used (95%, 14 GB free)   ← 危險
After:     218 GB used (79%, 62 GB free)   ← 安全
Recovered: 48 GB
```

清掉的：
1. 2 個 zombie containers (`optimistic_satoshi`, `naughty_lamarr`) — 12 天前 omniver-kit debug session 卡住
2. 9 個孤兒 volume（zombie 留的 anon + 舊 omnivers_platform 系列 + ransim-du 舊 pgdata + tmp_kit）
3. json.log 用 `truncate -s 0` 清空（user 之前手動做的）

---

## 還沒做（需 sudo，下班時間執行）

### A. 立刻可做：再次 truncate json.log（如果又長大）

每天定期跑：
```bash
sudo find /var/lib/docker/containers/ -name "*-json.log" -type f -exec truncate -s 0 {} \;
df -h /
```

### B. **永久解決**：設 docker log rotation

⚠️ **會 restart Docker → 所有 14 個 container 一起 restart**

選週末 / 沒人用 sim 的時段。

```bash
# 1. 編輯 daemon config（沒這檔就建立）
sudo nano /etc/docker/daemon.json

# 2. 加入（檔案空就整個貼）：
```

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
```

```bash
# 3. 重啟 Docker
sudo systemctl restart docker

# 4. 等所有 container 起來
sleep 30
docker ps
```

效果：每個 container 最多 3 個 log 檔 × 100 MB = **單 container 上限 300 MB**。

### C. 替代方案：對個別 container 限 log（不需 restart docker）

如果不想 restart docker，編輯 docker-compose.yml，在每個重要 service 加：

```yaml
services:
  ransim-e2adapter:
    image: ransim-e2adapter:platform
    # ...
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "3"
```

下次 `docker compose up -d` 時生效（會重建這個 container，但其他不動）。

---

## 監控腳本（每天看一眼）

```bash
#!/bin/bash
# /home/mitlab/check-docker-disk.sh
echo "=== Disk ==="
df -h /
echo ""
echo "=== Top 5 largest container logs ==="
sudo find /var/lib/docker/containers/ -name "*-json.log" -type f -exec du -h {} \; 2>/dev/null | sort -hr | head -5
echo ""
echo "=== Docker breakdown ==="
docker system df
echo ""
echo "=== Container CPU/Mem (catch log spammers) ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -15
```

加 cron（每天 9 點看一次）：
```bash
crontab -e
# 加這行:
0 9 * * * /home/mitlab/check-docker-disk.sh > /tmp/docker-check.log 2>&1
```

如果 `df` 看到 > 85% 就要警覺。

---

## 根因：ransim-e2adapter CPU 104% 一直噴 log

從本次診斷看到 e2adapter 跑滿 1 個 core，每秒輸出 SCTP heartbeat / KPM poll 訊息。**這是 application-level 的問題，不是 Docker 問題**。

### 短期：改 log level

`RANsim-E2Adapter` 的 log 設定改：
```python
# 目前可能用 logging.INFO，每秒 print
# 改成只在錯誤時印
logger.setLevel(logging.WARNING)   # heartbeat / poll OK 不印
```

### 長期：把 routine 訊息降 DEBUG

E2 adapter 的：
- `RIC indication poll OK (n=12345)` → DEBUG
- `SCTP heartbeat sent` → DEBUG
- `Subscription registry size = X` → DEBUG
- 只留 `RIC SUB_REQ received` / `Indication encoding failed` 之類事件 INFO

---

## 緊急情況：磁碟又快滿了怎麼辦

優先順序（最大救援/最小風險）：

```bash
# 1. 殺 truncate 所有 json.log（5 秒，0 風險）
sudo find /var/lib/docker/containers/ -name "*-json.log" -type f -exec truncate -s 0 {} \;
df -h /

# 2. 看有沒有新的 zombie / exited container
docker ps -a --filter "status=exited"
docker ps -a --filter "status=dead"
# 有就 docker rm <name>

# 3. 清孤兒 volume（先看會清啥）
docker volume ls -f "dangling=true"
# 確認沒有重要 named volume 後:
docker volume prune -f

# 4. 清 image (build cache)
docker buildx prune -f
docker image prune -f      # 不加 -a，安全

# 5. 真的緊急：清所有 stopped container + dangling resources
docker container prune -f
```

**不要做**（除非真的逼到絕境）：
- ❌ `docker system prune --volumes -f` — 會吃 named volume，可能殺到 postgres
- ❌ `docker image prune -a -f` — 已驗證對你環境救不到（active container 持有所有 image）
- ❌ `rm -rf /var/lib/docker/*` — 等於 reset Docker

---

## 監控 .json.log 大小（不需 sudo 也能看）

```bash
# 透過 inspect 拿 LogPath，然後 ls -la
for c in $(docker ps --format '{{.Names}}'); do
  lp=$(docker inspect "$c" --format '{{.LogPath}}')
  sz=$(sudo ls -la "$lp" 2>/dev/null | awk '{print $5}')
  if [ -n "$sz" ]; then
    printf "%12s  %s\n" "$(numfmt --to=iec $sz)" "$c"
  fi
done | sort -hr
```

---

## 一句話 SOP

> 每天看一次 `df -h /`，超過 80% 立刻 truncate json.log；超過 85% 殺 zombie；找時間設 daemon.json log rotation **永久解決**。
