#!/usr/bin/env python3
"""
Mac Mini Telegram Control Bot v5.0.0

Admin-only keyboard bot for macOS / Mac Mini control and monitoring.

Important safety features:
- Private chat only
- Numeric Telegram ID allow-list
- Keyboard-only actions
- Dangerous actions require confirmation
- Rate limiting
- Emergency disable switches
- Audit log and unauthorized access log
- No custom shell commands from Telegram
"""
from __future__ import annotations
import asyncio
import glob
import json
import logging
import os
import plistlib
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_VERSION = "5.0.0"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_NAME = os.getenv("BOT_NAME", "Mac Mini Control Bot").strip()
SERVICE_LABEL = os.getenv("SERVICE_LABEL", "com.macmini.controlbot").strip()
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"

BOT_ENABLED = os.getenv("BOT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
STATUS_FEATURES_ENABLED = os.getenv("STATUS_FEATURES_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
CONTROL_ACTIONS_ENABLED = os.getenv("CONTROL_ACTIONS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
SCREENSHOT_ENABLED = os.getenv("SCREENSHOT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
ALERTS_ENABLED = os.getenv("ALERTS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
DISK_HEALTH_ENABLED = os.getenv("DISK_HEALTH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

QUIET_HOURS_ENABLED = os.getenv("QUIET_HOURS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
QUIET_HOURS_START = os.getenv("QUIET_HOURS_START", "23:00").strip()
QUIET_HOURS_END = os.getenv("QUIET_HOURS_END", "07:00").strip()

ENABLE_PUBLIC_IP = os.getenv("ENABLE_PUBLIC_IP", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_VOLUME_ALERTS = os.getenv("ENABLE_VOLUME_ALERTS", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_INTERNET_ALERTS = os.getenv("ENABLE_INTERNET_ALERTS", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_LOCK_UNLOCK_ALERTS = os.getenv("ENABLE_LOCK_UNLOCK_ALERTS", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_LOGIN_LOGOUT_ALERTS = os.getenv("ENABLE_LOGIN_LOGOUT_ALERTS", "true").lower() in {"1", "true", "yes", "on"}
ENABLE_DAILY_REPORT = os.getenv("ENABLE_DAILY_REPORT", "true").lower() in {"1", "true", "yes", "on"}

ALERT_CHECK_INTERVAL_SECONDS = int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS", "60"))
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "30"))
HIGH_CPU_PERCENT = float(os.getenv("HIGH_CPU_PERCENT", "90"))
HIGH_CPU_CONSECUTIVE_CHECKS = int(os.getenv("HIGH_CPU_CONSECUTIVE_CHECKS", "5"))
HIGH_RAM_PERCENT = float(os.getenv("HIGH_RAM_PERCENT", "90"))
LOWER_RESET_MARGIN_PERCENT = float(os.getenv("LOWER_RESET_MARGIN_PERCENT", "10"))
DAILY_REPORT_TIME = os.getenv("DAILY_REPORT_TIME", "09:00").strip()
NETWORK_SPEED_SAMPLE_SECONDS = float(os.getenv("NETWORK_SPEED_SAMPLE_SECONDS", "2"))
SCREENSHOT_KEEP_LAST = int(os.getenv("SCREENSHOT_KEEP_LAST", "10"))
MONITOR_ALL_VOLUMES = os.getenv("MONITOR_ALL_VOLUMES", "true").lower() in {"1", "true", "yes", "on"}

RATE_LIMIT_GENERAL_PER_MINUTE = int(os.getenv("RATE_LIMIT_GENERAL_PER_MINUTE", "30"))
RATE_LIMIT_CONTROL_PER_MINUTE = int(os.getenv("RATE_LIMIT_CONTROL_PER_MINUTE", "5"))
RATE_LIMIT_SCREENSHOT_PER_MINUTE = int(os.getenv("RATE_LIMIT_SCREENSHOT_PER_MINUTE", "3"))
RATE_LIMIT_RESTART_SHUTDOWN_PER_2MIN = int(os.getenv("RATE_LIMIT_RESTART_SHUTDOWN_PER_2MIN", "1"))

DISK_ALERT_PERCENTAGES = [
    int(x.strip())
    for x in os.getenv("DISK_ALERT_PERCENTAGES", "85,90,95").split(",")
    if x.strip().isdigit()
]

LOG_PATH = BASE_DIR / "macmini_bot.log"
AUDIT_LOG_PATH = BASE_DIR / "audit_log.jsonl"
UNAUTHORIZED_LOG_PATH = BASE_DIR / "unauthorized_access_log.jsonl"
STATE_DIR = BASE_DIR / "state"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
PUBLIC_IP_STATE_PATH = STATE_DIR / "public_ip.txt"
INTERNET_STATE_PATH = STATE_DIR / "internet.json"
VOLUME_STATE_PATH = STATE_DIR / "volumes.json"
LOCK_STATE_PATH = STATE_DIR / "lock_state.json"
USER_STATE_PATH = STATE_DIR / "console_user.json"

STATE_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR.mkdir(exist_ok=True)

BTN_BACK = "⬅️ Back"
BTN_CANCEL = "❌ Cancel"

BTN_QUICK_STATUS = "⚡ Quick Status"
BTN_LOCAL_IP = "🏠 Local IP"
BTN_LOCK = "🔒 Lock Mac"

BTN_SYSTEM_MENU = "🖥 System"
BTN_STORAGE_MENU = "💾 Storage"
BTN_NETWORK_MENU = "🌐 Network"
BTN_CONTROLS_MENU = "🛠 Controls"
BTN_LOGS_MENU = "📜 Logs"
BTN_HELP = "❓ Help"

BTN_STATUS = "🖥 Status"
BTN_CPU = "📊 CPU Usage"
BTN_TOP_CPU = "🔥 Top CPU Apps"
BTN_TOP_RAM = "🧠 Top RAM Apps"
BTN_ACTIVE_APP = "🪟 Active App"
BTN_RUNNING_APPS = "📋 Running Apps"
BTN_SCREENSHOT = "📸 Screenshot"
BTN_BOT_HEALTH = "🩺 Bot Health"
BTN_SERVICE_STATUS = "⚙️ Service Status"
BTN_BOT_CONFIG = "⚙️ Bot Config"
BTN_VERSION = "ℹ️ Bot Version"

BTN_STORAGE_DETAILS = "💾 Storage Details"
BTN_ALL_MOUNTED_DISKS = "🗂 All Mounted Disks"
BTN_DISK_HEALTH = "🩻 Disk Health"
BTN_TRASH_SIZE = "🧹 Trash Size"
BTN_DISK_ALERT_STATUS = "⚠️ Disk Alert Status"

BTN_IP = "🌐 IP Details"
BTN_NETWORK_SPEED = "📡 Network Speed"
BTN_INTERNET_TEST = "📶 Internet Test"
BTN_NETWORK_INTERFACES = "📶 Wi-Fi/Ethernet"

BTN_SLEEP = "🌙 Sleep Mac"
BTN_DISPLAY_SLEEP = "🖥 Display Sleep"
BTN_RESTART = "🔁 Restart Mac"
BTN_SHUTDOWN = "⏻ Shutdown Mac"
BTN_RESTART_BOT = "♻️ Restart Bot"

BTN_EXPORT_LOGS = "📦 Export Logs"
BTN_LAST_LOGS = "📄 Last 50 Logs"
BTN_AUDIT_SUMMARY = "🧾 Audit Summary"
BTN_UNAUTHORIZED_SUMMARY = "⛔ Unauthorized Summary"
BTN_DAILY_REPORT_NOW = "📅 Daily Report Now"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_QUICK_STATUS],
        [BTN_LOCAL_IP, BTN_LOCK],
        [BTN_SYSTEM_MENU, BTN_STORAGE_MENU],
        [BTN_NETWORK_MENU, BTN_CONTROLS_MENU],
        [BTN_LOGS_MENU, BTN_HELP],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

SYSTEM_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_STATUS, BTN_CPU],
        [BTN_TOP_CPU, BTN_TOP_RAM],
        [BTN_ACTIVE_APP, BTN_RUNNING_APPS],
        [BTN_SCREENSHOT],
        [BTN_BOT_HEALTH, BTN_SERVICE_STATUS],
        [BTN_BOT_CONFIG, BTN_VERSION],
        [BTN_BACK],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

STORAGE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_STORAGE_DETAILS],
        [BTN_ALL_MOUNTED_DISKS],
        [BTN_DISK_HEALTH],
        [BTN_TRASH_SIZE, BTN_DISK_ALERT_STATUS],
        [BTN_BACK],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

NETWORK_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_LOCAL_IP, BTN_IP],
        [BTN_NETWORK_INTERFACES],
        [BTN_NETWORK_SPEED, BTN_INTERNET_TEST],
        [BTN_BACK],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

CONTROLS_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_LOCK, BTN_SLEEP],
        [BTN_DISPLAY_SLEEP],
        [BTN_RESTART, BTN_SHUTDOWN],
        [BTN_RESTART_BOT],
        [BTN_BACK],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

LOGS_KEYBOARD = ReplyKeyboardMarkup(
    [
        [BTN_LAST_LOGS],
        [BTN_EXPORT_LOGS],
        [BTN_AUDIT_SUMMARY, BTN_UNAUTHORIZED_SUMMARY],
        [BTN_DAILY_REPORT_NOW],
        [BTN_BACK],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

DANGEROUS_ACTIONS = {
    BTN_LOCK: ("lock", "✅ Confirm Lock", "⚠️ Confirm locking the Mac Mini."),
    BTN_SLEEP: ("sleep", "✅ Confirm Sleep", "⚠️ Confirm putting the Mac Mini to sleep."),
    BTN_DISPLAY_SLEEP: ("display_sleep", "✅ Confirm Display Sleep", "⚠️ Confirm turning off the display."),
    BTN_RESTART: ("restart", "✅ Confirm Restart", "⚠️ Confirm restarting the Mac Mini."),
    BTN_SHUTDOWN: ("shutdown", "✅ Confirm Shutdown", "⚠️ Confirm shutting down the Mac Mini."),
    BTN_RESTART_BOT: ("restart_bot", "✅ Confirm Restart Bot", "⚠️ Confirm restarting only the Telegram bot service."),
}
CONFIRM_BUTTON_TO_ACTION = {value[1]: value[0] for value in DANGEROUS_ACTIONS.values()}

RATE_LIMIT_BUCKETS: dict[tuple[int, str], deque[float]] = defaultdict(deque)
ALERT_LAST_SENT: dict[str, datetime] = {}


def setup_logging() -> None:
    from logging.handlers import RotatingFileHandler

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024))),
        backupCount=int(os.getenv("LOG_BACKUP_COUNT", "3")),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)


setup_logging()
logger = logging.getLogger("macmini-control-bot")


def parse_allowed_ids(raw: str) -> set[int]:
    ids = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.add(int(item))
        except ValueError:
            logger.warning("Invalid Telegram ID ignored: %s", item)
    return ids


ALLOWED_TELEGRAM_IDS = parse_allowed_ids(os.getenv("ALLOWED_TELEGRAM_IDS", ""))


def validate_config() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing in .env")
    if not ALLOWED_TELEGRAM_IDS:
        raise RuntimeError("ALLOWED_TELEGRAM_IDS is empty in .env")
    if ALERT_CHECK_INTERVAL_SECONDS < 30:
        raise RuntimeError("ALERT_CHECK_INTERVAL_SECONDS should be at least 30 seconds")


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_cmd(command: list[str], timeout: int = 10, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, capture_output=True, text=True, timeout=timeout)


def json_read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def json_write(path: Path, data: Any) -> None:
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed writing JSON %s: %s", path, exc)


def text_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def text_write(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed writing text %s: %s", path, exc)


def human_bytes(value: float) -> str:
    size = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 1024 or unit == "PB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = value.split(":", 1)
        return max(0, min(23, int(h))), max(0, min(59, int(m)))
    except Exception:
        return 0, 0


def is_quiet_hours() -> bool:
    if not QUIET_HOURS_ENABLED:
        return False

    start_h, start_m = parse_hhmm(QUIET_HOURS_START)
    end_h, end_m = parse_hhmm(QUIET_HOURS_END)

    now = datetime.now()
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

    if start <= end:
        return start <= now < end

    return now >= start or now < end


def get_uptime() -> str:
    delta = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"


def get_console_user() -> str:
    try:
        user = run_cmd(["stat", "-f", "%Su", "/dev/console"], timeout=5).stdout.strip()
        return user or "Unavailable"
    except Exception:
        return os.getenv("USER", "Unavailable")


def is_console_logged_in() -> bool:
    user = get_console_user()
    return bool(user and user not in {"root", "loginwindow", "Unavailable"})


def get_user_details(update: Update) -> dict[str, Any]:
    user = update.effective_user
    if not user:
        return {"telegram_id": None, "username": None, "full_name": None, "is_bot": None}
    return {
        "telegram_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "is_bot": user.is_bot,
    }


def is_private_chat(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type == "private")


def is_allowed(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in ALLOWED_TELEGRAM_IDS)


def write_jsonl(path: Path, data: dict[str, Any]) -> None:
    payload = dict(data)
    payload.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def audit(update: Update, action: str, result: str, extra: dict[str, Any] | None = None) -> None:
    record = {
        "event_type": "admin_action",
        "action": action,
        "result": result,
        "user": get_user_details(update),
    }
    if extra:
        record["extra"] = extra
    write_jsonl(AUDIT_LOG_PATH, record)


def log_rejected(update: Update, reason: str, text: str = "") -> None:
    write_jsonl(
        UNAUTHORIZED_LOG_PATH,
        {
            "event_type": "rejected_access",
            "reason": reason,
            "message_text": text,
            "user": get_user_details(update),
            "chat_type": update.effective_chat.type if update.effective_chat else None,
            "chat_id": update.effective_chat.id if update.effective_chat else None,
        },
    )


def rate_limit_key(update: Update) -> int:
    return update.effective_user.id if update.effective_user else 0


def check_rate_limit(update: Update, bucket_name: str, max_count: int, window_seconds: int) -> tuple[bool, int]:
    uid = rate_limit_key(update)
    now = time.time()
    bucket = RATE_LIMIT_BUCKETS[(uid, bucket_name)]

    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()

    if len(bucket) >= max_count:
        retry_after = int(window_seconds - (now - bucket[0])) if bucket else window_seconds
        return False, max(1, retry_after)

    bucket.append(now)
    return True, 0


async def precheck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    text = update.message.text.strip() if update.message and update.message.text else ""

    if not is_private_chat(update):
        log_rejected(update, "non_private_chat", text)
        if update.message:
            await update.message.reply_text("⛔ This bot only works in private chat.")
        return False

    if not is_allowed(update):
        log_rejected(update, "telegram_id_not_allowed", text)
        if update.message:
            telegram_id = update.effective_user.id if update.effective_user else "unknown"
            await update.message.reply_text(
                "⛔ Access denied.\n\n"
                f"Your Telegram ID is:\n{telegram_id}\n\n"
                "Ask the admin to add this ID to ALLOWED_TELEGRAM_IDS."
            )
        return False

    if not BOT_ENABLED and text not in {"/start", "/menu", BTN_BOT_CONFIG, BTN_HELP}:
        audit(update, "bot_disabled_reject", "rejected", {"text": text})
        if update.message:
            await update.message.reply_text("🚧 Bot is currently disabled by BOT_ENABLED=false.")
        return False

    ok, retry_after = check_rate_limit(update, "general", RATE_LIMIT_GENERAL_PER_MINUTE, 60)
    if not ok:
        audit(update, "rate_limit_general", "rejected", {"retry_after": retry_after})
        if update.message:
            await update.message.reply_text(f"⏳ Rate limit reached. Try again in {retry_after}s.")
        return False

    return True


def require_status_enabled() -> tuple[bool, str]:
    if not STATUS_FEATURES_ENABLED:
        return False, "Status features are disabled by STATUS_FEATURES_ENABLED=false."
    return True, ""


def require_controls_enabled() -> tuple[bool, str]:
    if not CONTROL_ACTIONS_ENABLED:
        return False, "Control actions are disabled by CONTROL_ACTIONS_ENABLED=false."
    return True, ""


def require_screenshot_enabled() -> tuple[bool, str]:
    if not SCREENSHOT_ENABLED:
        return False, "Screenshot feature is disabled by SCREENSHOT_ENABLED=false."
    return True, ""


def confirmation_keyboard(confirm_button: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[confirm_button], [BTN_CANCEL]], resize_keyboard=True, is_persistent=True)


def storage_paths() -> list[str]:
    paths = ["/"]
    if MONITOR_ALL_VOLUMES:
        for path in glob.glob("/Volumes/*"):
            if os.path.ismount(path):
                paths.append(path)

    result = []
    seen = set()
    for path in paths:
        real = os.path.realpath(path)
        if real not in seen:
            seen.add(real)
            result.append(path)
    return result


def get_disk_partitions() -> list:
    partitions = psutil.disk_partitions(all=False)
    seen = set()
    result = []

    for part in partitions:
        if not part.mountpoint:
            continue
        key = (part.device, part.mountpoint)
        if key in seen:
            continue
        seen.add(key)
        result.append(part)

    root_seen = any(part.mountpoint == "/" for part in result)
    if not root_seen:
        for part in psutil.disk_partitions(all=True):
            if part.mountpoint == "/":
                result.insert(0, part)
                break

    return result


def volume_snapshot() -> dict[str, dict[str, Any]]:
    data = {}
    for part in get_disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            data[part.mountpoint] = {
                "device": part.device,
                "fstype": part.fstype,
                "opts": part.opts,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        except Exception:
            pass
    return data


def get_lan_ips() -> list[str]:
    items = []
    for name, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            if address.family == socket.AF_INET:
                ip = address.address
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    items.append(f"{name}: {ip}")
    return items


def get_primary_lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        pass

    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "Unavailable"


def get_public_ip() -> str:
    if not ENABLE_PUBLIC_IP:
        return "Disabled"
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as response:
            return response.read().decode("utf-8").strip()
    except Exception:
        return "Unavailable"


def internet_ok() -> bool:
    try:
        urllib.request.urlopen("https://api.telegram.org", timeout=6).read(1)
        return True
    except Exception:
        try:
            socket.gethostbyname("google.com")
            return True
        except Exception:
            return False


def get_screen_lock_state() -> str:
    """
    Returns: locked / unlocked / unknown
    Uses ioreg key CGSSessionScreenIsLocked where available.
    """
    try:
        result = run_cmd(["ioreg", "-n", "Root", "-d1"], timeout=5, check=False)
        output = result.stdout + "\n" + result.stderr

        if "CGSSessionScreenIsLocked" in output:
            match = re.search(r'CGSSessionScreenIsLocked"\s*=\s*(Yes|No|true|false|1|0)', output, re.I)
            if match:
                value = match.group(1).lower()
                return "locked" if value in {"yes", "true", "1"} else "unlocked"

            line = next((ln for ln in output.splitlines() if "CGSSessionScreenIsLocked" in ln), "")
            if "Yes" in line or "true" in line or "=1" in line:
                return "locked"
            if "No" in line or "false" in line or "=0" in line:
                return "unlocked"

        return "unknown"
    except Exception:
        return "unknown"


def get_local_ip_report() -> str:
    interfaces = "\n".join(get_lan_ips()) or "No active LAN IP found"
    return f"🏠 Local IP Details\n\nPrimary Local IP: {get_primary_lan_ip()}\n\nAll Local Interfaces:\n{interfaces}"


def get_quick_status_report() -> str:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return (
        "⚡ Quick Status\n\n"
        f"CPU: {pct(cpu)}\n"
        f"RAM: {human_bytes(memory.used)} / {human_bytes(memory.total)} ({pct(memory.percent)})\n"
        f"Disk /: {human_bytes(disk.used)} / {human_bytes(disk.total)} ({pct(disk.percent)})\n"
        f"Uptime: {get_uptime()}\n"
        f"User: {get_console_user()}\n"
        f"Login State: {'Logged in' if is_console_logged_in() else 'Logged out / loginwindow'}\n"
        f"Lock State: {get_screen_lock_state()}\n"
        f"Local IP: {get_primary_lan_ip()}\n"
        f"Public IP: {get_public_ip()}"
    )


def get_status_report() -> str:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return (
        "🖥 Mac Mini Status\n\n"
        f"Bot: {BOT_NAME}\n"
        f"Version: {BOT_VERSION}\n"
        f"Hostname: {socket.gethostname()}\n"
        f"macOS: {platform.mac_ver()[0] or 'Unavailable'}\n"
        f"Machine: {platform.machine()}\n"
        f"Python: {platform.python_version()}\n"
        f"Logged-in User: {get_console_user()}\n"
        f"Login State: {'Logged in' if is_console_logged_in() else 'Logged out / loginwindow'}\n"
        f"Lock State: {get_screen_lock_state()}\n"
        f"Uptime: {get_uptime()}\n\n"
        f"CPU: {pct(cpu)}\n"
        f"RAM: {human_bytes(memory.used)} / {human_bytes(memory.total)} ({pct(memory.percent)})\n"
        f"Root Disk: {human_bytes(disk.used)} / {human_bytes(disk.total)} ({pct(disk.percent)})\n"
        f"Local IP: {get_primary_lan_ip()}"
    )


def get_cpu_report() -> str:
    total = psutil.cpu_percent(interval=1)
    per_core = psutil.cpu_percent(interval=1, percpu=True)
    memory = psutil.virtual_memory()

    try:
        load_1, load_5, load_15 = os.getloadavg()
        load_text = f"{load_1:.2f}, {load_5:.2f}, {load_15:.2f}"
    except Exception:
        load_text = "Unavailable"

    core_text = "\n".join(f"Core {idx}: {pct(value)}" for idx, value in enumerate(per_core, 1))

    return (
        "📊 CPU / Memory Usage\n\n"
        f"CPU Total: {pct(total)}\n"
        f"CPU Cores: {psutil.cpu_count(logical=True)} logical / {psutil.cpu_count(logical=False) or 'unknown'} physical\n"
        f"Load Avg: {load_text}\n\n"
        f"RAM Total: {human_bytes(memory.total)}\n"
        f"RAM Used: {human_bytes(memory.used)} / {pct(memory.percent)}\n"
        f"RAM Available: {human_bytes(memory.available)}\n\n"
        f"{core_text}"
    )


def get_storage_report() -> str:
    lines = ["💾 Storage Details", ""]
    for path in storage_paths():
        try:
            usage = psutil.disk_usage(path)
            lines += [
                f"Mount: {path}",
                f"Total: {human_bytes(usage.total)}",
                f"Used: {human_bytes(usage.used)} / {pct(usage.percent)}",
                f"Free: {human_bytes(usage.free)}",
                "",
            ]
        except Exception as exc:
            lines += [f"Mount: {path}", f"Error: {exc}", ""]
    return "\n".join(lines).strip()


def get_all_mounted_disks_report() -> str:
    lines = ["🗂 All Mounted Disks / Volumes", ""]
    partitions = get_disk_partitions()

    if not partitions:
        return "🗂 All Mounted Disks / Volumes\n\nNo mounted disks found."

    for index, part in enumerate(partitions, 1):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            lines += [
                f"{index}. Mount: {part.mountpoint}",
                f"   Device: {part.device or 'Unavailable'}",
                f"   Filesystem: {part.fstype or 'Unavailable'}",
                f"   Options: {part.opts or 'Unavailable'}",
                f"   Total: {human_bytes(usage.total)}",
                f"   Used: {human_bytes(usage.used)} ({pct(usage.percent)})",
                f"   Free: {human_bytes(usage.free)}",
                "",
            ]
        except PermissionError:
            lines += [
                f"{index}. Mount: {part.mountpoint}",
                f"   Device: {part.device or 'Unavailable'}",
                f"   Filesystem: {part.fstype or 'Unavailable'}",
                "   Usage: Permission denied",
                "",
            ]
        except Exception as exc:
            lines += [
                f"{index}. Mount: {part.mountpoint}",
                f"   Device: {part.device or 'Unavailable'}",
                f"   Filesystem: {part.fstype or 'Unavailable'}",
                f"   Usage: Unavailable ({exc})",
                "",
            ]

    return "\n".join(lines).strip()


def run_diskutil_info(device_or_mount: str) -> dict[str, Any]:
    if not command_exists("diskutil"):
        return {}

    try:
        result = run_cmd(["diskutil", "info", "-plist", device_or_mount], timeout=10, check=True)
        return plistlib.loads(result.stdout.encode("utf-8"))
    except Exception:
        return {}


def run_smartctl(device: str) -> str:
    if not command_exists("smartctl"):
        return "smartctl not installed"

    try:
        result = run_cmd(["smartctl", "-H", device], timeout=20, check=False)
        output = (result.stdout + "\n" + result.stderr).strip()
        return output[:1200] if output else "No smartctl output"
    except Exception as exc:
        return f"smartctl error: {exc}"


def get_disk_health_report() -> str:
    if not DISK_HEALTH_ENABLED:
        return "🩻 Disk Health\n\nDisk health feature is disabled by DISK_HEALTH_ENABLED=false."

    lines = ["🩻 Disk Health", ""]
    partitions = get_disk_partitions()

    if not partitions:
        return "🩻 Disk Health\n\nNo mounted disks found."

    seen_devices = set()

    for part in partitions:
        device = part.device or part.mountpoint
        mount = part.mountpoint

        info = run_diskutil_info(mount)
        device_identifier = info.get("DeviceIdentifier") or Path(device).name
        parent_whole_disk = info.get("ParentWholeDisk") or info.get("DeviceIdentifier") or device_identifier
        whole_device = f"/dev/{parent_whole_disk}" if parent_whole_disk and not str(parent_whole_disk).startswith("/dev/") else str(parent_whole_disk or device)

        key = (device_identifier, mount)
        if key in seen_devices:
            continue
        seen_devices.add(key)

        try:
            usage = psutil.disk_usage(mount)
            usage_text = f"{human_bytes(usage.used)} used / {human_bytes(usage.free)} free / {human_bytes(usage.total)} total ({pct(usage.percent)})"
        except Exception:
            usage_text = "Usage unavailable"

        smart_status = info.get("SMARTStatus", "Unavailable")
        volume_name = info.get("VolumeName") or info.get("MediaName") or "Unavailable"
        protocol = info.get("DeviceProtocol", "Unavailable")
        internal = info.get("Internal", "Unavailable")
        solid_state = info.get("SolidState", "Unavailable")
        writable = info.get("Writable", "Unavailable")
        encrypted = info.get("FileVault", info.get("Encrypted", "Unavailable"))

        lines += [
            f"Mount: {mount}",
            f"Device: {device}",
            f"Whole Disk: {whole_device}",
            f"Volume/Media: {volume_name}",
            f"Filesystem: {part.fstype or 'Unavailable'}",
            f"Usage: {usage_text}",
            f"SMART Status: {smart_status}",
            f"Protocol: {protocol}",
            f"Internal: {internal}",
            f"SSD: {solid_state}",
            f"Writable: {writable}",
            f"Encrypted/FileVault: {encrypted}",
        ]

        if command_exists("smartctl"):
            smart_output = run_smartctl(whole_device)
            lines += ["smartctl:", smart_output]
        else:
            lines += ["smartctl: Not installed. Optional: brew install smartmontools"]

        lines.append("")

    return "\n".join(str(x) for x in lines).strip()


def get_disk_alert_status_report() -> str:
    lines = ["⚠️ Disk Alert Status", "", f"Thresholds: {', '.join(str(x) + '%' for x in DISK_ALERT_PERCENTAGES)}", ""]
    for part in get_disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            crossed = [x for x in DISK_ALERT_PERCENTAGES if usage.percent >= x]
            status = f"ALERT >= {max(crossed)}%" if crossed else "OK"
            lines.append(f"{part.mountpoint}: {pct(usage.percent)} used - {status}")
        except Exception as exc:
            lines.append(f"{part.mountpoint}: Unavailable ({exc})")
    return "\n".join(lines)


def get_ip_report() -> str:
    interfaces = "\n".join(get_lan_ips()) or "No active LAN IP found"
    return (
        "🌐 IP Details\n\n"
        f"Hostname: {socket.gethostname()}\n"
        f"Local IP: {get_primary_lan_ip()}\n"
        f"Public IP: {get_public_ip()}\n\n"
        f"Interfaces:\n{interfaces}"
    )


def internet_test() -> str:
    dns_ok = False
    tg_ok = False
    dns_error = ""
    tg_error = ""

    try:
        socket.gethostbyname("google.com")
        dns_ok = True
    except Exception as exc:
        dns_error = str(exc)

    try:
        urllib.request.urlopen("https://api.telegram.org", timeout=6).read(1)
        tg_ok = True
    except Exception as exc:
        tg_error = str(exc)

    return (
        "📶 Internet Test\n\n"
        f"{'✅' if dns_ok else '❌'} DNS google.com: {'OK' if dns_ok else dns_error}\n"
        f"{'✅' if tg_ok else '❌'} HTTPS api.telegram.org: {'OK' if tg_ok else tg_error}"
    )


async def get_network_speed_report() -> str:
    first = psutil.net_io_counters()
    await asyncio.sleep(max(NETWORK_SPEED_SAMPLE_SECONDS, 0.1))
    second = psutil.net_io_counters()
    seconds = max(NETWORK_SPEED_SAMPLE_SECONDS, 0.1)

    upload = (second.bytes_sent - first.bytes_sent) / seconds
    download = (second.bytes_recv - first.bytes_recv) / seconds

    return (
        "📡 Network Speed\n\n"
        f"Sample Time: {seconds:.1f}s\n"
        f"Upload: {human_bytes(upload)}/s\n"
        f"Download: {human_bytes(download)}/s\n\n"
        f"Total Sent: {human_bytes(second.bytes_sent)}\n"
        f"Total Received: {human_bytes(second.bytes_recv)}"
    )


def get_wifi_ssid(device: str) -> str:
    airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"

    if os.path.exists(airport):
        try:
            output = run_cmd([airport, "-I"], timeout=5).stdout
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    return line.split("SSID:", 1)[1].strip()
        except Exception:
            pass

    if command_exists("networksetup"):
        try:
            output = run_cmd(["networksetup", "-getairportnetwork", device], timeout=5).stdout.strip()
            if ":" in output and "not associated" not in output.lower():
                return output.split(":", 1)[1].strip()
        except Exception:
            pass

    return ""


def get_network_interface_report() -> str:
    lines = ["📶 Wi-Fi / Ethernet Details", ""]
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    af_link = getattr(socket, "AF_LINK", None)

    for name, addresses in addrs.items():
        if name.startswith("lo"):
            continue

        ipv4 = []
        mac = "Unavailable"

        for address in addresses:
            if address.family == socket.AF_INET:
                ipv4.append(address.address)
            elif af_link is not None and address.family == af_link:
                mac = address.address

        stat = stats.get(name)
        is_up = stat.isup if stat else False
        speed = f"{stat.speed} Mbps" if stat and stat.speed else "Unavailable"

        if not ipv4 and not is_up:
            continue

        lines += [
            f"Interface: {name}",
            f"Status: {'Up' if is_up else 'Down'}",
            f"IP: {', '.join(ipv4) if ipv4 else 'No IPv4'}",
            f"MAC: {mac or 'Unavailable'}",
            f"Speed: {speed}",
        ]

        ssid = get_wifi_ssid(name)
        if ssid:
            lines.append(f"Wi-Fi SSID: {ssid}")

        lines.append("")

    if len(lines) <= 2:
        lines.append("No active network interfaces found.")

    return "\n".join(lines).strip()


def get_trash_size_report() -> str:
    trash = Path.home() / ".Trash"
    total = 0

    if not trash.exists():
        return "🧹 Trash Size\n\nTrash folder was not found."

    for root, dirs, files in os.walk(trash):
        for filename in files:
            try:
                total += (Path(root) / filename).stat().st_size
            except Exception:
                pass

    return f"🧹 Trash Size\n\nChecked: {trash}\nApprox Size: {human_bytes(total)}"


def list_top_processes(kind: str, limit: int = 5) -> str:
    if kind == "cpu":
        for proc in psutil.process_iter():
            try:
                proc.cpu_percent(interval=None)
            except Exception:
                pass
        time.sleep(1)

    rows = []

    for proc in psutil.process_iter(["pid", "name", "username", "memory_info"]):
        try:
            info = proc.info
            if kind == "cpu":
                value = proc.cpu_percent(interval=None)
                if value <= 0:
                    continue
                display = f"{value:.1f}%"
                sort_value = value
            else:
                rss = info["memory_info"].rss if info.get("memory_info") else 0
                if rss <= 0:
                    continue
                display = human_bytes(rss)
                sort_value = rss

            rows.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name") or "unknown",
                    "username": info.get("username") or "unknown",
                    "display": display,
                    "sort": sort_value,
                }
            )
        except Exception:
            continue

    rows.sort(key=lambda row: row["sort"], reverse=True)
    rows = rows[:limit]

    title = "🔥 Top CPU Apps" if kind == "cpu" else "🧠 Top RAM Apps"
    label = "CPU" if kind == "cpu" else "RAM"

    if not rows:
        return f"{title}\n\nNo process data available."

    lines = [title, ""]
    for index, row in enumerate(rows, 1):
        lines += [
            f"{index}. {row['name']}",
            f"   PID: {row['pid']} | {label}: {row['display']}",
            f"   User: {row['username']}",
        ]

    return "\n".join(lines)


def get_active_app_report() -> str:
    script = "\n".join(
        [
            'tell application "System Events"',
            'set frontApp to name of first application process whose frontmost is true',
            'set windowTitle to ""',
            'try',
            'tell process frontApp',
            'set windowTitle to name of front window',
            'end tell',
            'end try',
            'end tell',
            'return frontApp & linefeed & windowTitle',
        ]
    )

    try:
        output = run_cmd(["osascript", "-e", script], timeout=10).stdout.strip()
        parts = output.splitlines()
        app = parts[0] if parts else "Unavailable"
        window = parts[1] if len(parts) > 1 and parts[1] else "Unavailable"
        return f"🪟 Active App\n\nApp: {app}\nWindow: {window}\nUser: {get_console_user()}"
    except Exception as exc:
        return (
            "🪟 Active App\n\n"
            "Unable to read active app/window.\n\n"
            "Allow Terminal/Python in:\n"
            "System Settings > Privacy & Security > Accessibility\n\n"
            f"Error: {exc}"
        )


def get_running_apps_report() -> str:
    script = "\n".join(
        [
            'tell application "System Events"',
            'set appNames to name of every application process whose background only is false',
            'end tell',
            "set AppleScript's text item delimiters to linefeed",
            'return appNames as text',
        ]
    )

    try:
        output = run_cmd(["osascript", "-e", script], timeout=10).stdout
        apps = sorted(set(line.strip() for line in output.splitlines() if line.strip()), key=str.lower)
        if not apps:
            return "📋 Running Apps\n\nNo GUI apps found."
        return "📋 Running Apps\n\n" + "\n".join(f"- {app}" for app in apps[:60])
    except Exception as exc:
        return (
            "📋 Running Apps\n\n"
            "Unable to read running GUI apps.\n\n"
            "Allow Terminal/Python in:\n"
            "System Settings > Privacy & Security > Accessibility\n\n"
            f"Error: {exc}"
        )


def cleanup_old_screenshots() -> None:
    try:
        screenshots = sorted(SCREENSHOT_DIR.glob("screenshot_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in screenshots[SCREENSHOT_KEEP_LAST:]:
            old.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Screenshot cleanup failed: %s", exc)


def capture_screenshot() -> tuple[bool, Path | None, str]:
    path = SCREENSHOT_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    try:
        run_cmd(["screencapture", "-x", str(path)], timeout=20)
        cleanup_old_screenshots()
        return True, path, "OK"
    except Exception as exc:
        return False, None, str(exc)


def get_service_status_report() -> str:
    loaded = False
    details = ""
    try:
        result = subprocess.run(["launchctl", "list", SERVICE_LABEL], capture_output=True, text=True, timeout=8)
        loaded = result.returncode == 0
        details = result.stdout.strip() if loaded else (result.stderr.strip() or result.stdout.strip() or "Not loaded")
    except Exception as exc:
        details = str(exc)

    return (
        "⚙️ Service Status\n\n"
        f"Service: {SERVICE_LABEL}\n"
        f"Loaded/Running: {'Yes' if loaded else 'No'}\n"
        f"LaunchAgent file: {'Found' if LAUNCH_AGENT_PATH.exists() else 'Missing'}\n"
        f"Path: {LAUNCH_AGENT_PATH}\n\n"
        f"Details:\n{details[:1500]}"
    )


def get_bot_health_report() -> str:
    cgsession = "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession"
    checks = [
        ("BOT_TOKEN loaded", bool(BOT_TOKEN), "Configured" if BOT_TOKEN else "Missing"),
        ("Admin IDs configured", bool(ALLOWED_TELEGRAM_IDS), f"{len(ALLOWED_TELEGRAM_IDS)} admin(s)"),
        ("BOT_ENABLED", BOT_ENABLED, str(BOT_ENABLED)),
        ("Internet/Telegram reachable", internet_ok(), "api.telegram.org/google.com"),
        ("Base directory writable", os.access(BASE_DIR, os.W_OK), str(BASE_DIR)),
        ("screencapture available", command_exists("screencapture"), "Screenshot command"),
        ("osascript available", command_exists("osascript"), "AppleScript command"),
        ("diskutil available", command_exists("diskutil"), "Disk health command"),
        ("smartctl optional", command_exists("smartctl"), "Optional: brew install smartmontools"),
        ("pmset available", command_exists("pmset"), "Power command"),
        ("ioreg available", command_exists("ioreg"), "Lock detection command"),
        ("launchctl available", command_exists("launchctl"), "Service command"),
        ("LaunchAgent installed", LAUNCH_AGENT_PATH.exists(), str(LAUNCH_AGENT_PATH)),
        ("CGSession lock available", os.path.exists(cgsession), cgsession),
    ]

    lines = ["🩺 Bot Health", ""]
    required_ok = True
    for name, ok, detail in checks:
        if name != "smartctl optional":
            required_ok = required_ok and ok
        lines.append(f"{'✅' if ok else '❌'} {name}: {detail}")

    lines += ["", f"Overall: {'OK' if required_ok else 'Needs attention'}"]
    return "\n".join(lines)


def get_bot_config_report() -> str:
    return (
        "⚙️ Bot Config\n\n"
        "Token: configured but hidden\n"
        f"Allowed admins: {len(ALLOWED_TELEGRAM_IDS)}\n"
        f"Private chat only: true\n"
        f"Bot enabled: {BOT_ENABLED}\n"
        f"Status features enabled: {STATUS_FEATURES_ENABLED}\n"
        f"Control actions enabled: {CONTROL_ACTIONS_ENABLED}\n"
        f"Screenshot enabled: {SCREENSHOT_ENABLED}\n"
        f"Alerts enabled: {ALERTS_ENABLED}\n"
        f"Disk health enabled: {DISK_HEALTH_ENABLED}\n\n"
        f"Quiet hours enabled: {QUIET_HOURS_ENABLED}\n"
        f"Quiet hours: {QUIET_HOURS_START} - {QUIET_HOURS_END}\n"
        f"Currently quiet hours: {is_quiet_hours()}\n"
        f"Alert cooldown: {ALERT_COOLDOWN_MINUTES} minutes\n\n"
        f"Rate limit general: {RATE_LIMIT_GENERAL_PER_MINUTE}/minute\n"
        f"Rate limit controls: {RATE_LIMIT_CONTROL_PER_MINUTE}/minute\n"
        f"Rate limit screenshots: {RATE_LIMIT_SCREENSHOT_PER_MINUTE}/minute\n"
        f"Rate limit restart/shutdown: {RATE_LIMIT_RESTART_SHUTDOWN_PER_2MIN}/2 minutes\n\n"
        f"CPU alert: >= {HIGH_CPU_PERCENT}% for {HIGH_CPU_CONSECUTIVE_CHECKS} checks\n"
        f"RAM alert: >= {HIGH_RAM_PERCENT}%\n"
        f"Disk alert thresholds: {', '.join(str(x) + '%' for x in DISK_ALERT_PERCENTAGES)}\n"
        f"Daily report: {ENABLE_DAILY_REPORT} at {DAILY_REPORT_TIME}\n"
        f"Service label: {SERVICE_LABEL}\n"
        f"Version: {BOT_VERSION}"
    )


def get_version_report() -> str:
    return (
        "ℹ️ Bot Version\n\n"
        f"Name: {BOT_NAME}\n"
        f"Version: {BOT_VERSION}\n"
        f"Python: {platform.python_version()}\n"
        f"Base Dir: {BASE_DIR}\n"
        f"Service Label: {SERVICE_LABEL}"
    )


@dataclass
class CommandResult:
    success: bool
    method: str
    detail: str


def run_methods(methods: list[tuple[str, list[str]]]) -> CommandResult:
    last_error = ""
    for label, command in methods:
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            return CommandResult(True, label, "OK")
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Command failed using %s: %s", label, exc)
    return CommandResult(False, "none", last_error or "All methods failed")


def run_lock_command() -> CommandResult:
    cgsession = "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession"
    methods = []
    if os.path.exists(cgsession):
        methods.append(("CGSession lock", [cgsession, "-suspend"]))
    methods += [
        (
            "macOS Lock Screen shortcut",
            ["osascript", "-e", 'tell application "System Events" to key code 12 using {control down, command down}'],
        ),
        ("Display sleep fallback", ["pmset", "displaysleepnow"]),
    ]
    return run_methods(methods)


def run_sleep_command() -> CommandResult:
    return run_methods(
        [
            ("pmset sleepnow", ["pmset", "sleepnow"]),
            ("AppleScript sleep", ["osascript", "-e", 'tell application "System Events" to sleep']),
        ]
    )


def run_display_sleep_command() -> CommandResult:
    return run_methods([("pmset displaysleepnow", ["pmset", "displaysleepnow"])])


def run_restart_command() -> CommandResult:
    return run_methods([("AppleScript restart", ["osascript", "-e", 'tell application "System Events" to restart'])])


def run_shutdown_command() -> CommandResult:
    return run_methods([("AppleScript shutdown", ["osascript", "-e", 'tell application "System Events" to shut down'])])


def run_restart_bot_command() -> CommandResult:
    if not command_exists("launchctl"):
        return CommandResult(False, "launchctl", "launchctl is not available")

    try:
        subprocess.Popen(
            ["/bin/bash", "-lc", f"sleep 1; launchctl stop {SERVICE_LABEL}; sleep 1; launchctl start {SERVICE_LABEL}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return CommandResult(True, "launchctl stop/start", f"Restart requested for {SERVICE_LABEL}")
    except Exception as exc:
        return CommandResult(False, "launchctl stop/start", str(exc))


def execute_control_action(action_key: str) -> CommandResult:
    if action_key == "lock":
        return run_lock_command()
    if action_key == "sleep":
        return run_sleep_command()
    if action_key == "display_sleep":
        return run_display_sleep_command()
    if action_key == "restart":
        return run_restart_command()
    if action_key == "shutdown":
        return run_shutdown_command()
    if action_key == "restart_bot":
        return run_restart_bot_command()
    return CommandResult(False, "unknown", f"Unknown action: {action_key}")


def tail_lines(path: Path, limit: int = 50) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except Exception:
        return []


def get_last_logs_report() -> str:
    lines = tail_lines(LOG_PATH, 50)
    if not lines:
        return "📄 Last 50 Logs\n\nNo log lines found."

    text = "\n".join(lines)
    if len(text) > 3500:
        text = text[-3500:]
    return f"📄 Last 50 Logs\n\n{text}"


def tail_jsonl(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            records.append(json.loads(line))
        except Exception:
            pass
    return records


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)
    except Exception:
        return 0


def get_audit_summary() -> str:
    records = tail_jsonl(AUDIT_LOG_PATH, 10)
    if not records:
        return "🧾 Audit Summary\n\nNo admin actions logged yet."

    lines = ["🧾 Audit Summary", "", "Last 10 admin actions:", ""]
    for record in records:
        user = record.get("user", {})
        lines += [
            record.get("timestamp", "unknown_time"),
            f"Action: {record.get('action', 'unknown_action')}",
            f"Result: {record.get('result', 'unknown_result')}",
            f"User: {user.get('telegram_id', 'unknown_id')} @{user.get('username') or 'no_username'}",
            "",
        ]
    return "\n".join(lines).strip()


def get_unauthorized_summary() -> str:
    records = tail_jsonl(UNAUTHORIZED_LOG_PATH, 10)
    if not records:
        return "⛔ Unauthorized Summary\n\nNo unauthorized attempts logged yet."

    lines = ["⛔ Unauthorized Summary", "", "Last 10 rejected attempts:", ""]
    for record in records:
        user = record.get("user", {})
        lines += [
            record.get("timestamp", "unknown_time"),
            f"Reason: {record.get('reason', 'unknown')}",
            f"User: {user.get('telegram_id', 'unknown_id')} @{user.get('username') or 'no_username'}",
            f"Chat type: {record.get('chat_type')}",
            f"Message: {record.get('message_text') or '-'}",
            "",
        ]
    return "\n".join(lines).strip()


def create_logs_zip() -> Path:
    zip_path = BASE_DIR / f"macmini_bot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    files = [
        LOG_PATH,
        AUDIT_LOG_PATH,
        UNAUTHORIZED_LOG_PATH,
        PUBLIC_IP_STATE_PATH,
        INTERNET_STATE_PATH,
        VOLUME_STATE_PATH,
        LOCK_STATE_PATH,
        USER_STATE_PATH,
    ]

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.exists():
                archive.write(path, arcname=path.relative_to(BASE_DIR))
        for rotated in BASE_DIR.glob("macmini_bot.log.*"):
            archive.write(rotated, arcname=rotated.name)

    return zip_path


def get_daily_report() -> str:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    root = psutil.disk_usage("/")
    volume_lines = []

    for part in get_disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            volume_lines.append(
                f"{part.mountpoint}: {pct(usage.percent)} used, {human_bytes(usage.free)} free of {human_bytes(usage.total)}"
            )
        except Exception:
            pass

    return (
        "📅 Daily Status Report\n\n"
        f"Time: {now_text()}\n"
        f"Host: {socket.gethostname()}\n"
        f"User: {get_console_user()}\n"
        f"Login State: {'Logged in' if is_console_logged_in() else 'Logged out / loginwindow'}\n"
        f"Lock State: {get_screen_lock_state()}\n"
        f"Uptime: {get_uptime()}\n\n"
        f"CPU Now: {pct(cpu)}\n"
        f"RAM: {human_bytes(memory.used)} / {human_bytes(memory.total)} ({pct(memory.percent)})\n"
        f"Root Disk: {human_bytes(root.used)} / {human_bytes(root.total)} ({pct(root.percent)})\n\n"
        f"Local IP: {get_primary_lan_ip()}\n"
        f"Public IP: {get_public_ip()}\n"
        f"Internet: {'OK' if internet_ok() else 'Failed'}\n\n"
        f"Volumes:\n{chr(10).join(volume_lines) if volume_lines else 'No volume data'}\n\n"
        f"Audit Actions Logged: {count_jsonl(AUDIT_LOG_PATH)}\n"
        f"Rejected Attempts Logged: {count_jsonl(UNAUTHORIZED_LOG_PATH)}"
    )


async def send_to_admins(application: Application, text: str, alert_key: str | None = None, critical: bool = False) -> None:
    if not ALERTS_ENABLED and alert_key:
        return

    if alert_key:
        now = datetime.now()

        if is_quiet_hours() and not critical:
            logger.info("Alert suppressed by quiet hours: %s", alert_key)
            return

        last = ALERT_LAST_SENT.get(alert_key)
        if last and now - last < timedelta(minutes=ALERT_COOLDOWN_MINUTES):
            logger.info("Alert suppressed by cooldown: %s", alert_key)
            return

        ALERT_LAST_SENT[alert_key] = now

    for telegram_id in sorted(ALLOWED_TELEGRAM_IDS):
        try:
            await application.bot.send_message(chat_id=telegram_id, text=text, reply_markup=MAIN_KEYBOARD)
        except (TelegramError, Exception) as exc:
            logger.warning("Failed to send message to %s: %s", telegram_id, exc)


class AlertState:
    def __init__(self) -> None:
        self.cpu_high_count = 0
        self.cpu_alert_active = False
        self.ram_alert_active = False
        self.disk_alert_levels: dict[str, int] = {}
        self.public_ip = text_read(PUBLIC_IP_STATE_PATH)
        internet_state = json_read(INTERNET_STATE_PATH, {"is_up": True, "down_since": None})
        self.internet_was_up = bool(internet_state.get("is_up", True))
        self.internet_down_since = internet_state.get("down_since")
        self.volumes = json_read(VOLUME_STATE_PATH, volume_snapshot())
        lock_state = json_read(LOCK_STATE_PATH, {"state": get_screen_lock_state()})
        self.lock_state = lock_state.get("state", "unknown")
        user_state = json_read(USER_STATE_PATH, {"user": get_console_user(), "logged_in": is_console_logged_in()})
        self.console_user = user_state.get("user", get_console_user())
        self.console_logged_in = bool(user_state.get("logged_in", is_console_logged_in()))


ALERT_STATE = AlertState()


async def alert_monitor_loop(application: Application) -> None:
    if ENABLE_PUBLIC_IP and not ALERT_STATE.public_ip:
        current = get_public_ip()
        if current not in {"Unavailable", "Disabled", ""}:
            ALERT_STATE.public_ip = current
            text_write(PUBLIC_IP_STATE_PATH, current)

    if ENABLE_VOLUME_ALERTS and not ALERT_STATE.volumes:
        ALERT_STATE.volumes = volume_snapshot()
        json_write(VOLUME_STATE_PATH, ALERT_STATE.volumes)

    while True:
        try:
            await asyncio.sleep(ALERT_CHECK_INTERVAL_SECONDS)
            await check_alerts(application)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Alert monitor error: %s", exc)


async def daily_report_loop(application: Application) -> None:
    last_sent_date = ""
    while True:
        try:
            await asyncio.sleep(30)
            if not ENABLE_DAILY_REPORT or not ALERTS_ENABLED:
                continue

            hour, minute = parse_hhmm(DAILY_REPORT_TIME)
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")

            if now.hour == hour and now.minute == minute and last_sent_date != today:
                last_sent_date = today
                await send_to_admins(application, get_daily_report(), "daily_report", critical=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Daily report error: %s", exc)


async def check_alerts(application: Application) -> None:
    cpu = psutil.cpu_percent(interval=1)

    if cpu >= HIGH_CPU_PERCENT:
        ALERT_STATE.cpu_high_count += 1
    else:
        ALERT_STATE.cpu_high_count = 0
        if ALERT_STATE.cpu_alert_active and cpu <= max(0, HIGH_CPU_PERCENT - LOWER_RESET_MARGIN_PERCENT):
            ALERT_STATE.cpu_alert_active = False
            await send_to_admins(application, f"✅ CPU alert recovered.\n\nCurrent CPU: {pct(cpu)}", "cpu_recovered")

    if ALERT_STATE.cpu_high_count >= HIGH_CPU_CONSECUTIVE_CHECKS and not ALERT_STATE.cpu_alert_active:
        ALERT_STATE.cpu_alert_active = True
        await send_to_admins(application, f"🚨 High CPU Alert\n\nCurrent CPU: {pct(cpu)}", "high_cpu", critical=True)

    memory = psutil.virtual_memory()

    if memory.percent >= HIGH_RAM_PERCENT and not ALERT_STATE.ram_alert_active:
        ALERT_STATE.ram_alert_active = True
        await send_to_admins(
            application,
            f"🚨 High RAM Alert\n\nRAM: {pct(memory.percent)}\nUsed: {human_bytes(memory.used)} / {human_bytes(memory.total)}",
            "high_ram",
            critical=True,
        )

    if ALERT_STATE.ram_alert_active and memory.percent <= max(0, HIGH_RAM_PERCENT - LOWER_RESET_MARGIN_PERCENT):
        ALERT_STATE.ram_alert_active = False
        await send_to_admins(application, f"✅ RAM alert recovered.\n\nCurrent RAM: {pct(memory.percent)}", "ram_recovered")

    await check_disk_alerts(application)

    if ENABLE_PUBLIC_IP:
        await check_public_ip_alert(application)
    if ENABLE_INTERNET_ALERTS:
        await check_internet_alert(application)
    if ENABLE_VOLUME_ALERTS:
        await check_volume_alert(application)
    if ENABLE_LOCK_UNLOCK_ALERTS:
        await check_lock_unlock_alert(application)
    if ENABLE_LOGIN_LOGOUT_ALERTS:
        await check_login_logout_alert(application)


async def check_disk_alerts(application: Application) -> None:
    thresholds = sorted(DISK_ALERT_PERCENTAGES)

    for part in get_disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue

        crossed = [x for x in thresholds if usage.percent >= x]
        current_level = max(crossed) if crossed else 0
        previous_level = ALERT_STATE.disk_alert_levels.get(part.mountpoint, 0)

        if current_level > previous_level:
            ALERT_STATE.disk_alert_levels[part.mountpoint] = current_level
            await send_to_admins(
                application,
                f"🚨 Low Disk Space Alert\n\n"
                f"Mount: {part.mountpoint}\n"
                f"Device: {part.device}\n"
                f"Used: {pct(usage.percent)}\n"
                f"Threshold: {current_level}%\n"
                f"Free: {human_bytes(usage.free)}",
                f"disk_{part.mountpoint}_{current_level}",
                critical=True,
            )

        if current_level == 0 and previous_level > 0:
            ALERT_STATE.disk_alert_levels[part.mountpoint] = 0
            await send_to_admins(application, f"✅ Disk space recovered.\n\nMount: {part.mountpoint}\nUsed: {pct(usage.percent)}", f"disk_recovered_{part.mountpoint}")


async def check_public_ip_alert(application: Application) -> None:
    current = get_public_ip()
    if current in {"Unavailable", "Disabled", ""}:
        return

    if not ALERT_STATE.public_ip:
        ALERT_STATE.public_ip = current
        text_write(PUBLIC_IP_STATE_PATH, current)
        return

    if current != ALERT_STATE.public_ip:
        old = ALERT_STATE.public_ip
        ALERT_STATE.public_ip = current
        text_write(PUBLIC_IP_STATE_PATH, current)
        await send_to_admins(application, f"🌐 Public IP Changed\n\nOld IP: {old}\nNew IP: {current}", "public_ip_changed")


async def check_internet_alert(application: Application) -> None:
    is_up = internet_ok()

    if is_up and not ALERT_STATE.internet_was_up:
        downtime = "Unavailable"
        if ALERT_STATE.internet_down_since:
            try:
                delta = datetime.now() - datetime.fromisoformat(ALERT_STATE.internet_down_since)
                downtime = str(delta).split(".")[0]
            except Exception:
                pass

        ALERT_STATE.internet_was_up = True
        ALERT_STATE.internet_down_since = None
        json_write(INTERNET_STATE_PATH, {"is_up": True, "down_since": None})
        await send_to_admins(application, f"✅ Internet restored\n\nDowntime: {downtime}", "internet_restored", critical=True)

    elif not is_up and ALERT_STATE.internet_was_up:
        down_since = datetime.now().isoformat(timespec="seconds")
        ALERT_STATE.internet_was_up = False
        ALERT_STATE.internet_down_since = down_since
        json_write(INTERNET_STATE_PATH, {"is_up": False, "down_since": down_since})
        logger.warning("Internet appears down since %s", down_since)


async def check_volume_alert(application: Application) -> None:
    current = volume_snapshot()
    previous = ALERT_STATE.volumes or {}

    current_paths = set(current.keys())
    previous_paths = set(previous.keys())

    mounted = sorted(current_paths - previous_paths)
    unmounted = sorted(previous_paths - current_paths)

    for mountpoint in mounted:
        data = current[mountpoint]
        await send_to_admins(
            application,
            f"💾 Drive Mounted\n\n"
            f"Mount: {mountpoint}\n"
            f"Device: {data.get('device')}\n"
            f"Filesystem: {data.get('fstype')}\n"
            f"Total: {human_bytes(data['total'])}\n"
            f"Free: {human_bytes(data['free'])}\n"
            f"Used: {pct(data['percent'])}",
            f"drive_mounted_{mountpoint}",
        )

    for mountpoint in unmounted:
        old = previous.get(mountpoint, {})
        await send_to_admins(
            application,
            f"⚠️ Drive Unmounted\n\nMount: {mountpoint}\nDevice: {old.get('device', 'Unavailable')}",
            f"drive_unmounted_{mountpoint}",
            critical=True,
        )

    if mounted or unmounted:
        ALERT_STATE.volumes = current
        json_write(VOLUME_STATE_PATH, current)


async def check_lock_unlock_alert(application: Application) -> None:
    current = get_screen_lock_state()
    previous = ALERT_STATE.lock_state

    if current == "unknown":
        return

    if previous == "unknown":
        ALERT_STATE.lock_state = current
        json_write(LOCK_STATE_PATH, {"state": current, "updated": now_text()})
        return

    if current != previous:
        ALERT_STATE.lock_state = current
        json_write(LOCK_STATE_PATH, {"state": current, "updated": now_text()})
        emoji = "🔒" if current == "locked" else "🔓"
        await send_to_admins(application, f"{emoji} Mac {current}\n\nTime: {now_text()}", f"lock_state_{current}", critical=True)


async def check_login_logout_alert(application: Application) -> None:
    user = get_console_user()
    logged_in = is_console_logged_in()

    if user != ALERT_STATE.console_user or logged_in != ALERT_STATE.console_logged_in:
        old_user = ALERT_STATE.console_user
        old_logged_in = ALERT_STATE.console_logged_in

        ALERT_STATE.console_user = user
        ALERT_STATE.console_logged_in = logged_in
        json_write(USER_STATE_PATH, {"user": user, "logged_in": logged_in, "updated": now_text()})

        if logged_in and not old_logged_in:
            message = f"👤 User logged in\n\nUser: {user}\nTime: {now_text()}"
        elif not logged_in and old_logged_in:
            message = f"👤 User logged out\n\nPrevious user: {old_user}\nCurrent console user: {user}\nTime: {now_text()}"
        else:
            message = f"👤 Console user changed\n\nOld: {old_user}\nNew: {user}\nTime: {now_text()}"

        await send_to_admins(application, message, "console_user_changed", critical=True)


async def show_menu(update: Update) -> None:
    if update.message:
        await update.message.reply_text(f"✅ {BOT_NAME} ready.\n\nUse the keyboard buttons below.", reply_markup=MAIN_KEYBOARD)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await precheck(update, context):
        return
    audit(update, "start", "success")
    await show_menu(update)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await precheck(update, context):
        return
    audit(update, "menu", "success")
    await show_menu(update)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await precheck(update, context):
        return

    if not update.message:
        return

    text = (update.message.text or "").strip()

    if text == BTN_BACK:
        audit(update, "back", "success")
        await show_menu(update)
        return

    if text == BTN_CANCEL:
        context.user_data.pop("pending_action", None)
        audit(update, "cancel", "success")
        await update.message.reply_text("Cancelled.", reply_markup=MAIN_KEYBOARD)
        return

    if text == BTN_HELP:
        audit(update, "help", "success")
        await update.message.reply_text(
            "❓ Help\n\n"
            "Use keyboard buttons only.\n\n"
            "Security:\n"
            "- Private chat only\n"
            "- Admin Telegram ID only\n"
            "- Rate limited\n"
            "- Dangerous actions require confirmation\n"
            "- No custom shell commands\n\n"
            "Storage:\n"
            "🗂 All Mounted Disks shows device, filesystem, mount, total, used, free.\n"
            "🩻 Disk Health uses diskutil and optional smartctl.\n\n"
            "Logs:\n"
            "📄 Last 50 Logs shows recent bot logs.\n"
            "📦 Export Logs sends logs as ZIP.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text in {BTN_QUICK_STATUS, BTN_LOCAL_IP, BTN_STATUS, BTN_CPU, BTN_TOP_CPU, BTN_TOP_RAM, BTN_ACTIVE_APP, BTN_RUNNING_APPS,
                BTN_STORAGE_DETAILS, BTN_ALL_MOUNTED_DISKS, BTN_DISK_HEALTH, BTN_TRASH_SIZE, BTN_DISK_ALERT_STATUS, BTN_IP,
                BTN_NETWORK_INTERFACES, BTN_NETWORK_SPEED, BTN_INTERNET_TEST, BTN_BOT_HEALTH, BTN_SERVICE_STATUS, BTN_BOT_CONFIG,
                BTN_VERSION, BTN_DAILY_REPORT_NOW}:
        ok, message = require_status_enabled()
        if not ok:
            audit(update, "status_feature_disabled", "rejected", {"button": text})
            await update.message.reply_text(message, reply_markup=MAIN_KEYBOARD)
            return

    if text == BTN_QUICK_STATUS:
        audit(update, "quick_status", "success")
        await update.message.reply_text(get_quick_status_report(), reply_markup=MAIN_KEYBOARD)
        return

    if text == BTN_LOCAL_IP:
        audit(update, "local_ip", "success")
        await update.message.reply_text(get_local_ip_report(), reply_markup=MAIN_KEYBOARD)
        return

    if text == BTN_SYSTEM_MENU:
        audit(update, "open_system_menu", "success")
        await update.message.reply_text("🖥 System Menu", reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_STORAGE_MENU:
        audit(update, "open_storage_menu", "success")
        await update.message.reply_text("💾 Storage Menu", reply_markup=STORAGE_KEYBOARD)
        return

    if text == BTN_NETWORK_MENU:
        audit(update, "open_network_menu", "success")
        await update.message.reply_text("🌐 Network Menu", reply_markup=NETWORK_KEYBOARD)
        return

    if text == BTN_CONTROLS_MENU:
        audit(update, "open_controls_menu", "success")
        await update.message.reply_text("🛠 Controls Menu", reply_markup=CONTROLS_KEYBOARD)
        return

    if text == BTN_LOGS_MENU:
        audit(update, "open_logs_menu", "success")
        await update.message.reply_text("📜 Logs Menu", reply_markup=LOGS_KEYBOARD)
        return

    if text == BTN_STATUS:
        audit(update, "status", "success")
        await update.message.reply_text(get_status_report(), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_CPU:
        audit(update, "cpu_usage", "success")
        await update.message.reply_text(get_cpu_report(), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_TOP_CPU:
        audit(update, "top_cpu", "success")
        await update.message.reply_text(await asyncio.to_thread(list_top_processes, "cpu", 5), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_TOP_RAM:
        audit(update, "top_ram", "success")
        await update.message.reply_text(await asyncio.to_thread(list_top_processes, "ram", 5), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_ACTIVE_APP:
        audit(update, "active_app", "success")
        await update.message.reply_text(await asyncio.to_thread(get_active_app_report), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_RUNNING_APPS:
        audit(update, "running_apps", "success")
        await update.message.reply_text(await asyncio.to_thread(get_running_apps_report), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_SCREENSHOT:
        ok, message = require_screenshot_enabled()
        if not ok:
            audit(update, "screenshot_disabled", "rejected")
            await update.message.reply_text(message, reply_markup=SYSTEM_KEYBOARD)
            return

        ok, retry_after = check_rate_limit(update, "screenshot", RATE_LIMIT_SCREENSHOT_PER_MINUTE, 60)
        if not ok:
            audit(update, "rate_limit_screenshot", "rejected", {"retry_after": retry_after})
            await update.message.reply_text(f"⏳ Screenshot rate limit reached. Try again in {retry_after}s.", reply_markup=SYSTEM_KEYBOARD)
            return

        await update.message.reply_text("📸 Capturing screenshot...", reply_markup=SYSTEM_KEYBOARD)
        success, path, detail = await asyncio.to_thread(capture_screenshot)

        if success and path:
            audit(update, "screenshot", "success", {"file": str(path)})
            with path.open("rb") as handle:
                await update.message.reply_document(document=handle, filename=path.name, caption="📸 Mac Mini screenshot", reply_markup=SYSTEM_KEYBOARD)
        else:
            audit(update, "screenshot", "failed", {"error": detail})
            await update.message.reply_text(
                "❌ Screenshot failed.\n\n"
                "Allow Terminal/Python in:\n"
                "System Settings > Privacy & Security > Screen Recording\n\n"
                f"Error: {detail}",
                reply_markup=SYSTEM_KEYBOARD,
            )
        return

    if text == BTN_BOT_HEALTH:
        audit(update, "bot_health", "success")
        await update.message.reply_text(await asyncio.to_thread(get_bot_health_report), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_SERVICE_STATUS:
        audit(update, "service_status", "success")
        await update.message.reply_text(await asyncio.to_thread(get_service_status_report), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_BOT_CONFIG:
        audit(update, "bot_config", "success")
        await update.message.reply_text(get_bot_config_report(), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_VERSION:
        audit(update, "version", "success")
        await update.message.reply_text(get_version_report(), reply_markup=SYSTEM_KEYBOARD)
        return

    if text == BTN_STORAGE_DETAILS:
        audit(update, "storage", "success")
        await update.message.reply_text(get_storage_report(), reply_markup=STORAGE_KEYBOARD)
        return

    if text == BTN_ALL_MOUNTED_DISKS:
        audit(update, "all_mounted_disks", "success")
        await update.message.reply_text(await asyncio.to_thread(get_all_mounted_disks_report), reply_markup=STORAGE_KEYBOARD)
        return

    if text == BTN_DISK_HEALTH:
        audit(update, "disk_health", "success")
        await update.message.reply_text(await asyncio.to_thread(get_disk_health_report), reply_markup=STORAGE_KEYBOARD)
        return

    if text == BTN_TRASH_SIZE:
        audit(update, "trash_size", "success")
        await update.message.reply_text(await asyncio.to_thread(get_trash_size_report), reply_markup=STORAGE_KEYBOARD)
        return

    if text == BTN_DISK_ALERT_STATUS:
        audit(update, "disk_alert_status", "success")
        await update.message.reply_text(get_disk_alert_status_report(), reply_markup=STORAGE_KEYBOARD)
        return

    if text == BTN_IP:
        audit(update, "ip_details", "success")
        await update.message.reply_text(get_ip_report(), reply_markup=NETWORK_KEYBOARD)
        return

    if text == BTN_NETWORK_INTERFACES:
        audit(update, "network_interfaces", "success")
        await update.message.reply_text(await asyncio.to_thread(get_network_interface_report), reply_markup=NETWORK_KEYBOARD)
        return

    if text == BTN_NETWORK_SPEED:
        audit(update, "network_speed", "success")
        await update.message.reply_text("📡 Measuring network speed...", reply_markup=NETWORK_KEYBOARD)
        await update.message.reply_text(await get_network_speed_report(), reply_markup=NETWORK_KEYBOARD)
        return

    if text == BTN_INTERNET_TEST:
        audit(update, "internet_test", "success")
        await update.message.reply_text(await asyncio.to_thread(internet_test), reply_markup=NETWORK_KEYBOARD)
        return

    if text in DANGEROUS_ACTIONS:
        ok, message = require_controls_enabled()
        if not ok:
            audit(update, "control_disabled", "rejected", {"button": text})
            await update.message.reply_text(message, reply_markup=CONTROLS_KEYBOARD)
            return

        ok, retry_after = check_rate_limit(update, "control", RATE_LIMIT_CONTROL_PER_MINUTE, 60)
        if not ok:
            audit(update, "rate_limit_control", "rejected", {"retry_after": retry_after})
            await update.message.reply_text(f"⏳ Control action rate limit reached. Try again in {retry_after}s.", reply_markup=CONTROLS_KEYBOARD)
            return

        action_key, confirm_button, confirm_text = DANGEROUS_ACTIONS[text]

        if action_key in {"restart", "shutdown", "restart_bot"}:
            ok, retry_after = check_rate_limit(update, "restart_shutdown", RATE_LIMIT_RESTART_SHUTDOWN_PER_2MIN, 120)
            if not ok:
                audit(update, "rate_limit_restart_shutdown", "rejected", {"retry_after": retry_after})
                await update.message.reply_text(f"⏳ Restart/shutdown rate limit reached. Try again in {retry_after}s.", reply_markup=CONTROLS_KEYBOARD)
                return

        context.user_data["pending_action"] = action_key
        audit(update, f"request_{action_key}", "pending_confirmation")
        await update.message.reply_text(confirm_text, reply_markup=confirmation_keyboard(confirm_button))
        return

    if text in CONFIRM_BUTTON_TO_ACTION:
        requested = CONFIRM_BUTTON_TO_ACTION[text]
        pending = context.user_data.get("pending_action")

        if requested != pending:
            audit(update, f"confirm_{requested}", "failed_no_matching_pending_action", {"pending": pending})
            await update.message.reply_text("No matching pending action. Please select the action again.", reply_markup=CONTROLS_KEYBOARD)
            return

        context.user_data.pop("pending_action", None)
        await update.message.reply_text(f"Executing: {requested}", reply_markup=MAIN_KEYBOARD)
        result = await asyncio.to_thread(execute_control_action, requested)
        audit(update, f"execute_{requested}", "success" if result.success else "failed", {"method": result.method, "detail": result.detail})

        if result.success:
            await update.message.reply_text(f"✅ Command sent.\nAction: {requested}\nMethod: {result.method}", reply_markup=MAIN_KEYBOARD)
        else:
            await update.message.reply_text(f"❌ Command failed.\nAction: {requested}\nError: {result.detail}", reply_markup=CONTROLS_KEYBOARD)
        return

    if text == BTN_LAST_LOGS:
        audit(update, "last_50_logs", "success")
        await update.message.reply_text(get_last_logs_report(), reply_markup=LOGS_KEYBOARD)
        return

    if text == BTN_EXPORT_LOGS:
        try:
            zip_path = create_logs_zip()
            audit(update, "export_logs", "success", {"zip_file": str(zip_path)})
            with zip_path.open("rb") as handle:
                await update.message.reply_document(document=handle, filename=zip_path.name, caption="📦 Mac Mini bot logs export", reply_markup=LOGS_KEYBOARD)
            zip_path.unlink(missing_ok=True)
        except Exception as exc:
            audit(update, "export_logs", "failed", {"error": str(exc)})
            await update.message.reply_text(f"❌ Failed to export logs.\n\nError: {exc}", reply_markup=LOGS_KEYBOARD)
        return

    if text == BTN_AUDIT_SUMMARY:
        audit(update, "audit_summary", "success")
        await update.message.reply_text(get_audit_summary(), reply_markup=LOGS_KEYBOARD)
        return

    if text == BTN_UNAUTHORIZED_SUMMARY:
        audit(update, "unauthorized_summary", "success")
        await update.message.reply_text(get_unauthorized_summary(), reply_markup=LOGS_KEYBOARD)
        return

    if text == BTN_DAILY_REPORT_NOW:
        audit(update, "daily_report_now", "success")
        await update.message.reply_text(get_daily_report(), reply_markup=LOGS_KEYBOARD)
        return

    audit(update, "unknown_text", "rejected", {"text": text})
    await update.message.reply_text("Please use the keyboard buttons only.", reply_markup=MAIN_KEYBOARD)


async def post_init(application: Application) -> None:
    await send_to_admins(
        application,
        "✅ Mac Mini Telegram Bot started\n\n"
        f"Bot: {BOT_NAME}\n"
        f"Version: {BOT_VERSION}\n"
        f"Host: {socket.gethostname()}\n"
        f"Uptime: {get_uptime()}\n"
        f"Local IP: {get_primary_lan_ip()}\n"
        f"Public IP: {get_public_ip()}",
        alert_key=None,
    )
    asyncio.create_task(alert_monitor_loop(application))
    asyncio.create_task(daily_report_loop(application))


def main() -> None:
    validate_config()

    logger.info("Starting %s v%s", BOT_NAME, BOT_VERSION)
    logger.info("Allowed Telegram IDs: %s", sorted(ALLOWED_TELEGRAM_IDS))

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
