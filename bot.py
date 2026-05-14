"""
🎂 Events Bot — дни рождения, годовщины, корпоративные события
pip install python-telegram-bot apscheduler
"""

import os
import json
import logging
from datetime import datetime, date
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── Настройки ───────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8885591506:AAHpnJCbrn_QzY_xtr9YFo_JZUE67et2E0A")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "569847079"))
DATA_FILE = Path("events.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Состояния диалога ────────────────────────────────────────────────────────
ASK_CATEGORY, ASK_NAME, ASK_DATE, ASK_REPEAT, ASK_REMIND_DAYS = range(5)

CATEGORY_EMOJI = {
    "🎂 День рождения": "🎂",
    "💍 Годовщина": "💍",
    "🏢 Корпоративное": "🏢",
}

# ─── Хранилище ────────────────────────────────────────────────────────────────
def load_events() -> list:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_events(data: list):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def days_until(date_str: str, yearly: bool) -> int:
    today = date.today()
    d = datetime.strptime(date_str, "%d.%m.%Y").date()
    if yearly:
        next_d = d.replace(year=today.year)
        if next_d < today:
            next_d = next_d.replace(year=today.year + 1)
    else:
        next_d = d
    return (next_d - today).days

def format_event(e: dict) -> str:
    days = days_until(e["date"], e["repeat"])
    emoji = CATEGORY_EMOJI.get(e["category"], "📅")
    repeat_label = "ежегодно" if e["repeat"] else "однократно"
    if days == 0:
        when = "СЕГОДНЯ 🎉"
    elif days == 1:
        when = "ЗАВТРА 🔥"
    elif days < 0:
        when = "прошло"
    else:
        when = f"через {days} дн."
    return (
        f"{emoji} *{e['name']}*\n"
        f"   📅 {e['date']} · {when} · напомнить за {e['remind_days']} дн. · {repeat_label}"
    )

# ─── /start ───────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Events Bot* — твой личный органайзер событий!\n\n"
        "Категории:\n"
        "🎂 Дни рождения\n"
        "💍 Годовщины\n"
        "🏢 Корпоративные события\n\n"
        "Команды:\n"
        "➕ /add — добавить событие\n"
        "📋 /list — все события\n"
        "📅 /upcoming — ближайшие 90 дней\n"
        "🗑 /delete — удалить\n"
        "ℹ️ /help — помощь"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, ctx)

# ─── Добавить событие ─────────────────────────────────────────────────────────
async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🎂 День рождения", "💍 Годовщина"], ["🏢 Корпоративное"]]
    await update.message.reply_text(
        "Выбери категорию:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_CATEGORY

async def got_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text not in CATEGORY_EMOJI:
        await update.message.reply_text("Пожалуйста, выбери из кнопок.")
        return ASK_CATEGORY
    ctx.user_data["category"] = text
    await update.message.reply_text(
        "Как называется событие?\nНапример: *День рождения мамы* или *Годовщина компании*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_NAME

async def got_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Введи дату в формате *ДД.ММ.ГГГГ*\nНапример: 15.03.1990",
        parse_mode="Markdown"
    )
    return ASK_DATE

async def got_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        datetime.strptime(raw, "%d.%m.%Y")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введи как ДД.ММ.ГГГГ, например 15.03.1990")
        return ASK_DATE
    ctx.user_data["date"] = raw
    keyboard = [["🔁 Ежегодно", "1️⃣ Один раз"]]
    await update.message.reply_text(
        "Это событие повторяется каждый год?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_REPEAT

async def got_repeat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["repeat"] = "Ежегодно" in update.message.text
    await update.message.reply_text(
        "⏰ За сколько дней напомнить?\n\n"
        "Введи любое число, например:\n"
        "• 7 — за неделю\n"
        "• 30 — за месяц\n"
        "• 180 — за 6 месяцев",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_REMIND_DAYS

async def got_remind_days(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        if days < 1 or days > 730:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введи число от 1 до 730.")
        return ASK_REMIND_DAYS

    data = load_events()
    entry = {
        "name": ctx.user_data["name"],
        "category": ctx.user_data["category"],
        "date": ctx.user_data["date"],
        "repeat": ctx.user_data["repeat"],
        "remind_days": days,
    }
    data.append(entry)
    save_events(data)

    repeat_label = "ежегодно" if entry["repeat"] else "один раз"
    await update.message.reply_text(
        f"✅ Сохранено!\n\n{format_event(entry)}\n\nНапоминание за *{days} дн.* ({repeat_label})",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ─── /list ────────────────────────────────────────────────────────────────────
async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_events()
    if not data:
        await update.message.reply_text("Список пуст. Добавь первое событие /add 🎉")
        return
    groups = {}
    for e in data:
        groups.setdefault(e["category"], []).append(e)

    lines = ["📋 *Все события:*"]
    for cat, events in groups.items():
        lines.append(f"\n{cat}")
        for e in sorted(events, key=lambda x: days_until(x["date"], x["repeat"])):
            lines.append(format_event(e))
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /upcoming ────────────────────────────────────────────────────────────────
async def cmd_upcoming(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_events()
    upcoming = [e for e in data if 0 <= days_until(e["date"], e["repeat"]) <= 90]
    upcoming.sort(key=lambda x: days_until(x["date"], x["repeat"]))
    if not upcoming:
        await update.message.reply_text("В ближайшие 90 дней событий нет 🕊")
        return
    lines = ["📅 *Ближайшие события (90 дней):*\n"]
    for e in upcoming:
        lines.append(format_event(e))
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /delete ─────────────────────────────────────────────────────────────────
async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_events()
    if not data:
        await update.message.reply_text("Список пуст.")
        return
    lines = ["Введи номер для удаления:\n"]
    for i, e in enumerate(data, 1):
        emoji = CATEGORY_EMOJI.get(e["category"], "📅")
        lines.append(f"{i}. {emoji} {e['name']} ({e['date']})")
    ctx.user_data["delete_list"] = data
    await update.message.reply_text("\n".join(lines))

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "delete_list" not in ctx.user_data:
        return
    try:
        idx = int(update.message.text.strip()) - 1
        data = ctx.user_data["delete_list"]
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            save_events(data)
            del ctx.user_data["delete_list"]
            await update.message.reply_text(f"🗑 *{removed['name']}* удалено.", parse_mode="Markdown")
        else:
            await update.message.reply_text("Неверный номер.")
    except ValueError:
        pass

# ─── Ежедневные напоминания ───────────────────────────────────────────────────
async def daily_check(app: Application):
    data = load_events()
    for e in data:
        days_left = days_until(e["date"], e["repeat"])
        emoji = CATEGORY_EMOJI.get(e["category"], "📅")
        if days_left == 0:
            msg = f"{emoji} Сегодня: *{e['name']}*! 🎉"
        elif days_left == e["remind_days"]:
            msg = f"⏰ Напоминание: *{e['name']}* через *{days_left} дн.*\n📅 {e['date']}"
        else:
            continue
        try:
            await app.bot.send_message(OWNER_CHAT_ID, msg, parse_mode="Markdown")
        except Exception as ex:
            log.error(f"Ошибка: {ex}")

# ─── Запуск ───────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", cmd_add)],
        states={
            ASK_CATEGORY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_category)],
            ASK_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            ASK_DATE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
            ASK_REPEAT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, got_repeat)],
            ASK_REMIND_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_remind_days)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(add_conv)
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("upcoming", cmd_upcoming))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_check, "cron", hour=9, minute=0, args=[app])
    scheduler.start()

    log.info("🎂 Events Bot запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
