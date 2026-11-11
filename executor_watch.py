#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
executor_watch.py
=================
บอทติดตามการอัปเดตของ Roblox executor แล้วแจ้งเข้า Discord

ข้อมูลมาจาก WEAO public API (https://weao.xyz/api) ซึ่งเป็นแหล่งข้อมูลเดียวกับ
ที่หน้า https://scriptblox.com/executors ใช้แสดงผล (scriptblox ระบุไว้ท้ายหน้าเอง)

บอทจะ:
  1. ดึงสถานะ executor ทุกตัว + เวอร์ชัน Roblox ล่าสุดของแต่ละแพลตฟอร์ม
  2. ดึงโลโก้จากเว็บทางการของแต่ละเจ้า (แคชไว้ใน state.json ไม่ยิงซ้ำทุกวัน)
  3. เทียบกับ state.json ที่บันทึกไว้จากครั้งก่อน
  4. แจ้งเข้า Discord เฉพาะสิ่งที่มีการเปลี่ยนแปลง พร้อมรูปโลโก้และลิงก์ล่าสุด
  5. เขียนรายงานเป็น CSV / Markdown ไว้ในโฟลเดอร์ reports/

ไม่ต้องติดตั้งไลบรารีเพิ่ม (ใช้ Python มาตรฐานล้วน) ต้องมี Python 3.9 ขึ้นไป

การใช้งานพื้นฐาน:
    python3 executor_watch.py --dry-run     # ทดสอบ ดูผลในหน้าจอ ไม่ส่ง Discord
    python3 executor_watch.py               # ตรวจและแจ้ง Discord ถ้ามีของใหม่
    python3 executor_watch.py --force       # ส่งสรุปเต็มทุกครั้ง ไม่สนว่ามีของใหม่ไหม
    python3 executor_watch.py --report-only # เขียนรายงานอย่างเดียว ไม่ส่ง Discord

บอทนี้ไม่โฮสต์และไม่กระจายไฟล์ใด ๆ ของ executor ทั้งสิ้น — ให้ลิงก์ไปยัง
เว็บไซต์/Discord ทางการของแต่ละเจ้าเท่านั้น
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import error, request
from urllib.parse import urljoin, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "state.json"
CONFIG_FILE = SCRIPT_DIR / "config.json"
REPORT_DIR = SCRIPT_DIR / "reports"

API_EXPLOITS = "https://weao.xyz/api/status/exploits"
API_VERSIONS = "https://weao.xyz/api/versions/current"
USER_AGENT = "executor-watch/1.1 (personal Discord status bot)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SCRIPTBLOX_EXECUTOR = "https://scriptblox.com/executor/{slug}"

TH_TZ = timezone(timedelta(hours=7))
MONTHS_TH = [
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]

DEFAULT_CONFIG = {
    "discord_webhook_url": "",
    "discord_username": "Roblox Executor Watch",
    "platforms": ["Windows", "Mac", "Android", "iOS"],
    "include_externals": True,
    "notify_new_version": True,
    "notify_patched": True,
    "notify_outdated": True,
    "attach_logos": True,
    "max_detail_embeds": 10,
    "write_reports": True,
    "timezone_offset_hours": 7,
}


# --------------------------------------------------------------------------
# utilities
# --------------------------------------------------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def log(msg: str) -> None:
    stamp = datetime.now(TH_TZ).strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def th_date(dt: datetime | None) -> str:
    if dt is None:
        return "ไม่ทราบเวลา"
    d = dt.astimezone(TH_TZ)
    return f"{d.day} {MONTHS_TH[d.month - 1]} {d.year + 543} {d:%H:%M} น."


def human_ago(dt: datetime | None, ref: datetime | None = None) -> str:
    if dt is None:
        return "ไม่ทราบเวลา"
    ref = ref or now_utc()
    secs = (ref - dt).total_seconds()
    if secs < 0:
        secs = 0
    if secs < 90:
        return "เมื่อสักครู่"
    if secs < 3600:
        return f"{int(secs // 60)} นาทีที่แล้ว"
    if secs < 86400:
        return f"{int(secs // 3600)} ชั่วโมงที่แล้ว"
    if secs < 86400 * 30:
        return f"{int(secs // 86400)} วันที่แล้ว"
    if secs < 86400 * 365:
        return f"{int(secs // (86400 * 30))} เดือนที่แล้ว"
    return f"{int(secs // (86400 * 365))} ปีที่แล้ว"


def parse_ts(text: str | None) -> datetime | None:
    """แปลงสตริงวันที่จาก API เช่น '11/06/2026 at 1:24 PM UTC'."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    formats = (
        "%m/%d/%Y at %I:%M %p UTC",
        "%m/%d/%Y, %I:%M:%S %p UTC",
        "%m/%d/%Y, %I:%M %p UTC",
        "%m/%d/%Y at %I:%M:%S %p UTC",
        "%m/%d/%Y %H:%M:%S UTC",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:  # ISO 8601 เผื่อ API เปลี่ยนรูปแบบ
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_version(raw: str | None) -> str:
    """จัดรูปแบบเลขเวอร์ชันให้อ่านง่าย (บางเจ้าตั้งชื่อมี v นำหน้าอยู่แล้ว)."""
    text = str(raw or "").strip()
    if not text:
        return ""
    if text[:1] in ("v", "V") and text[1:2].isdigit():
        return text
    return f"v{text}"


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "unknown"


def scriptblox_url(name: str) -> str:
    return SCRIPTBLOX_EXECUTOR.format(slug=slug(name))


def http_json(url: str, retries: int = 3, timeout: int = 30):
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "Cache-Control": "no-cache",
                },
            )
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
            if attempt < retries:
                wait = 2 * attempt
                log(f"ดึงข้อมูลไม่สำเร็จ (ครั้งที่ {attempt}/{retries}): {exc} — ลองใหม่ใน {wait} วิ")
                time.sleep(wait)
    raise RuntimeError(f"ดึงข้อมูลจาก {url} ไม่สำเร็จ: {last_err}")


def http_bytes(url: str, timeout: float = 8.0, limit: int = 4096) -> tuple[str, bytes] | None:
    """GET แบบเบา ๆ เอาไว้ตรวจรูป/อ่านหัวเว็บ (คืน (content-type, bytes))."""
    try:
        req = request.Request(
            url,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.headers.get("Content-Type", ""), resp.read(limit)
    except (error.URLError, error.HTTPError, TimeoutError, ValueError, OSError):
        return None


# --------------------------------------------------------------------------
# logo / image lookup
# --------------------------------------------------------------------------
def is_image(url: str) -> bool:
    got = http_bytes(url, timeout=6.0, limit=2048)
    if not got:
        return False
    ctype, blob = got
    if ctype.lower().startswith("image/"):
        return True
    signatures = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"<svg", b"<?xml")
    return any(blob.startswith(sig) for sig in signatures)


def find_logo(site_url: str) -> str:
    """หาโลโก้/ไอคอนจากเว็บทางการของ executor (apple-touch-icon > og:image > favicon)."""
    site_url = (site_url or "").strip()
    host = urlparse(site_url).netloc
    if site_url:
        got = http_bytes(site_url, timeout=8.0, limit=400_000)
        if got:
            html = got[1].decode("utf-8", "replace")
            patterns = (
                r'<link[^>]+rel=["\'][^"\']*apple-touch-icon[^"\']*["\'][^>]*>',
                r'<meta[^>]+(?:property|name)=["\'](?:og:image|og:image:url|twitter:image)["\'][^>]*>',
                r'<link[^>]+rel=["\'][^"\']*\bicon\b[^"\']*["\'][^>]*>',
            )
            candidates: list[str] = []
            for pattern in patterns:
                for match in re.finditer(pattern, html, re.IGNORECASE):
                    found = re.search(r'(?:href|content)=["\']([^"\']+)["\']', match.group(0), re.IGNORECASE)
                    if found:
                        candidate = urljoin(site_url, found.group(1).strip())
                        if candidate.startswith("http"):
                            candidates.append(candidate)
            for candidate in candidates:
                if is_image(candidate):
                    return candidate
    if host:
        # ทางสำรอง: บริการไอคอนของ DuckDuckGo (คืน PNG ขนาดกำลังดีให้ Discord ใช้)
        return f"https://icons.duckduckgo.com/ip3/{host}.ico"
    return ""


class LogoCache:
    """แคชลิงก์โลโก้ไว้ใน state.json — ดึงครั้งแรกครั้งเดียว แล้วใช้ซ้ำข้ามวัน"""

    def __init__(self, data: dict | None = None):
        self.data = dict(data or {})
        self.fetched = 0

    @staticmethod
    def key(rec: dict) -> str:
        return f"{slug(rec['name'])}|{rec['platform'].lower()}"

    def get(self, rec: dict) -> str:
        k = self.key(rec)
        if k not in self.data:
            self.data[k] = find_logo(rec.get("website") or "")
            self.fetched += 1
            if self.fetched % 10 == 0:
                log(f"ดึงโลโก้ไปแล้ว {self.fetched} เจ้า...")
        return self.data[k]

    def known(self, rec: dict) -> str:
        return self.data.get(self.key(rec), "") or ""

    def export(self) -> dict:
        return {k: v for k, v in self.data.items() if v}


# --------------------------------------------------------------------------
# config / state
# --------------------------------------------------------------------------
def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text("utf-8")))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"config.json อ่านไม่ได้ (JSON ผิดรูป): {exc}")
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        cfg["discord_webhook_url"] = os.environ["DISCORD_WEBHOOK_URL"].strip()
    return cfg


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except json.JSONDecodeError:
            log("state.json เสียหาย — เริ่มนับสถานะใหม่")
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", "utf-8")


# --------------------------------------------------------------------------
# data collection
# --------------------------------------------------------------------------
def build_snapshot(cfg: dict) -> dict:
    raw = http_json(API_EXPLOITS)
    if not isinstance(raw, list):
        raise RuntimeError("รูปแบบข้อมูลจาก API ไม่ถูกต้อง (คาดว่าเป็น list)")

    versions = http_json(API_VERSIONS)
    if not isinstance(versions, dict):
        versions = {}

    allowed = {p.lower() for p in cfg.get("platforms", DEFAULT_CONFIG["platforms"])}
    include_externals = bool(cfg.get("include_externals", True))

    executors: dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        platform = str(item.get("platform") or "Windows").strip()
        if allowed and platform.lower() not in allowed:
            continue
        is_external = slug(item.get("extype", "")).startswith("external")
        if is_external and not include_externals:
            continue

        updated_dt = parse_ts(item.get("updatedDate"))
        purchase = str(item.get("purchaselink") or item.get("purcselink") or "").strip()
        key = f"{slug(title)}|{platform.lower()}"
        executors[key] = {
            "name": title,
            "platform": platform,
            "version": str(item.get("version") or "").strip(),
            "updated": bool(item.get("updateStatus")),
            "updated_at": updated_dt.isoformat() if updated_dt else None,
            "rbx_version": str(item.get("rbxversion") or ""),
            "sunc": item.get("suncPercentage"),
            "free": bool(item.get("free")),
            "detected": bool(item.get("detected")),
            "cost": str(item.get("cost") or "").strip(),
            "key_system": bool(item.get("keysystem")),
            "website": str(item.get("websitelink") or "").strip(),
            "discord": str(item.get("discordlink") or "").strip(),
            "purchase": purchase,
            "scriptblox": scriptblox_url(title),
            "external": is_external,
        }

    rbx: dict[str, dict] = {}
    for platform in ("Windows", "Mac", "Android", "iOS"):
        ver = versions.get(platform)
        if not ver:
            continue
        resp = versions.get(f"{platform}Response") or {}
        rbx[platform] = {
            "version": str(ver),
            "build": str(resp.get("version") or ""),
            "changed_at": (parse_ts(versions.get(f"{platform}Date")) or now_utc()).isoformat(),
        }

    return {
        "collected_at": now_utc().isoformat(),
        "rbx": rbx,
        "executors": executors,
    }


def diff_snapshots(prev: dict, cur: dict, cfg: dict) -> dict:
    changes = {"new_version": [], "patched": [], "outdated": [], "added": [], "rbx": []}
    prev_ex = prev.get("executors") or {}

    for key, rec in cur["executors"].items():
        old = prev_ex.get(key)
        if old is None:
            if prev_ex:
                changes["added"].append(rec)
            continue
        if cfg.get("notify_new_version", True) and old.get("version") != rec["version"]:
            rec = dict(rec, previous_version=old.get("version") or "")
            changes["new_version"].append(rec)
        elif cfg.get("notify_patched", True) and not old.get("updated") and rec["updated"]:
            changes["patched"].append(rec)
        elif cfg.get("notify_outdated", True) and old.get("updated") and not rec["updated"]:
            changes["outdated"].append(rec)

    prev_rbx = prev.get("rbx") or {}
    for platform, info in cur["rbx"].items():
        old = prev_rbx.get(platform) or {}
        if old.get("version") and old["version"] != info["version"]:
            prev_build = old.get("build") or old.get("version")
            changes["rbx"].append(
                {"platform": platform, "old": prev_build, "new": info["build"] or info["version"]}
            )

    return changes


def has_changes(changes: dict) -> bool:
    return any(changes[k] for k in changes)


# --------------------------------------------------------------------------
# Discord
# --------------------------------------------------------------------------
COLORS = {"new_version": 0x57F287, "patched": 0x3BA55D, "outdated": 0xED4245}
EMOJI = {"new_version": "🆕", "patched": "✅", "outdated": "⚠️"}


def chunk_lines(lines: list[str], limit: int = 1000) -> list[str]:
    chunks, buf = [], ""
    for line in lines:
        candidate = f"{buf}\n{line}" if buf else line
        if len(candidate) > limit and buf:
            chunks.append(buf)
            buf = line
        else:
            buf = candidate
    if buf:
        chunks.append(buf)
    return chunks or ["—"]


def executor_line(rec: dict, note: str = "") -> str:
    bits = [f"**{rec['name']}**"]
    if rec.get("version"):
        bits.append(f"`{fmt_version(rec['version'])}`")
    bits.append(f"· {rec['platform']}")
    if note:
        bits.append(f"· {note}")
    when = parse_ts(rec.get("updated_at"))
    if when:
        bits.append(f"· {human_ago(when)}")
    links = []
    if rec.get("website"):
        links.append(f"[เว็บ]({rec['website']})")
    if rec.get("discord"):
        links.append(f"[Discord]({rec['discord']})")
    links.append(f"[ScriptBlox]({rec.get('scriptblox') or scriptblox_url(rec['name'])})")
    return " ".join(bits) + " — " + " · ".join(links)


def link_line(rec: dict) -> str:
    """ลิงก์ล่าสุดของเจ้านั้น: เว็บทางการ / ดาวน์โหลด-ซื้อ / Discord / หน้ารายละเอียด"""
    links = []
    if rec.get("website"):
        links.append(f"[🌐 เว็บทางการ]({rec['website']})")
    if rec.get("purchase"):
        label = "⬇️ ดาวน์โหลด/ซื้อ" if not rec.get("free") else "⬇️ ดาวน์โหลด"
        links.append(f"[{label}]({rec['purchase']})")
    if rec.get("discord"):
        links.append(f"[💬 Discord]({rec['discord']})")
    links.append(f"[📄 หน้า ScriptBlox]({rec.get('scriptblox') or scriptblox_url(rec['name'])})")
    return " · ".join(links)


def plain_links(rec: dict) -> str:
    links = []
    if rec.get("website"):
        links.append(f"[เว็บ]({rec['website']})")
    if rec.get("purchase"):
        links.append(f"[ดาวน์โหลด/ซื้อ]({rec['purchase']})")
    if rec.get("discord"):
        links.append(f"[Discord]({rec['discord']})")
    links.append(f"[ScriptBlox]({rec.get('scriptblox') or scriptblox_url(rec['name'])})")
    return " · ".join(links)


def detail_embed(rec: dict, kind: str, logo: str) -> dict:
    """การ์ดรายตัว 1 ใบ — มีโลโก้ + ลิงก์ล่าสุดครบ"""
    status = "ใช้ได้กับ build ปัจจุบัน" if rec["updated"] else "ยังรอแพตช์"
    fields = [
        {"name": "สถานะ", "value": status, "inline": True},
        {"name": "แพลตฟอร์ม", "value": rec["platform"], "inline": True},
    ]
    if rec.get("sunc") is not None:
        fields.append({"name": "sUNC", "value": f"{rec['sunc']}%", "inline": True})
    if kind == "new_version" and rec.get("previous_version"):
        fields.append(
            {
                "name": "เวอร์ชัน",
                "value": f"{fmt_version(rec['previous_version'])} → **{fmt_version(rec['version'])}**",
                "inline": False,
            }
        )
    fields.append({"name": "🔗 ลิงก์ล่าสุด", "value": link_line(rec)[:1000], "inline": False})

    embed = {
        "title": f"{EMOJI[kind]} {rec['name']} — {fmt_version(rec['version'])}",
        "url": rec.get("website") or rec.get("scriptblox") or scriptblox_url(rec["name"]),
        "color": COLORS[kind],
        "fields": fields[:25],
        "timestamp": now_utc().isoformat(),
    }
    footnote = []
    if rec.get("cost"):
        footnote.append(rec["cost"])
    elif rec.get("free"):
        footnote.append("ฟรี")
    if rec.get("detected"):
        footnote.append("เคยถูกตรวจจับ")
    if rec.get("key_system"):
        footnote.append("มี key system")
    if footnote:
        embed["footer"] = {"text": " · ".join(footnote)[:200]}
    if logo:
        embed["thumbnail"] = {"url": logo}
    return embed


def build_embeds(
    cur: dict,
    changes: dict,
    cfg: dict,
    full: bool = False,
    logos: LogoCache | None = None,
) -> list[dict]:
    ex = cur["executors"]
    total = len(ex)
    updated = sum(1 for r in ex.values() if r["updated"])
    free = sum(1 for r in ex.values() if r["free"])
    safe = sum(1 for r in ex.values() if not r["detected"])

    header = (
        f"🕒 {th_date(now_utc())} (เวลาไทย)\n"
        f"ติดตาม **{total}** ตัว · ใช้ได้กับ build ปัจจุบัน **{updated}** ตัว · "
        f"ฟรี {free} · ไม่เคยถูกตรวจจับ {safe}"
    )
    rbx_lines = []
    for platform, info in cur["rbx"].items():
        when = parse_ts(info.get("changed_at"))
        rbx_lines.append(
            f"**{platform}** — `{info.get('build') or info['version']}` ({info['version']}) · {human_ago(when)}"
        )
    if rbx_lines:
        header += "\n\n**Roblox client ล่าสุด**\n" + "\n".join(rbx_lines)

    main = {
        "title": "📋 สรุปสถานะ Roblox Executor ทั้งหมด" if full else "🔄 สรุปการอัปเดต Roblox Executor",
        "description": header[:4000],
        "color": 0x5865F2,
        "footer": {"text": "ที่มา: WEAO public API (ข้อมูลเดียวกับ scriptblox.com/executors)"},
        "timestamp": now_utc().isoformat(),
    }

    fields: list[dict] = []
    if changes["new_version"]:
        lines = [
            executor_line(r, f"เดิม `{fmt_version(r['previous_version'])}` → ใหม่")
            for r in changes["new_version"]
        ]
        for i, chunk in enumerate(chunk_lines(lines)):
            fields.append({
                "name": f"🆕 ออกเวอร์ชันใหม่ ({len(changes['new_version'])})" if i == 0 else "🆕 ต่อ",
                "value": chunk,
                "inline": False,
            })
    if changes["patched"]:
        lines = [executor_line(r, "แพตช์ทัน build แล้ว") for r in changes["patched"]]
        for i, chunk in enumerate(chunk_lines(lines)):
            fields.append({
                "name": f"✅ กลับมาใช้ได้แล้ว ({len(changes['patched'])})" if i == 0 else "✅ ต่อ",
                "value": chunk,
                "inline": False,
            })
    if changes["outdated"]:
        lines = [executor_line(r, "ยังไม่แพตช์") for r in changes["outdated"][:40]]
        for i, chunk in enumerate(chunk_lines(lines)):
            fields.append({
                "name": f"⚠️ กลายเป็นใช้ไม่ได้ ({len(changes['outdated'])})" if i == 0 else "⚠️ ต่อ",
                "value": chunk,
                "inline": False,
            })
    if changes["rbx"]:
        lines = [f"**{c['platform']}**: `{c['old']}` → `{c['new']}`" for c in changes["rbx"]]
        fields.append({"name": "🎮 Roblox ออก build ใหม่", "value": "\n".join(lines)[:1000], "inline": False})

    if full or not fields:
        ready = sorted(
            (r for r in ex.values() if r["updated"]),
            key=lambda r: parse_ts(r.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        lines = [executor_line(r) for r in ready[:45]]
        if lines:
            for i, chunk in enumerate(chunk_lines(lines)):
                fields.append({
                    "name": f"พร้อมใช้ตอนนี้ ({len(ready)})" if i == 0 else "พร้อมใช้ (ต่อ)",
                    "value": chunk,
                    "inline": False,
                })
        not_ready = [r for r in ex.values() if not r["updated"]]
        if not_ready:
            names = ", ".join(sorted(r["name"] for r in not_ready))
            fields.append({"name": f"รอแพตช์ ({len(not_ready)})", "value": names[:1000], "inline": False})

    # เลือก "ตัวเด่น" ของรอบนี้ไว้เป็นรูปประจำข้อความ
    hero = None
    for kind in ("new_version", "patched"):
        if changes.get(kind):
            hero = changes[kind][0]
            break

    detail_pairs: list[tuple[dict, str]] = []
    for kind in ("new_version", "patched", "outdated"):
        detail_pairs += [(r, kind) for r in changes.get(kind, [])]
    if (full or not detail_pairs) and not detail_pairs:
        ready = sorted(
            (r for r in ex.values() if r["updated"]),
            key=lambda r: parse_ts(r.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        detail_pairs = [(r, "patched") for r in ready[:8]]
    limit = max(0, int(cfg.get("max_detail_embeds", 10) or 0))
    detail_pairs = detail_pairs[:limit]

    attach_logos = bool(cfg.get("attach_logos", True))
    if hero and logos and attach_logos:
        logo = logos.get(hero)
        if logo:
            main["thumbnail"] = {"url": logo}

    embeds: list[dict] = []
    if fields:
        main["fields"] = fields[:25]
        embeds.append(main)
        rest = fields[25:]
        while rest:
            embeds.append({
                "title": "📊 ต่อจากข้อความก่อนหน้า",
                "color": 0x5865F2,
                "fields": rest[:25],
                "timestamp": now_utc().isoformat(),
            })
            rest = rest[25:]
    else:
        main["description"] = header[:4000] + "\n\n_ไม่มีการเปลี่ยนแปลงตั้งแต่รอบก่อน_"
        embeds.append(main)

    for rec, kind in detail_pairs:
        logo = logos.get(rec) if (logos and attach_logos) else ""
        embeds.append(detail_embed(rec, kind, logo))

    return embeds


def post_discord(webhook: str, embeds: list[dict], username: str, dry_run: bool = False) -> None:
    if dry_run:
        log("— โหมดทดสอบ: ข้อความที่จะส่งเข้า Discord —")
        print(json.dumps({"username": username, "embeds": embeds}, ensure_ascii=False, indent=2))
        return
    if not webhook:
        raise SystemExit(
            "ยังไม่ได้ตั้งค่า webhook\n"
            "ใส่ URL ใน config.json (ช่อง discord_webhook_url) "
            "หรือตั้งตัวแปรสภาพแวดล้อม DISCORD_WEBHOOK_URL"
        )

    # Discord จำกัด 10 embed ต่อข้อความ และ ~6000 ตัวอักษรรวม
    batches: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for embed in embeds:
        length = len(json.dumps(embed, ensure_ascii=False))
        if current and (len(current) >= 10 or size + length > 5500):
            batches.append(current)
            current, size = [], 0
        current.append(embed)
        size += length
    if current:
        batches.append(current)

    for index, batch in enumerate(batches, start=1):
        payload = json.dumps({"username": username, "embeds": batch}, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                if resp.status not in (200, 204):
                    log(f"Discord ตอบกลับสถานะ {resp.status}")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            raise SystemExit(f"ส่งเข้า Discord ไม่สำเร็จ ({exc.code}): {body}")
        except error.URLError as exc:
            raise SystemExit(f"เชื่อมต่อ Discord ไม่ได้: {exc.reason}")
        log(f"ส่งข้อความที่ {index}/{len(batches)} แล้ว ({len(batch)} embed)")


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------
def write_reports(cur: dict, changes: dict, logos: LogoCache | None = None) -> tuple[Path, Path] | None:
    REPORT_DIR.mkdir(exist_ok=True)
    stamp = now_utc().astimezone(TH_TZ).strftime("%Y-%m-%d")
    csv_path = REPORT_DIR / f"executors-{stamp}.csv"
    md_path = REPORT_DIR / f"executors-{stamp}.md"

    rows = sorted(
        cur["executors"].values(),
        key=lambda r: (not r["updated"], r["platform"], r["name"].lower()),
    )
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "name", "platform", "version", "working_on_current_build", "last_update_utc",
            "age_hours", "sunc_percent", "free", "detected_before", "key_system", "cost", "type",
            "website", "download_or_buy", "discord", "scriptblox_page", "logo_url", "roblox_build",
        ])
        ref = now_utc()
        for r in rows:
            when = parse_ts(r.get("updated_at"))
            age = round((ref - when).total_seconds() / 3600, 1) if when else ""
            writer.writerow([
                r["name"], r["platform"], r["version"], "yes" if r["updated"] else "no",
                when.strftime("%Y-%m-%d %H:%M") if when else "",
                age, r.get("sunc") if r.get("sunc") is not None else "",
                "yes" if r["free"] else "no", "yes" if r["detected"] else "no",
                "yes" if r.get("key_system") else "no",
                r.get("cost", ""), "external" if r.get("external") else "executor",
                r.get("website", ""), r.get("purchase", ""), r.get("discord", ""),
                r.get("scriptblox", ""), (logos.known(r) if logos else ""),
                r.get("rbx_version", ""),
            ])

    total = len(rows)
    working = sum(1 for r in rows if r["updated"])
    lines = [
        f"# รายงานสถานะ Roblox Executor — {stamp}",
        "",
        f"เก็บข้อมูลเมื่อ {th_date(now_utc())} (เวลาไทย) · ที่มา: WEAO public API",
        "",
        f"- ติดตามทั้งหมด **{total}** ตัว",
        f"- ใช้งานได้กับ build ปัจจุบัน **{working}** ตัว, รอแพตช์ **{total - working}** ตัว",
    ]
    for platform, info in cur["rbx"].items():
        lines.append(f"- Roblox {platform}: `{info.get('build') or info['version']}`")
    lines += ["", "## การเปลี่ยนแปลงรอบนี้", ""]
    labels = [
        ("new_version", "ออกเวอร์ชันใหม่"),
        ("patched", "กลับมาใช้ได้แล้ว"),
        ("outdated", "กลายเป็นใช้ไม่ได้"),
        ("added", "เพิ่งเริ่มติดตาม"),
    ]
    any_change = False
    for key, label in labels:
        if changes.get(key):
            any_change = True
            lines.append(f"### {label} ({len(changes[key])})")
            for r in changes[key]:
                extra = f" (เดิม `{fmt_version(r['previous_version'])}`)" if r.get("previous_version") else ""
                mark = "✅" if r["updated"] else "⏳"
                lines.append(
                    f"- {mark} **{r['name']}** — `{fmt_version(r['version'])}` · {r['platform']}{extra}"
                    f" — {plain_links(r)}"
                )
            lines.append("")
    if changes.get("rbx"):
        any_change = True
        lines.append("### Roblox ออก build ใหม่")
        for c in changes["rbx"]:
            lines.append(f"- {c['platform']}: `{c['old']}` → `{c['new']}`")
        lines.append("")
    if not any_change:
        lines += ["_ไม่มีการเปลี่ยนแปลง_", ""]

    lines += [
        "## ทั้งหมด",
        "",
        "| ชื่อ | แพลตฟอร์ม | เวอร์ชัน | สถานะ | sUNC | อัปเดตล่าสุด | ลิงก์ |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        when = parse_ts(r.get("updated_at"))
        lines.append(
            f"| {r['name']} | {r['platform']} | {fmt_version(r['version']) or '-'} | "
            f"{'✅ ใช้ได้' if r['updated'] else '⏳ รอแพตช์'} | "
            f"{r['sunc'] if r['sunc'] is not None else '-'} | {human_ago(when)} | {plain_links(r)} |"
        )
    md_path.write_text("\n".join(lines) + "\n", "utf-8")
    return csv_path, md_path


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="บอทติดตามการอัปเดต Roblox executor แจ้งเข้า Discord")
    ap.add_argument("--dry-run", action="store_true", help="แสดงข้อความในหน้าจอ ไม่ส่ง Discord")
    ap.add_argument("--force", action="store_true", help="ส่งสรุปเต็มทุกครั้ง แม้ไม่มีการเปลี่ยนแปลง")
    ap.add_argument("--report-only", action="store_true", help="เขียนรายงาน CSV/MD เท่านั้น ไม่ส่ง Discord")
    ap.add_argument("--no-save", action="store_true", help="ไม่บันทึก state.json (ไว้ทดสอบเท่านั้น)")
    ap.add_argument("--no-logos", action="store_true", help="ไม่ต้องดึงรูปโลโก้รอบนี้")
    ap.add_argument("--refresh-logos", action="store_true", help="ดึงโลโก้ใหม่ทั้งหมด (ล้างแคชเดิม)")
    ap.add_argument("--webhook", help="URL ของ Discord webhook (ทับค่าใน config)")
    ap.add_argument("--print", dest="print_only", action="store_true", help="พิมพ์ตารางสถานะในหน้าจอ")
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.webhook:
        cfg["discord_webhook_url"] = args.webhook.strip()
    if args.no_logos:
        cfg["attach_logos"] = False

    log("กำลังดึงข้อมูลจาก WEAO API...")
    cur = build_snapshot(cfg)
    prev = load_state()
    first_run = not prev
    changes = diff_snapshots(prev, cur, cfg)

    total = len(cur["executors"])
    if total == 0:
        log("ไม่พบข้อมูล executor เลย — ตรวจการตั้งค่า platforms ใน config.json")
        return 1
    working = sum(1 for r in cur["executors"].values() if r["updated"])
    log(f"ได้ข้อมูล {total} ตัว (ใช้ได้กับ build ปัจจุบัน {working} ตัว)")

    cached_logos = {} if args.refresh_logos else (prev.get("logos") or {})
    logos = LogoCache(cached_logos)

    if first_run:
        log("รอบแรก: บันทึกสถานะเริ่มต้นและส่งสรุปเต็ม")

    summary_bits = []
    for key, label in (("new_version", "เวอร์ชันใหม่"), ("patched", "กลับมาใช้ได้"),
                       ("outdated", "ใช้ไม่ได้"), ("rbx", "Roblox build ใหม่")):
        if changes.get(key):
            summary_bits.append(f"{label} {len(changes[key])}")
    log("เปลี่ยนแปลง: " + (", ".join(summary_bits) if summary_bits else "ไม่มี"))

    if args.print_only or args.dry_run:
        for r in sorted(cur["executors"].values(), key=lambda x: (not x["updated"], x["name"].lower())):
            when = parse_ts(r.get("updated_at"))
            mark = "OK " if r["updated"] else ".. "
            print(f"{mark}{r['name']:<12} {r['platform']:<8} {fmt_version(r['version']):<18} "
                  f"sUNC {str(r['sunc'] or '-'):>4}  {human_ago(when)}")

    if cfg.get("write_reports", True):
        paths = write_reports(cur, changes, logos)
        if paths:
            log(f"เขียนรายงาน: {paths[0].name}, {paths[1].name}")

    should_post = (not args.report_only) and (first_run or args.force or has_changes(changes))
    if should_post:
        embeds = build_embeds(cur, changes, cfg, full=first_run or args.force, logos=logos)
        post_discord(cfg["discord_webhook_url"], embeds, cfg.get("discord_username", "Executor Watch"),
                     dry_run=args.dry_run)
        if logos.fetched:
            log(f"ดึงโลโก้ใหม่ {logos.fetched} เจ้า (เก็บไว้ใช้รอบหน้าด้วย)")
    elif not args.report_only:
        log("ไม่มีการเปลี่ยนแปลง — ไม่ส่งข้อความ")

    if not args.no_save:
        cur["logos"] = logos.export()
        save_state(cur)
        log("บันทึกสถานะล่าสุดลง state.json แล้ว")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
