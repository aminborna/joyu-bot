import os
import json
import socket
import ssl
import http.client
import time
import logging
import threading
from datetime import datetime
from collections import deque
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

TOKEN = "8315460370:AAG-KuAgvByAuQ0tOblr2Z5GNpc-908NqDw"
SUDO_ADMINS = {7661598575}
NORMAL_ADMINS = {5859213071} 
DOMAINS = []
CHAT_ID = None

LOG_FILE = "/root/joyu_bot/joyu.log"
STATE_FILE = "/root/joyu_bot/state.json"

terminal_tick_seconds = 5
telegram_push_interval_secs = 4 * 60 * 60
monitor_interval_secs = 60
telegram_logging_enabled = True
monitoring_enabled = True

last_results = deque(maxlen=200)
PENDING_ACTION = {}

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")]
)
logger = logging.getLogger("joyu")

def is_sudo(uid): return uid in SUDO_ADMINS
def is_admin(uid): return uid in SUDO_ADMINS or uid in NORMAL_ADMINS

def save_state():
    try:
        state = {
            "SUDO_ADMINS": list(SUDO_ADMINS),
            "NORMAL_ADMINS": list(NORMAL_ADMINS),
            "DOMAINS": DOMAINS,
            "terminal_tick_seconds": terminal_tick_seconds,
            "telegram_push_interval_secs": telegram_push_interval_secs,
            "monitor_interval_secs": monitor_interval_secs,
            "telegram_logging_enabled": telegram_logging_enabled,
            "monitoring_enabled": monitoring_enabled,
            "CHAT_ID": CHAT_ID,
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save_state error: {e}")

def load_state():
    global SUDO_ADMINS, NORMAL_ADMINS, DOMAINS
    global terminal_tick_seconds, telegram_push_interval_secs
    global monitor_interval_secs, telegram_logging_enabled, monitoring_enabled, CHAT_ID
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            SUDO_ADMINS = set(data.get("SUDO_ADMINS", []))
            NORMAL_ADMINS = set(data.get("NORMAL_ADMINS", []))
            DOMAINS = list(data.get("DOMAINS", []))
            terminal_tick_seconds = int(data.get("terminal_tick_seconds", terminal_tick_seconds))
            telegram_push_interval_secs = int(data.get("telegram_push_interval_secs", telegram_push_interval_secs))
            monitor_interval_secs = int(data.get("monitor_interval_secs", monitor_interval_secs))
            telegram_logging_enabled = bool(data.get("telegram_logging_enabled", telegram_logging_enabled))
            monitoring_enabled = bool(data.get("monitoring_enabled", monitoring_enabled))
            CHAT_ID = data.get("CHAT_ID", CHAT_ID)
    except Exception as e:
        logger.error(f"load_state error: {e}")

def build_keyboard(uid):
    base_rows = [
        ["افزودن دامنه", "لیست دامنه‌ها"],
        ["حذف دامنه", "بررسی الان"],
        ["📜 دیدن لاگ‌ها"],
        ["▶️ شروع", "⏹ توقف"],
    ]
    if is_sudo(uid):
        admin_rows = [
            ["➕ اضافه کردن ادمین معمولی", "➖ حذف ادمین معمولی"],
            ["➕ اضافه کردن سودو", "➖ حذف سودو"],
            ["👥 دیدن لیست همهٔ ادمین‌ها"],
            ["⏱ تنظیم زمان ارسال تلگرام", "⏱ تنظیم زمان لاگ ترمینال"],
        ]
        kb = base_rows + admin_rows
    elif is_admin(uid):
        kb = base_rows
    else:
        kb = [["/start"]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def push_result_for_telegram_batch(text: str):
    try:
        last_results.append(text)
    except Exception:
        pass

def status_summary():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"⏱ {now} | terminal_tick={terminal_tick_seconds}s | telegram_interval={telegram_push_interval_secs}s | monitor_interval={monitor_interval_secs}s | monitoring={'on' if monitoring_enabled else 'off'}"

def terminal_ticker():
    while True:
        try:
            logger.info(status_summary())
        except Exception as e:
            logger.error(f"terminal_ticker error: {e}")
        time.sleep(max(1, terminal_tick_seconds))

def telegram_scheduler(bot):
    while True:
        try:
            if CHAT_ID and telegram_logging_enabled and len(last_results):
                batch = []
                for _ in range(min(4, len(last_results))):
                    batch.append(last_results.popleft())
                body = "📡 گزارش دوره‌ای:\n\n" + ("\n\n".join(batch))
                bot.send_message(chat_id=CHAT_ID, text=body)
        except Exception as e:
            logger.error(f"telegram_scheduler error: {e}")
        time.sleep(max(60, telegram_push_interval_secs))

def check_domain(domain: str) -> str:
    lines = []
    lines.append(f"✅ 🌐 دامنه: {domain}")
    try:
        infos = socket.getaddrinfo(domain, None)
        ip_list = list(dict.fromkeys([x[4][0] for x in infos]))
        lines.append(f"📍 Host/IP: {domain} / {', '.join(ip_list)}")
        lines.append("✅ DNS [0ms]")
    except Exception:
        lines.append(f"📍 Host/IP: {domain} / -")
        lines.append("❌ DNS Resolve Failed")
        lines.append("\n👤 توسعه‌دهنده: امین (@Bornaa99)")
        return "\n".join(lines)

    try:
        t0 = time.time()
        s = socket.create_connection((domain, 80), 5)
        ms = int((time.time() - t0) * 1000)
        lines.append(f"✅ TCP:80 [{ms}ms]")
        s.close()
    except Exception:
        lines.append("❌ TCP:80 [0ms]")

    try:
        t0 = time.time()
        s = socket.create_connection((domain, 443), 5)
        ms = int((time.time() - t0) * 1000)
        lines.append(f"✅ TCP:443 [{ms}ms]")
        s.close()
    except Exception:
        lines.append("❌ TCP:443 [0ms]")

    try:
        t0 = time.time()
        ctx = ssl.create_default_context()
        ss = ctx.wrap_socket(socket.socket(), server_hostname=domain)
        ss.settimeout(6)
        ss.connect((domain, 443))
        ms = int((time.time() - t0) * 1000)
        lines.append(f"✅ TLS [{ms}ms]")
        ss.close()
    except Exception:
        lines.append("❌ TLS [0ms]")

    try:
        t0 = time.time()
        conn = http.client.HTTPConnection(domain, 80, timeout=6)
        conn.request("GET", "/")
        resp = conn.getresponse()
        ms = int((time.time() - t0) * 1000)
        lines.append(f"✅ HTTP http://{domain} [{ms}ms] → {resp.status}")
        lines.append(f"↪ http://{domain}/")
        conn.close()
    except Exception:
        lines.append(f"❌ HTTP http://{domain} → HTTP_CONN_ERR")

    lines.append("\n👤 توسعه‌دهنده: امین (@Bornaa99)")
    return "\n".join(lines)

def domain_checker():
    while True:
        try:
            if monitoring_enabled and DOMAINS:
                for d in list(DOMAINS):
                    report = "📡 نتیجه بررسی:\n\n" + check_domain(d)
                    logger.info(report.replace("\n", " "))
                    push_result_for_telegram_batch(report)
        except Exception as e:
            logger.error(f"domain_checker error: {e}")
        time.sleep(max(10, monitor_interval_secs))

def send_recent_logs(bot, chat_id, lines_cnt: int = 40):
    try:
        if not os.path.exists(LOG_FILE):
            bot.send_message(chat_id, "لاگی هنوز ایجاد نشده.")
            return
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            tail = f.readlines()[-lines_cnt:]
        text = "📜 آخرین لاگ‌ها:\n" + "".join(tail[-lines_cnt:])
        bot.send_message(chat_id, text[-4000:])
    except Exception as e:
        bot.send_message(chat_id, f"خطا در خواندن لاگ: {e}")

def cmd_start(update: Update, context: CallbackContext):
    global CHAT_ID
    uid = update.effective_user.id
    CHAT_ID = update.effective_chat.id
    update.message.reply_text("سلام! منوی مدیریت آماده‌ست.", reply_markup=build_keyboard(uid))

def handle_message(update: Update, context: CallbackContext):
    global PENDING_ACTION, terminal_tick_seconds, telegram_push_interval_secs, monitor_interval_secs, monitoring_enabled
    uid = update.effective_user.id
    text = (update.message.text or "").strip()

    if PENDING_ACTION.get(uid) == "ADD_DOMAIN":
        d = text.strip().lower()
        if d and d not in DOMAINS:
            DOMAINS.append(d)
            save_state()
            update.message.reply_text(f"✅ دامنه اضافه شد: {d}")
            logger.info(f"domain added: {d}")
        else:
            update.message.reply_text("❌ دامنه تکراری/نامعتبر.")
        PENDING_ACTION[uid] = None
        return

    if PENDING_ACTION.get(uid) == "REMOVE_DOMAIN":
        d = text.strip().lower()
        if d in DOMAINS:
            DOMAINS.remove(d)
            save_state()
            update.message.reply_text(f"🗑 حذف شد: {d}")
            logger.info(f"domain removed: {d}")
        else:
            update.message.reply_text("❌ دامنه پیدا نشد.")
        PENDING_ACTION[uid] = None
        return

    if PENDING_ACTION.get(uid) == "ADD_ADMIN" and is_sudo(uid):
        try:
            new_id = int(text.replace("@", "").strip())
            NORMAL_ADMINS.add(new_id)
            save_state()
            update.message.reply_text(f"✅ ادمین معمولی اضافه شد: {new_id}")
        except:
            update.message.reply_text("❌ آیدی معتبر نیست.")
        PENDING_ACTION[uid] = None
        return

    if PENDING_ACTION.get(uid) == "REMOVE_ADMIN" and is_sudo(uid):
        try:
            rem_id = int(text.replace("@", "").strip())
            if rem_id in NORMAL_ADMINS:
                NORMAL_ADMINS.remove(rem_id)
                save_state()
                update.message.reply_text(f"✅ ادمین معمولی حذف شد: {rem_id}")
            else:
                update.message.reply_text("❌ در لیست نبود.")
        except:
            update.message.reply_text("❌ آیدی معتبر نیست.")
        PENDING_ACTION[uid] = None
        return

    if PENDING_ACTION.get(uid) == "ADD_SUDO" and is_sudo(uid):
        try:
            new_id = int(text.replace("@", "").strip())
            SUDO_ADMINS.add(new_id)
            save_state()
            update.message.reply_text(f"✅ سودو اضافه شد: {new_id}")
        except:
            update.message.reply_text("❌ آیدی معتبر نیست.")
        PENDING_ACTION[uid] = None
        return

    if PENDING_ACTION.get(uid) == "REMOVE_SUDO" and is_sudo(uid):
        try:
            rem_id = int(text.replace("@", "").strip())
            if rem_id in SUDO_ADMINS:
                SUDO_ADMINS.remove(rem_id)
                save_state()
                update.message.reply_text(f"✅ سودو حذف شد: {rem_id}")
            else:
                update.message.reply_text("❌ در لیست سودو نبود.")
        except:
            update.message.reply_text("❌ آیدی معتبر نیست.")
        PENDING_ACTION[uid] = None
        return

    if PENDING_ACTION.get(uid) == "SET_TG_INTERVAL" and is_sudo(uid):
        try:
            mins = int(text)
            telegram_push_interval_secs = max(60, mins * 60)
            save_state()
            update.message.reply_text(f"✅ فاصلهٔ ارسال تلگرام: {mins} دقیقه")
        except:
            update.message.reply_text("❌ یک عدد دقیقه بفرست.")
        PENDING_ACTION[uid] = None
        return

    if PENDING_ACTION.get(uid) == "SET_TERM_INTERVAL" and is_sudo(uid):
        try:
            secs = int(text)
            terminal_tick_seconds = max(1, secs)
            save_state()
            update.message.reply_text(f"✅ فاصلهٔ لاگ ترمینال: {secs} ثانیه")
        except:
            update.message.reply_text("❌ یک عدد ثانیه بفرست.")
        PENDING_ACTION[uid] = None
        return

    if text == "افزودن دامنه" and is_admin(uid):
        update.message.reply_text("📥 دامنه را ارسال کنید:")
        PENDING_ACTION[uid] = "ADD_DOMAIN"
        return

    if text == "حذف دامنه" and is_admin(uid):
        if DOMAINS:
            update.message.reply_text("📥 دامنه‌ای که حذف شود را بفرست:")
            PENDING_ACTION[uid] = "REMOVE_DOMAIN"
        else:
            update.message.reply_text("❌ لیست دامنه‌ها خالی است.")
        return

    if text == "لیست دامنه‌ها" and is_admin(uid):
        if DOMAINS:
            update.message.reply_text("📜 دامنه‌ها:\n" + "\n".join(DOMAINS))
        else:
            update.message.reply_text("❌ هیچ دامنه‌ای ثبت نشده است.")
        return

    if text == "بررسی الان" and is_admin(uid):
        if not DOMAINS:
            update.message.reply_text("❌ هیچ دامنه‌ای برای بررسی وجود ندارد.")
            return
        for d in DOMAINS:
            report = "📡 نتیجه بررسی:\n\n" + check_domain(d)
            logger.info(report.replace("\n", " "))
            push_result_for_telegram_batch(report)
            update.message.reply_text(report)
        return

    if text == "📜 دیدن لاگ‌ها" and is_admin(uid):
        send_recent_logs(context.bot, update.effective_chat.id)
        return

    if text == "➕ اضافه کردن ادمین معمولی" and is_sudo(uid):
        update.message.reply_text("آیدی عددی ادمین معمولی را بفرست:")
        PENDING_ACTION[uid] = "ADD_ADMIN"
        return

    if text == "➖ حذف ادمین معمولی" and is_sudo(uid):
        update.message.reply_text("آیدی ادمین معمولی که حذف شود را بفرست:")
        PENDING_ACTION[uid] = "REMOVE_ADMIN"
        return

    if text == "➕ اضافه کردن سودو" and is_sudo(uid):
        update.message.reply_text("آیدی عددی سودو جدید را بفرست:")
        PENDING_ACTION[uid] = "ADD_SUDO"
        return

    if text == "➖ حذف سودو" and is_sudo(uid):
        update.message.reply_text("آیدی سودویی که حذف شود را بفرست:")
        PENDING_ACTION[uid] = "REMOVE_SUDO"
        return

    if text == "👥 دیدن لیست همهٔ ادمین‌ها" and is_sudo(uid):
        s = f"SUDO: {sorted(list(SUDO_ADMINS))}\nADMINS: {sorted(list(NORMAL_ADMINS))}"
        update.message.reply_text(s)
        return

    if text == "⏱ تنظیم زمان ارسال تلگرام" and is_sudo(uid):
        update.message.reply_text("دقیقه را بفرست:")
        PENDING_ACTION[uid] = "SET_TG_INTERVAL"
        return

    if text == "⏱ تنظیم زمان لاگ ترمینال" and is_sudo(uid):
        update.message.reply_text("ثانیه را بفرست:")
        PENDING_ACTION[uid] = "SET_TERM_INTERVAL"
        return

    if text == "▶️ شروع" and is_admin(uid):
        monitoring_enabled = True
        save_state()
        update.message.reply_text("✅ مانیتورینگ شروع شد.")
        return

    if text == "⏹ توقف" and is_admin(uid):
        monitoring_enabled = False
        save_state()
        update.message.reply_text("⏹ مانیتورینگ متوقف شد.")
        return

def main():
    load_state()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    bot = updater.bot
    threading.Thread(target=terminal_ticker, daemon=True).start()
    threading.Thread(target=telegram_scheduler, args=(bot,), daemon=True).start()
    threading.Thread(target=domain_checker, daemon=True).start()
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()