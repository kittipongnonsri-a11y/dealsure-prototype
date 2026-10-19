#!/usr/bin/env bash
# เริ่มเซิร์ฟเวอร์ดีลชัวร์ (ทำงานเบื้องหลัง) – ใช้: ./start.sh   (เปลี่ยนพอร์ต: PORT=9000 ./start.sh)
cd "$(dirname "$0")"
mkdir -p data
pkill -f "python3 server.py" 2>/dev/null; sleep 0.5
PYTHONUNBUFFERED=1 nohup python3 server.py > data/server.log 2>&1 &
sleep 1; cat data/server.log
