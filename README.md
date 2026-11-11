# บอทติดตามการอัปเดต Roblox Executor → Discord

บอทตัวนี้จะเช็กทุกวันว่า **executor ตัวไหนออกเวอร์ชันใหม่ / แพตช์ทัน Roblox build ล่าสุด / กลายเป็นใช้ไม่ได้**
แล้วส่งสรุปเป็นข้อความสวย ๆ เข้า Discord พร้อมลิงก์เว็บกับ Discord ทางการของแต่ละเจ้า
และเขียนรายงานเป็นไฟล์ CSV / Markdown เก็บไว้ให้ด้วย

นอกจากข้อความสรุปแล้ว บอทจะแนบ **การ์ดรายตัว** ของทุกเจ้าที่มีการเปลี่ยนแปลง 1 ใบต่อ 1 เจ้า
โดยมีการ์ดจะมี **โลโก้ของเจ้านั้น** (ดึงจากเว็บทางการ — apple-touch-icon / og:image / favicon)
และบล็อก **🔗 ลิงก์ล่าสุด** ครบทั้งเว็บทางการ, ดาวน์โหลด/ซื้อ, Discord และหน้ารายละเอียดบน ScriptBlox

ข้อมูลมาจาก **WEAO public API** (`weao.xyz/api`) ซึ่งเป็นแหล่งข้อมูลตัวเดียวกับที่หน้า
`https://scriptblox.com/executors` ใช้แสดงผล (scriptblox ระบุไว้ท้ายหน้าตัวเอง)
ข้อดีคือได้ข้อมูลเป็น JSON ที่นิ่งและแม่นกว่าการแอบอ่านหน้าเว็บ ซึ่งมักโดนบล็อกจาก Cloudflare

---

## สิ่งที่ต้องมี

- **Python 3.9 ขึ้นไป** (ไม่ต้องติดตั้งไลบรารีเพิ่มเลย — ใช้ของมาตรฐาน Python ล้วน)
  - Windows: โหลดจาก python.org แล้วตอนติดตั้ง **ติ๊ก "Add Python to PATH"** ด้วย
  - macOS / Linux: มีมาให้อยู่แล้ว
- **Discord webhook** ของห้องที่ต้องการให้บอทส่งข้อความ (วิธีสร้างอยู่ด้านล่าง)

---

## วิธีใช้ใน 3 นาที

### 1. สร้าง Discord webhook

1. เปิด Discord แล้วไปที่เซิร์ฟเวอร์ของคุณ (ต้องมีสิทธิ์ "Manage Webhooks")
2. คลิกขวาที่ห้องที่จะให้บอทส่งข้อความ → **Edit Channel** → **Integrations** → **Webhooks**
3. กด **New Webhook** → ตั้งชื่อ เช่น `Roblox Executor Watch` → **Copy Webhook URL**
4. เก็บ URL ไว้ (หน้าตาเป็น `https://discord.com/api/webhooks/....`)

### 2. ใส่ค่าในไฟล์ config

copy `config.example.json` แล้วเปลี่ยนชื่อเป็น `config.json` เปิดด้วย Notepad แล้ววาง URL ลงช่อง `discord_webhook_url`

```json
{
  "discord_webhook_url": "https://discord.com/api/webhooks/123456789/abcdef...",
  "discord_username": "Roblox Executor Watch",
  "platforms": ["Windows", "Mac", "Android", "iOS"],
  "include_externals": true
}
```

ทางเลือก: ไม่ต้องใช้ config.json ก็ได้ ถ้าตั้งตัวแปรสภาพแวดล้อม `DISCORD_WEBHOOK_URL` แทน

### 3. รัน

```bash
python3 executor_watch.py --dry-run   # ลองดูก่อนว่าข้อความหน้าตาเป็นยังไง (ไม่ส่งจริง)
python3 executor_watch.py             # ตรวจ + ส่ง Discord ถ้ามีของใหม่
```

ครั้งแรกบอทจะส่ง "สรุปสถานะทั้งหมด" ไป 1 ข้อความ แล้วจำสถานะไว้ใน `state.json`
ครั้งต่อ ๆ ไปจะส่งเฉพาะตอนที่มีอะไรเปลี่ยน — ไม่รบกวนห้อง

---

## คำสั่งทั้งหมด

