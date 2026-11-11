# วิธีรันบน bot-hosting.net

บอทนี้รองรับ **bot-hosting.net** แล้ว (ใช้ `bot.py` เป็น entry point)

## ขั้นตอนสั้น ๆ

1. ไปที่ [bot-hosting.net](https://bot-hosting.net) → Login ด้วย Discord → สร้าง **Deployment** เลือกภาษา **Python**
2. อัปโหลดไฟล์เหล่านี้ขึ้นไป (หรือ clone จาก GitHub):
   - `bot.py`          ← ไฟล์เริ่มต้น (ตั้งเป็น Entry File)
   - `command_bot.py`
   - `executor_watch.py`
   - `requirements.txt`
3. ไปที่แท็บ **Startup**
   - ตั้ง **Entry File (STARTUP_FILE)** = `bot.py`
4. ไปที่แท็บ **Environment** (หรือ Variables)
   - เพิ่มตัวแปร:
     - **Name**: `DISCORD_TOKEN`
     - **Value**: โทเคนบอทจาก [Discord Developer Portal](https://discord.com/developers/applications)
     - ทำเครื่องหมายเป็น Secret
5. **สำคัญ**: ใน Discord Developer Portal → บอทของคุณ → เปิด **Message Content Intent**
6. กด **Start** แล้วดู Console ควรเห็นข้อความประมาณ:
   ```
   [startup] เริ่มบอท...
   บอทพร้อม: YourBot#1234
   ฟังคำสั่ง: .op  |  see  |  .see
   ```

## คำสั่งที่ใช้ได้

พิมพ์ในแชท Discord (บอทต้องอยู่ในเซิร์ฟเวอร์):

| คำสั่ง     | ความหมาย                          |
|------------|-----------------------------------|
| `.op`      | ดูสถานะ executor ล่าสุด           |
| `see`      | เหมือน `.op`                      |
| `.see`     | เหมือน `.op`                      |
| `!op`      | เหมือน `.op`                      |
| `!see`     | เหมือน `.op`                      |

บอทจะ **reply** เฉพาะคนที่พิมพ์คำสั่ง

## หมายเหตุ

- บอทนี้ใช้ API สาธารณะของ WEAO ไม่ต้องมี config.json ก็ได้
- ถ้าต้องการปรับแพลตฟอร์มหรือตัวเลือกอื่น สามารถสร้าง `config.json` จาก `config.example.json` แล้วอัปโหลดเพิ่มได้
- บอทอัปเดตอัตโนมัติผ่าน GitHub Actions (webhook) ยังทำงานแยกต่างหากได้ตามปกติ
