#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
command_bot.py — Discord bot คำสั่ง .op / see
=============================================
รันค้างไว้บนเครื่อง/ VPS (GitHub Actions ใช้เป็น listener ไม่ได้)

คำสั่งที่รองรับ:
  .op          ดึงสถานะล่าสุดแล้วตอบกลับคนที่พิมพ์
  see  / .see  เหมือนกัน

ต้องเปิด Message Content Intent ใน Discord Developer Portal
และเชิญบอทเข้าเซิร์ฟเวอร์ด้วยสิทธิ์ Send Messages + Read Message History
"""

from __future__ import annotations

import os
import sys
import asyncio
from pathlib import Path

# ใช้ logic จาก executor_watch โดยไม่ต้องแก้ไฟล์หลัก
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("ต้องติดตั้ง discord.py ก่อน:  pip install discord.py")
    sys.exit(1)

from executor_watch import (
    build_snapshot,
    load_config,
    load_state,
    LogoCache,
    build_embeds,
    fmt_version,
    human_ago,
    parse_ts,
    log,
)

TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
PREFIXES = (".op", "see", ".see", "!op", "!see")

intents = discord.Intents.default()
intents.message_content = True  # ต้องเปิดใน Developer Portal ด้วย
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def build_status_text(cur: dict, limit: int = 20) -> str:
    """ข้อความสรุปสั้น ๆ สำหรับ reply"""
    ex = cur.get("executors") or {}
    ready = sorted(
        (r for r in ex.values() if r.get("updated")),
        key=lambda r: parse_ts(r.get("updated_at")) or __import__("datetime").datetime.min.replace(tzinfo=__import__("datetime").timezone.utc),
        reverse=True,
    )
    total = len(ex)
    working = len(ready)
    lines = [f"**สถานะล่าสุด** · ใช้ได้ **{working}/{total}** ตัว\n"]
    for r in ready[:limit]:
        when = parse_ts(r.get("updated_at"))
        sunc = r.get("sunc")
        sunc_s = f" · sUNC {sunc}%" if sunc is not None else ""
        lines.append(
            f"✅ **{r['name']}** `{fmt_version(r['version'])}` · {r['platform']}{sunc_s} · {human_ago(when)}"
        )
    not_ready = [r["name"] for r in ex.values() if not r.get("updated")]
    if not_ready:
        lines.append(f"\nรอแพตช์ ({len(not_ready)}): " + ", ".join(sorted(not_ready)[:25]))
    return "\n".join(lines)[:1900]


@bot.event
async def on_ready():
    log(f"บอทพร้อม: {bot.user} (id={bot.user.id})")
    log("ฟังคำสั่ง: .op  |  see  |  .see")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = (message.content or "").strip().lower()
    if content not in PREFIXES and not content.startswith((".op ", "see ", ".see ")):
        return

    # ตอบเฉพาะคนที่พิมพ์ (reply)
    async with message.channel.typing():
        try:
            cfg = load_config()
            # บังคับไม่ต้องมี webhook สำหรับโหมดคำสั่ง
            cur = build_snapshot(cfg)
            prev = load_state()
            logos = LogoCache(prev.get("logos") or {})
            text = build_status_text(cur)

            # ส่ง embed สรุปสั้น + รายการตัวที่ใช้ได้
            embed = discord.Embed(
                title="📋 สถานะ Roblox Executor (ล่าสุด)",
                description=text,
                color=0x5865F2,
            )
            embed.set_footer(text=f"ขอโดย {message.author.display_name} · ที่มา WEAO API")
            await message.reply(embed=embed, mention_author=False)
            log(f"ตอบ {message.author} ใน #{getattr(message.channel, 'name', '?')}")
        except Exception as exc:
            await message.reply(f"ดึงข้อมูลไม่สำเร็จ: `{exc}`", mention_author=False)
            log(f"error: {exc}")


def main() -> None:
    if not TOKEN:
        print(
            "ยังไม่มี DISCORD_TOKEN\n"
            "ตั้งค่า:  export DISCORD_TOKEN='...'\n"
            "หรือใส่ใน environment / secret ของเครื่องที่รันบอท"
        )
        sys.exit(1)
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