| คำสั่ง | ทำอะไร |
| --- | --- |
| `python3 executor_watch.py` | ตรวจและแจ้ง Discord เฉพาะเมื่อมีการเปลี่ยนแปลง |
| `python3 executor_watch.py --dry-run` | แสดงข้อความในหน้าจอ ไม่ส่ง Discord (ยังบันทึก state) |
| `python3 executor_watch.py --force` | ส่งสรุปเต็มทุกครั้ง ถึงไม่มีการเปลี่ยน |
| `python3 executor_watch.py --print` | พิมพ์ตารางสถานะทั้งหมดในหน้าจอ |
| `python3 executor_watch.py --report-only` | เขียนรายงาน CSV/MD อย่างเดียว ไม่แตะ Discord |
| `python3 executor_watch.py --no-logos` | รอบนี้ไม่ต้องแนบรูป (เร็วขึ้น) |
| `python3 executor_watch.py --refresh-logos` | ดึงโลโก้ใหม่ทั้งหมด ล้างแคชเดิม |
| `python3 executor_watch.py --no-save` | ไม่บันทึก state.json (ใช้ทดสอบ) |
| `python3 executor_watch.py --webhook "URL"` | ใช้ webhook อื่นเฉพาะครั้งนั้น |

---

## ให้มันทำงานเองทุกวัน (เลือก 1 วิธี)

> เคล็ดลับ: ถ้าไม่อยากให้มีรูปเลย (เช่น เน็ตช้า) ใช้ `--no-logos` หรือตั้ง `"attach_logos": false`
> ใน `config.json` — ลิงก์ล่าสุดยังอยู่ครบเหมือนเดิม

### วิธี A: GitHub Actions — ฟรี ไม่ต้องเปิดคอมทิ้งไว้ (แนะนำ)

ในโฟลเดอร์มีไฟล์ `.github/workflows/daily-update.yml` เตรียมไว้แล้ว ตั้งเวลาไว้ที่
**ทุก 15 นาที** (cron `*/15 * * * *`)

1. สร้าง repository ใหม่บน GitHub (private ก็ได้) แล้วอัปโหลดไฟล์ทั้งหมดขึ้นไป
2. ไปที่ **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `DISCORD_WEBHOOK_URL`
   - Secret: วาง webhook URL
3. ไปที่แท็บ **Actions** → เลือก workflow **Daily executor update bot** → **Enable workflow**
4. กด **Run workflow** หนึ่งครั้งเพื่อทดสอบ จากนั้นมันจะรันเองทุกวัน

workflow จะ **แก้ไขข้อความเดิม** ใน Discord แทนการส่งซ้ำ (เก็บ message id ไว้ใน `state.json`) และ commit state กลับเข้า repo
เก็บรายงานเป็น artifact 7 วัน
(ถ้าอยากเปลี่ยนความถี่ แก้ `cron: "*/15 * * * *"`)

### วิธี B: Windows Task Scheduler

1. เปิด **Task Scheduler** → **Create Basic Task** → ตั้งชื่อ → Daily → เลือกเวลา
2. Action: **Start a program**
   - Program: `python`
   - Arguments: `executor_watch.py`
   - Start in: โฟลเดอร์ที่วางไฟล์ เช่น `C:\executor-watch`
3. เสร็จแล้ว — จะมีหน้าต่างดำแวบขึ้นมาวันละครั้งแล้วหายไป

### วิธี C: macOS / Linux / VPS (cron)

```bash
crontab -e
# เพิ่มบรรทัดนี้ (ทุกวัน 08:00 น.)
0 8 * * * cd /path/to/executor-watch && /usr/bin/python3 executor_watch.py >> bot.log 2>&1
```

> หมายเหตุ: บอทไม่ใช่ process ที่รันค้างตลอด — มันตั้งเวลาให้ระบบปลุกขึ้นมาทำงานวันละครั้ง
> ถ้าเป็น VPS หรือ Raspberry Pi ก็ใช้ cron แบบเดียวกันได้เลย

---

## ไฟล์ที่ได้

```
executor-watch/
├── executor_watch.py              โค้ดหลักของบอท
├── config.example.json           ตัวอย่าง config (copy เป็น config.json)
├── README.md                     คู่มือนี้
├── state.json                    สถานะล่าสุด (สร้างเองหลังรันครั้งแรก)
├── reports/
│   ├── executors-2026-11-11.csv  ข้อมูลดิบสำหรับเอาไปวิเคราะห์ต่อ (เปิดใน Excel ได้)
│   └── executors-2026-11-11.md   รายงานอ่านง่าย
└── .github/workflows/daily-update.yml
```

