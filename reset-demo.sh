#!/usr/bin/env bash
# ล้างข้อมูลทั้งหมด แล้วเริ่มใหม่ด้วยข้อมูลตัวอย่าง (Gold/Silver ตัวอย่าง)
cd "$(dirname "$0")"
pkill -f "python3 server.py" 2>/dev/null; sleep 0.5
rm -f data/dealsure.db data/dealsure.db-wal data/dealsure.db-shm
rm -rf data/uploads
./start.sh
