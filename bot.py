#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot.py — Entry point สำหรับ bot-hosting.net / panel อื่น ๆ

วิธีใช้บน bot-hosting.net
-------------------------
1. สร้าง Deployment เลือกภาษา Python
2. อัปโหลดไฟล์ทั้งหมด (bot.py, command_bot.py, executor_watch.py, requirements.txt)
3. ไปที่ Startup ตั้ง Entry File = bot.py
4. ไปที่ Environment เพิ่มตัวแปร:
     Name  : DISCORD_TOKEN
     Value : โทเคนบอทจาก Discord Developer Portal (เปิด Message Content Intent ด้วย)
5. Start แล้วดู Console

คำสั่งที่รองรับ: .op  |  see  |  .see  |  !op  |  !see
"""

from command_bot import main

if __name__ == "__main__":
    main()