คอลัมน์ใน CSV: `name`, `platform`, `version`, `working_on_current_build`, `last_update_utc`,
`age_hours`, `sunc_percent`, `free`, `detected_before`, `key_system`, `cost`, `type`,
`website`, `download_or_buy`, `discord`, `scriptblox_page`, `logo_url`, `roblox_build`

โลโก้ถูกดึงครั้งแรกครั้งเดียวแล้วจำไว้ใน `state.json` (คีย์ `logos`) รอบต่อไปจะไม่ยิงเว็บซ้ำ
ถ้าเว็บไหนเปลี่ยนโลโก้ ใช้ `--refresh-logos` เพื่อดึงใหม่

---

## บอทแจ้งอะไรบ้าง

- 🆕 **ออกเวอร์ชันใหม่** — เทียบเลขเวอร์ชันกับรอบก่อน (บอกเวอร์ชันเดิม → ใหม่)
- ✅ **กลับมาใช้ได้แล้ว** — executor ที่เคยใช้ไม่ได้ ตอนนี้แพตช์ทัน build ปัจจุบัน
- ⚠️ **กลายเป็นใช้ไม่ได้** — Roblox ออก build ใหม่แล้วยังไม่มีแพตช์
- 🎮 **Roblox ออก build ใหม่** — เลข build ของแต่ละแพลตฟอร์มเปลี่ยน

ปรับได้ใน `config.json`:

- ปิดการแจ้งเตือนบางประเภท: `notify_new_version`, `notify_patched`, `notify_outdated`
- เลือกแพลตฟอร์ม: `platforms` (เช่น `["Windows"]`) หรือตัด externals ออก: `include_externals: false`
- เปิด/ปิดรูปโลโก้: `attach_logos` (ปิดแล้วข้อความจะเบาและเร็วขึ้น)
- จำกัดจำนวนการ์ดรายตัวต่อรอบ: `max_detail_embeds` (ค่าเริ่มต้น 10 — Discord จำกัด 10 embed ต่อข้อความ
  บอทจะแบ่งส่งหลายข้อความให้เองถ้าเกิน)

---

## ข้อควรรู้ก่อนใช้

- บอทนี้ **ไม่ได้โฮสต์ ไม่ได้เก็บ และไม่ได้รับไฟล์โปรแกรมใด ๆ** — ให้แค่ลิงก์ไปหน้าเว็บ/Discord ทางการของแต่ละเจ้า
  เท่านั้น (เหมือนที่ scriptblox ทำ)
- Executor เป็นโปรแกรมที่ละเมิดข้อกำหนดการใช้งานของ Roblox การใช้เสี่ยงถูกแบนบัญชี และไฟล์จากแหล่งไม่เป็นทางการ
  มักมีมัลแวร์ปนมาบ่อย ๆ — ถ้าจะใช้ ให้ใช้บัญชีสำรองและตรวจไฟล์ก่อนทุกครั้ง
- ถ้า API ล่มหรือเปลี่ยนรูปแบบ บอทจะลองใหม่อัตโนมัติ 3 ครั้งแล้วแจ้ง error ใน log (ไม่ส่งข้อความขยะเข้า Discord)

---

## คำสั่งใน Discord (`.op` / `see`)

บอร์ดสถานะอัตโนมัติใช้ **Webhook** (รันบน GitHub Actions)

ถ้าต้องการพิมพ์คำสั่งแล้วให้บอทตอบกลับ **เฉพาะคนที่พิมพ์** ใช้สคริปต์ `command_bot.py` รันค้างแยกต่างหาก:

1. สร้าง Discord Application → Bot → เปิด **Message Content Intent**
2. เชิญบอทเข้าเซิร์ฟเวอร์ (สิทธิ์ Send Messages)
3. ตั้งค่า token แล้วรัน:

```bash
pip install -r requirements.txt
export DISCORD_TOKEN="ใส่โทเคนบอท"
python3 command_bot.py
```

คำสั่งที่รองรับ: `.op`  `see`  `.see`

(รันบน VPS / คอมที่เปิดทิ้งไว้ / Railway / Replit — GitHub Actions ใช้เป็น listener 24 ชม. ไม่ได้)

