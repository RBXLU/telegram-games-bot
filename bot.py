from unittest.mock import call
import telebot
from telebot import types
import random
import time
from threading import Thread
from flask import Flask
import html
import json
import threading
from datetime import datetime, date
import os
from datetime import datetime, timedelta
import uuid
from groq import Groq


# ---------- BOT SETUP ----------
TOKEN = "8592750651:AAFuvdC6AIEXzD_WbJrx0p5Bq9wPO23bfwA"
bot = telebot.TeleBot(TOKEN)
bot.delete_webhook()

# ---------- CONFIGURATION ----------
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

FREE_DAILY_QUOTA = 10
PREMIUM_DAYS = 30

DATA_FILE = "ai_users.json"
# Название канала для обязательной подписки (если нужно)
REQUIRED_CHANNEL = "@minigamesbottgk"  # или None

# ---------- AI MODES ----------
AI_MODES = {
    "chat": "Обычный дружелюбный помощник",
    "short": "Отвечай максимально кратко, 1–2 предложения",
    "long": "Отвечай подробно и развернуто",
    "code": "Ты опытный программист, пиши код и объясняй"
}

# Параметры тарифа
FREE_DAILY_QUOTA = 10   # бесплатный тариф: 10 запросов в день
PREMIUM_PRICE = 5       # произвольная метка; не производит оплату — логика "пометка"
PREMIUM_PERIOD_DAYS = 30

# Путь к файлу хранения данных
DATA_FILE = "bot_data.json"

_storage_lock = threading.Lock()

def _ensure_data_file(path):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"users": {}, "premium": {}, "ai_cache": {}, "stats": {}}, f, ensure_ascii=False, indent=2)

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(uid):
    data = load_data()
    users = data["users"]
    today = date.today().isoformat()

    if str(uid) not in users:
        users[str(uid)] = {
            "count": 0,
            "date": today,
            "premium_until": 0,
            "pending": {}
        }

    user = users[str(uid)]

    if user["date"] != today:
        user["date"] = today
        user["count"] = 0

    save_data(data)
    return user

def has_premium(uid):
    user = get_user(uid)
    return user["premium_until"] > time.time()

def can_use_ai(uid):
    user = get_user(uid)
    if has_premium(uid):
        return True, None
    if user["count"] < FREE_DAILY_QUOTA:
        return True, None
    return False, "⚠️ Лимит 10 запросов в день. Купите премиум для неограниченного доступа."

# Утилиты
def get_user_record(user_id):
    data = load_data()
    users = data.setdefault("users", {})
    return users.setdefault(str(user_id), {
        "daily_count": 0,
        "daily_date": date.today().isoformat(),
        "is_premium": False,
        "premium_until": None,
    })

def reset_daily_if_needed(user_id):
    rec = get_user_record(user_id)
    today = date.today().isoformat()
    if rec.get("daily_date") != today:
        rec["daily_date"] = today
        rec["daily_count"] = 0
        d = load_data()
        d["users"][str(user_id)] = rec
        save_data(d)

def inc_user_count(user_id):
    d = load_data()
    rec = d.setdefault("users", {}).setdefault(str(user_id), {"daily_count":0,"daily_date":date.today().isoformat(),"is_premium":False})
    # reset if needed
    if rec.get("daily_date") != date.today().isoformat():
        rec["daily_date"] = date.today().isoformat()
        rec["daily_count"] = 0
    rec["daily_count"] = rec.get("daily_count",0) + 1
    d["users"][str(user_id)] = rec
    save_data(d)
    return rec["daily_count"]

def set_premium(user_id, until_timestamp):
    d = load_data()
    d.setdefault("premium", {})[str(user_id)] = {"until": until_timestamp}
    # also set users field
    user = d.setdefault("users", {}).setdefault(str(user_id), {})
    user["is_premium"] = True
    user["premium_until"] = until_timestamp
    save_data(d)

def clear_premium(user_id):
    d = load_data()
    if str(user_id) in d.get("premium", {}):
        del d["premium"][str(user_id)]
    user = d.setdefault("users", {}).setdefault(str(user_id), {})
    user["is_premium"] = False
    user["premium_until"] = None
    save_data(d)
    
def has_active_premium(user_id):
    d = load_data()
    user = d.get("users", {}).get(str(user_id), {})
    until = user.get("premium_until")
    if not until:
        return False
    try:
        return datetime.fromtimestamp(until) > datetime.utcnow()
    except:
        return False

def start_premium_watcher(bot_instance, check_interval=3600):
    """Фоновой поток: каждую check_interval сек проверяет премиум-аккаунты и шлет напоминания за 24h и при окончании."""
    def watcher():
        while True:
            try:
                data = load_data()
                pm = data.get("premium", {})
                now = datetime.utcnow()
                for uid_str, info in list(pm.items()):
                    try:
                        until_ts = info.get("until")
                        if not until_ts:
                            continue
                        until_dt = datetime.fromtimestamp(until_ts)
                        diff = until_dt - now
                        uid = int(uid_str)
                        # за 24 часа — напоминание
                        if 0 < diff.total_seconds() <= 24*3600 and not info.get("reminded_24h"):
                            try:
                                bot_instance.send_message(uid, f"⚠️ Ваша премиум-подписка истекает {until_dt.isoformat()} UTC. Продлите, чтобы не потерять доступ.")
                            except Exception as e:
                                print("notify 24h fail", e)
                            info["reminded_24h"] = True
                        # истекло — уведомляем и помечаем как неактивное
                        if diff.total_seconds() <= 0:
                            try:
                                bot_instance.send_message(uid, "⚠️ Ваша премиум-подписка окончена. Пока не продлите — премиум приостановлен.")
                            except Exception as e:
                                print("notify expired fail", e)
                            # удаляем/обнуляем
                            clear_premium(uid)
                            if str(uid) in pm:
                                del pm[str(uid)]
                    except Exception as e:
                        print("premium loop inner error", e)
                data["premium"] = pm
                save_data(data)
            except Exception as e:
                print("premium watcher error", e)
            time.sleep(check_interval)
    t = Thread(target=watcher, daemon=True)
    t.start()
    
def user_quota_allows(user_id):
    reset_daily_if_needed(user_id)
    rec = get_user_record(user_id)

    if has_active_premium(user_id):
        return True, None

    if rec.get("daily_count", 0) < FREE_DAILY_QUOTA:
        return True, None

    return False, f"⚠️ Лимит бесплатных запросов достигнут ({FREE_DAILY_QUOTA}/день). Купите премиум."

# ------------------- QUESTIONS -------------------
questions = [
    {
        "question": "Что такое Python?",
        "options": ["Язык программирования", "Программа", "Страна", "Ничего не подходит"],
        "answer": "Язык программирования"
    },
    {
        "question": "Что такое Roblox?",
        "options": ["Язык программирования", "Приложение", "Игра", "Платформа"],
        "answer": "Платформа"
    },
    {
        "question": "Какой тип данных используется для хранения текста в Python?",
        "options": ["int", "str", "float", "bool"],
        "answer": "str"
    },
    {
        "question": "Столица Франции?",
        "options": ["Париж", "Берлин", "Мадрид", "Рим"],
        "answer": "Париж"
    },
    {
        "question": "Сколько будет 2 + 2?",
        "options": ["3", "4", "5", "22"],
        "answer": "5"
    },
    {
        "question": "Какой океан самый большой?",
        "options": ["Тихий", "Атлантический", "Индийский", "Северный Ледовитый"],
        "answer": "Тихий"
    }
]

# ------------------- INLINE / GAME STATES -------------------
inline_ttt_games = {}
inline_guess_games = {}
inline_rps_games = {}
inline_snake_games = {}
inline_coin_games = {}
inline_slot_games = {}
# ---------------- SYSTEM NOTIFICATION STORAGE ----------------
user_sys_settings = {}      # uid -> {msg, btn, title, gui}
system_notify_wait = {}     # uid -> "field"
millionaire_games = {}   # short_id -> {"question":..., "attempts":int}

# in-memory games
games_flappy = {}   # gid -> {"bird_y":int,"pipes":[(x,gap)],"score":int}
games_2048 = {}     # gid -> {"board": [[int]]}
games_pong = {}     # gid -> {"players":[id_or_None,id_or_None],"paddles":[y1,y2],"ball":[x,y,dx,dy],"started":bool}
user_ai_mode = {}  # user_id -> mode


# ------------------- HELPERS -------------------
def short_id():
    return str(int(time.time()*1000))

# ------------------- KEYBOARDS -------------------
def snake_controls():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⬆️", callback_data="snake_up"))
    kb.row(types.InlineKeyboardButton("⬅️", callback_data="snake_left"),
           types.InlineKeyboardButton("➡️", callback_data="snake_right"))
    kb.row(types.InlineKeyboardButton("⬇️", callback_data="snake_down"))
    return kb

def telos_main_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📁 Файлы", callback_data="os_files"),
           types.InlineKeyboardButton("📝 Заметки", callback_data="os_notes"))
    kb.add(types.InlineKeyboardButton("🎮 Игры", callback_data="os_games"),
           types.InlineKeyboardButton("💬 Терминал", callback_data="os_terminal"))
    kb.add(types.InlineKeyboardButton("⚙️ Настройки", callback_data="os_settings"))
    kb.add(types.InlineKeyboardButton("⏻ Выключить", callback_data="os_shutdown"))
    return kb

def eng_keyboard():
    kb = types.InlineKeyboardMarkup()
    rows = [
        ['Q','W','E','R','T','Y','U','I','O','P'],
        ['A','S','D','F','G','H','J','K','L'],
        ['Z','X','C','V','B','N','M']
    ]
    for row in rows:
        kb.add(*[types.InlineKeyboardButton(k, callback_data=f"key_{k}") for k in row])
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="os_back"))
    return kb

def ask_ai(prompt: str, user_id: int) -> str:
    try:
        if not prompt.strip():
            return "⚠️ Напиши вопрос текстом"

        mode = user_ai_mode.get(user_id, "chat")
        system_prompt = AI_MODES.get(mode, AI_MODES["chat"])

        chat = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt[:2000]}
            ],
            temperature=0.7,
            max_tokens=900
        )

        return chat.choices[0].message.content

    except Exception as e:
        print("AI ERROR:", repr(e))
        return "❌ Ошибка при получении ответа"

# ------------------- TTT (улучшённый модуль) -------------------
def _user_display_name_from_id(uid):
    try:
        u = bot.get_chat(uid)  # обычно работает для пользователей
        name = u.username or (u.first_name or f"Player_{uid}")
        return name
    except Exception:
        return f"Player_{uid}"

def ttt_render_header(game):
    p1_id, p2_id = game["players"][0], game["players"][1]
    p1_name = game["names"].get(p1_id, _user_display_name_from_id(p1_id))
    p2_name = game["names"].get(p2_id, _user_display_name_from_id(p2_id))
    score1 = game["scores"].get(p1_id, 0)
    score2 = game["scores"].get(p2_id, 0)
    line1 = f"❌ {p1_name} — {score1}"
    line2 = f"⭕ {p2_name} — {score2}"
    turn_symbol = "❌" if game["turn"] == p1_id else "⭕"
    return f"{line1}\n{line2}\n\nХодит: {turn_symbol}\n\n"

def ttt_render_board(board):
    # board - list of 9 entries: " ", "❌", "⭕"
    lines = []
    for r in range(3):
        row = []
        for c in range(3):
            v = board[r*3 + c]
            row.append(v if v.strip() else "⬜️")
        lines.append(" ".join(row))
    return "\n".join(lines)

def ttt_build_keyboard(gid, board):
    kb = types.InlineKeyboardMarkup()
    symbols_map = {" ": "⬜️", "❌": "❌", "⭕": "⭕️"}
    for r in range(3):
        row = []
        for c in range(3):
            idx = r*3 + c
            label = symbols_map.get(board[idx], "⬜️")
            row.append(types.InlineKeyboardButton(label, callback_data=f"ttt_move_{gid}_{idx}"))
        kb.row(*row)
    # add restart button
    kb.row(types.InlineKeyboardButton("🔁 Сыграть ещё", callback_data=f"ttt_restart_{gid}"))
    return kb

# ------------------- /start -------------------
@bot.message_handler(commands=["start"])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ Крестики-нолики", "💰 Миллионер"),
    markup.add("🐣 Пасхалка", "🪙 Орёл или решка")
    markup.add("🖥 TELOS v1.0", "🔢 Угадай число")
    markup.add("✂ Камень-ножницы-бумага", "🐍 Змейка")
    markup.add("🎰 Казино", "🐦 Flappy Bird")
    markup.add("🔢 2048", "🏓 Пинг-понг")
    markup.add("🚀 Поддержать автора")
    bot.send_message(message.chat.id, "🎮 Привет! Выбери игру:\n\nМало кто знает, но скоро будет возможность подключения через Telegram Premium!", reply_markup=markup)

@bot.message_handler(commands=["settext"])
def settext_cmd(message):
    uid = message.from_user.id

    if uid not in user_sys_settings:
        user_sys_settings[uid] = {
            "msg": "Ваше сообщение",
            "btn": "ОК",
            "title": "Заголовок",
            "gui": "Текст внутри GUI"
        }

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("1. Изменить текст сообщения", callback_data="set_msg"))
    kb.add(types.InlineKeyboardButton("2. Изменить текст кнопки", callback_data="set_btn"))
    kb.add(types.InlineKeyboardButton("3. Изменить заголовок GUI", callback_data="set_title"))
    kb.add(types.InlineKeyboardButton("4. Изменить текст GUI", callback_data="set_gui"))

    bot.send_message(
        message.chat.id,
        "🔧 *Настройки системного уведомления*\nВыбери, что изменить:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["mode"])
def set_mode(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💬 Чат", callback_data="mode_chat"))
    kb.add(types.InlineKeyboardButton("⚡ Кратко", callback_data="mode_short"))
    kb.add(types.InlineKeyboardButton("🧠 Подробно", callback_data="mode_long"))
    kb.add(types.InlineKeyboardButton("💻 Код", callback_data="mode_code"))

    bot.send_message(
        message.chat.id,
        "🎛 Выбери режим ответа AI:",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text == "❌ Крестики-нолики")
def ttt(message):
    bot.send_message(message.chat.id, "Чтобы играть в крестики-нолики - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "💰 Миллионер")
def millionaire(message):
    bot.send_message(message.chat.id, "Чтобы играть в миллионера - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🐣 Пасхалка")
def pashalka(message):
    bot.send_message(message.chat.id, "Чтобы запустить анимацию пасхалки - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🪙 Орёл или решка")
def orel(message):
    bot.send_message(message.chat.id, "Чтобы играть в орёл или решка - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🖥 TELOS v1.0")
def telos(message):
    bot.send_message(message.chat.id, "Чтобы запустить мини ос - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🔢 Угадай число")
def ugadayka(message):
    bot.send_message(message.chat.id, "Чтобы играть в угадай число - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "✂ Камень-ножницы-бумага")
def rsp(message):
    bot.send_message(message.chat.id, "Чтобы играть в камень ножницы бумага - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🐍 Змейка")
def snake(message):
    bot.send_message(message.chat.id, "Чтобы играть в змейку - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🎰 Казино")
def casino(message):
    bot.send_message(message.chat.id, "Чтобы запустить казино - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🐦 Flappy Bird")
def flappybird(message):
    bot.send_message(message.chat.id, "Чтобы играть в flappy Bird - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🔢 2048")
def dvsorokvosem(message):
    bot.send_message(message.chat.id, "Чтобы играть в 2048 - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(func=lambda m: m.text == "🏓 Пинг-понг")
def pingpong(message):
    bot.send_message(message.chat.id, "Чтобы играть в пинг-понг - напиши @animkabyrbxbot в любом чате!")

@bot.message_handler(commands=["connect"])
def connect(message):
    bot.send_message(message.chat.id, "Внимание‼\n⚠ Данная функция сейчас в разработке.\n⚠ Для подключения бота требуется подписка Telegram Premium! Вы можете продолжать пользоватся ботом бесплатно через inline режим.\n\n<b>Как подключить бота?</b>\nИнструкция:\n1. Скопируйте имя <code>@animkabyrbxbot</code> нажав на него\n2. Перейдите в Настройки -> Telegram для бизнеса -> Чат-боты\n3. Вставьте скопированное имя и примените изменения\n‼️ Обратите внимание что оригинал бота будет первым в списке\n")

@bot.message_handler(func=lambda m: m.text == "🚀 Поддержать автора")
def support(message):
        bot.send_message(message.chat.id, "Если вам нравится этот бот, вы можете поддержать автора отправив донат на карту:\n\n💳 <code>4441 1144 3356 7409</code>\n\nЗаранее cпасибо вашу поддержку!")


@bot.message_handler(func=lambda m: m.text == "🎮 Играть")
def play(message):
    bot.send_message(message.chat.id, "Чтобы играть — используй инлайн через @YourBotUsername в любом чате!")

@bot.inline_handler(lambda q: q.query.strip() != "")
def ai_inline(query):
    uid = query.from_user.id
    text = query.query.strip()

    allow, err = can_use_ai(uid)
    if not allow:
        bot.answer_inline_query(
            query.id,
            [types.InlineQueryResultArticle(
                id="nope",
                title="⚠️ Лимит",
                input_message_content=types.InputTextMessageContent(err)
            )],
            cache_time=1,
            is_personal=True
        )
        return

    req_id = uuid.uuid4().hex
    data = load_data()
    data["users"][str(uid)]["pending"][req_id] = {
        "q": text,
        "a": None,
        "status": "wait"
    }
    save_data(data)

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📩 Получить ответ", callback_data=f"ai_{uid}_{req_id}"))

    result = types.InlineQueryResultArticle(
        id=req_id,
        title="🤖 Спросить ChatGPT",
        description=text[:60],
        input_message_content=types.InputTextMessageContent(
            f"💬 *Вопрос:*\n{text}",
            parse_mode="Markdown"
        ),
        reply_markup=kb
    )

    bot.answer_inline_query(query.id, [result], cache_time=1, is_personal=True)

# ------------------- INLINE MAIN (empty query) -------------------
@bot.inline_handler(lambda q: q.query.strip() == "")
def inline_handler(query):
    try:
        user = query.from_user
        user_name = html.escape(user.first_name or "Игрок")
        starter_id = user.id
        results = []



        # TTT
        join_markup = types.InlineKeyboardMarkup()
        join_markup.add(types.InlineKeyboardButton("Присоединиться ⭕", callback_data=f"ttt_join_{starter_id}"))
        ttext = f"🎮 Крестики-нолики\n❌ {user_name}\n⭕ — (ожидается)\nНажмите «Присоединиться ⭕», чтобы начать."
        results.append(types.InlineQueryResultArticle(
            id=f"ttt_{short_id()}", title="❌ Крестики-нолики",
            description="Играть с другом (inline)",
            input_message_content=types.InputTextMessageContent(message_text=ttext, parse_mode="HTML"),
            reply_markup=join_markup))

        # Millionaire preview (creates short game id)
        qdata = random.choice(questions)
        gid = short_id()
        millionaire_games[gid] = {"question": qdata, "attempts": 3}
        markup_m = types.InlineKeyboardMarkup()
        for i, opt in enumerate(qdata["options"]):
            markup_m.add(types.InlineKeyboardButton(opt, callback_data=f"millionaire_{gid}_{i}"))
        results.append(types.InlineQueryResultArticle(
            id=f"millionaire_{gid}",
            title="💰 Миллионер",
            description="Попробуй ответить правильно",
            input_message_content=types.InputTextMessageContent(f"💰 {qdata['question']}\nОсталось попыток: 3"),
            reply_markup=markup_m
        ))

        # Easter
        egg_markup = types.InlineKeyboardMarkup()
        egg_markup.add(types.InlineKeyboardButton("🐣 Пасхалка", callback_data="easter_egg"))
        results.append(types.InlineQueryResultArticle(
            id=f"egg_{short_id()}",
            title="🐣 Пасхалка",
            description="Прикольная анимация",
            input_message_content=types.InputTextMessageContent("🐣 Нажми кнопку, чтобы активировать пасхалку!"),
            reply_markup=egg_markup
        ))

        # Coin flip
        coin_m = types.InlineKeyboardMarkup()
        coin_m.add(types.InlineKeyboardButton("Бросить 🪙", callback_data="coin_flip"))
        results.append(types.InlineQueryResultArticle(
            id=f"coin_{short_id()}",
            title="🪙 Орёл или решка",
            description="Подбрось монетку",
            input_message_content=types.InputTextMessageContent("🪙 Орёл или решка?"),
            reply_markup=coin_m
        ))

        # TELOS OS
        results.append(types.InlineQueryResultArticle(
            id=f"os_{short_id()}",
            title="🖥 TELOS v1.0 (macOS)",
            description="Открыть системное меню",
            input_message_content=types.InputTextMessageContent("🖥 *TELOS v1.0*\nВыбирай приложение:", parse_mode="Markdown"),
            reply_markup=telos_main_menu()
        ))

        # Guess number
        guess_m = types.InlineKeyboardMarkup()
        row = []
        for i in range(1, 11):
            row.append(types.InlineKeyboardButton(str(i), callback_data=f"guess_inline_{i}"))
            if i % 5 == 0:
                guess_m.row(*row)
                row = []
        results.append(types.InlineQueryResultArticle(
            id=f"guess_{short_id()}",
            title="🔢 Угадай число",
            description="От 1 до 10",
            input_message_content=types.InputTextMessageContent("🔢 Угадай число (1–10)"),
            reply_markup=guess_m
        ))

        # ---------- SYSTEM NOTIFICATION (inline preview) ----------
        # Если пользователь уже сохранил своё уведомление в ЛС через /settext -> set_...
        u_uid = query.from_user.id
        if u_uid in user_sys_settings:
            data = user_sys_settings[u_uid]
            # показываем только если хотя бы есть заголовок или текст — это настраиваемо
            if data.get("title") or data.get("msg"):
                sys_preview_id = short_id()
                btn_text = data.get("btn") or "Открыть"
                markup_sys = types.InlineKeyboardMarkup()
                # при клике откроется GUI автора (мы используем callback sysopen_{uid})
                markup_sys.add(types.InlineKeyboardButton(btn_text, callback_data=f"sysopen_{u_uid}"))
                results.append(types.InlineQueryResultArticle(
                    id=f"sys_{sys_preview_id}",
                    title="🔔 Системное уведомление",
                    description="Ваше сохранённое уведомление",
                    input_message_content=types.InputTextMessageContent(
                        f"🔔 *{data.get('title','Системное уведомление')}*\n{data.get('msg','')}",
                        parse_mode="Markdown"
                    ),
                    reply_markup=markup_sys
                ))

        # RPS
        rps_m = types.InlineKeyboardMarkup()
        rps_m.row(
            types.InlineKeyboardButton("🪨", callback_data=f"rps_{starter_id}_rock"),
            types.InlineKeyboardButton("📄", callback_data=f"rps_{starter_id}_paper"),
            types.InlineKeyboardButton("✂️", callback_data=f"rps_{starter_id}_scissors")
        )
        results.append(types.InlineQueryResultArticle(
            id=f"rps_{short_id()}",
            title="✂️ Камень-ножницы-бумага",
            description="Выбери ход",
            input_message_content=types.InputTextMessageContent("✂️ Камень, ножницы, бумага!"),
            reply_markup=rps_m
        ))

        # Slot
        slot_m = types.InlineKeyboardMarkup()
        slot_m.add(types.InlineKeyboardButton("🎰 Крутить", callback_data="slot_spin"))
        results.append(types.InlineQueryResultArticle(
            id=f"slot_{short_id()}",
            title="🎰 Казино",
            description="Испытай свое везение!",
            input_message_content=types.InputTextMessageContent("🎰 Казино запущено!"),
            reply_markup=slot_m
        ))

        # Snake
        results.append(types.InlineQueryResultArticle(
            id=f"snake_{short_id()}",
            title="🐍 Змейка",
            description="Инлайн-змейка",
            input_message_content=types.InputTextMessageContent("🐍 Используй кнопки, чтобы управлять!"),
            reply_markup=snake_controls()
        ))

        # Flappy preview
        fp_markup = types.InlineKeyboardMarkup()
        fp_markup.add(types.InlineKeyboardButton("⬆️ Прыжок (начать)", callback_data="flappy_new"))
        results.append(types.InlineQueryResultArticle(
            id=f"flappy_{short_id()}",
            title="🐦 Flappy Bird",
            description="Нажми, чтобы начать Flappy Bird",
            input_message_content=types.InputTextMessageContent("🐦 Flappy Bird\nНажми кнопку, чтобы начать."),
            reply_markup=fp_markup
        ))

        # 2048 preview
        preview_markup = types.InlineKeyboardMarkup()
        preview_markup.row(types.InlineKeyboardButton("⬆️", callback_data="g2048_new_up"))
        preview_markup.row(types.InlineKeyboardButton("⬅️", callback_data="g2048_new_left"),
                           types.InlineKeyboardButton("➡️", callback_data="g2048_new_right"))
        preview_markup.row(types.InlineKeyboardButton("⬇️", callback_data="g2048_new_down"))
        results.append(types.InlineQueryResultArticle(
            id=f"g2048_{short_id()}",
            title="🔢 2048",
            description="Нажми стрелку, чтобы начать",
            input_message_content=types.InputTextMessageContent("🔢 2048\nНажми кнопку, чтобы начать."),
            reply_markup=preview_markup
        ))

        # Pong preview
        pgid = short_id()
        pm = types.InlineKeyboardMarkup()
        pm.add(types.InlineKeyboardButton("Присоединиться", callback_data=f"pong_{pgid}_join"))
        results.append(types.InlineQueryResultArticle(
            id=f"pong_{pgid}",
            title="🏓 Пинг-понг (2 игрока)",
            description="Нажмите 'Присоединиться' чтобы стать игроком",
            input_message_content=types.InputTextMessageContent("🏓 Пинг-понг\nНажмите 'Присоединиться' чтобы игра началась."),
            reply_markup=pm
        ))



        bot.answer_inline_query(query.id, results, cache_time=1, is_personal=True)

    except Exception as e:
        print("INLINE ERROR:", e)

# ------------------- Flappy (variant B) -------------------
def render_flappy_state(state):
    W, H = 10, 10
    field = [["⬛" for _ in range(W)] for _ in range(H)]
    for x, gap in state["pipes"]:
        for y in range(H):
            if not (gap <= y <= gap+2):
                if 0 <= x < W:
                    field[y][x] = "🟥"
    by = int(state["bird_y"])
    if 0 <= by < H:
        field[by][2] = "🐦"
    return "\n".join("".join(r) for r in field)

@bot.callback_query_handler(func=lambda c: c.data.startswith("flappy_"))
def flappy_callback(call):
    try:
        parts = call.data.split("_", 2)  # flappy_new OR flappy_<gid>_jump
        if parts[1] == "new":
            gid = short_id()
            games_flappy[gid] = {"bird_y":5, "pipes":[(9,3),(13,4)], "score":0}
            state = games_flappy[gid]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬆️ Прыжок", callback_data=f"flappy_{gid}_jump"))
            bot.edit_message_text(f"🐦 Flappy Bird\nОчки: {state['score']}\n\n{render_flappy_state(state)}",
                                  inline_message_id=call.inline_message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)
            return

        gid = parts[1]
        action = parts[2] if len(parts) > 2 else "jump"
        state = games_flappy.get(gid)
        if not state:
            bot.answer_callback_query(call.id, "Игра не найдена.")
            return

        # Advance simulation: pipes move left
        state["pipes"] = [(x-1, gap) for x,gap in state["pipes"]]
        if state["pipes"] and state["pipes"][-1][0] < 6:
            state["pipes"].append((9, random.randint(2,6)))

        # Player action
        if action == "jump":
            state["bird_y"] -= 2
        # gravity
        state["bird_y"] += 1

        # scoring: when pipe passes x==1 (just after bird) increment
        new_pipes = []
        for x,gap in state["pipes"]:
            if x >= 0:
                new_pipes.append((x,gap))
            if x == 1:
                state["score"] += 1
        state["pipes"] = new_pipes

        # collision
        by = state["bird_y"]
        collided = False
        if by < 0 or by >= 10:
            collided = True
        else:
            for x,gap in state["pipes"]:
                if x == 2:  # bird x pos is 2
                    if not (gap <= by <= gap+2):
                        collided = True
                        break

        if collided:
            bot.edit_message_text(f"💥 Вы проиграли! Очки: {state['score']}", inline_message_id=call.inline_message_id)
            games_flappy.pop(gid, None)
            bot.answer_callback_query(call.id, "Игра окончена")
            return

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬆️ Прыжок", callback_data=f"flappy_{gid}_jump"))
        bot.edit_message_text(f"🐦 Flappy Bird\nОчки: {state['score']}\n\n{render_flappy_state(state)}",
                              inline_message_id=call.inline_message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print("FLAPPY ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка игры Flappy")

# ------------------- AI HANDLER -------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("ai_"))
def ai_callback(call):
    try:
        _, uid, rid = call.data.split("_")
        uid = int(uid)

        data = load_data()
        user = data["users"].get(str(uid))
        if not user:
            bot.answer_callback_query(call.id, "Данные пользователя не найдены")
            return

        req = user["pending"].get(rid)
        if not req:
            bot.answer_callback_query(call.id, "Запрос устарел")
            return

        # если ещё не считали — запускаем
        if req["status"] == "wait":
            req["status"] = "process"
            save_data(data)

            def work():
                try:
                    prompt = req["q"]
                    answer = ask_ai(prompt, uid)
                    inc_user_count(uid)
                
                    req["a"] = answer
                    req["status"] = "done"
                    save_data(data)

                except Exception as e:
                    req["a"] = f"Ошибка AI: {e}"
                    req["status"] = "done"
                    save_data(data)

            Thread(target=work, daemon=True).start()
            bot.answer_callback_query(call.id, "⏳ Готовлю ответ…")
            return

        # если готово
        if req["status"] == "done":
            answer = req["a"]

            # 🔹 КОРОТКИЙ → alert
            if len(answer) <= 180:
                bot.answer_callback_query(call.id, "✅ Ответ готов!")
                bot.send_message(call.from_user.id, f"🤖 Ответ:\n\n{answer[:4000]}")

                return

            # 🔹 ДЛИННЫЙ → редактируем inline сообщение
            text = (
                "🤖 *Ответ ChatGPT:*\n\n"
                + answer[:3900]  # запас
            )

            bot.edit_message_text(
                text,
                inline_message_id=call.inline_message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

    except Exception as e:
        print("AI CALLBACK ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка при получении ответа")

# ------------------- TTT HANDLER -------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_join_"))
def ttt_join(call):
    try:
        # data format: ttt_join_{host_id}
        parts = call.data.split("_")
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "Неверные данные.")
            return
        host_id = int(parts[2])
        guest_id = call.from_user.id

        if host_id == guest_id:
            bot.answer_callback_query(call.id, "Вы не можете играть сами с собой!")
            return

        # create game id
        gid = short_id()

        # try to fetch display names (store them now)
        host_name = _user_display_name_from_id(host_id)
        guest_name = call.from_user.username or call.from_user.first_name or f"Player_{guest_id}"

        # initial game state: scores start at 0
        inline_ttt_games[gid] = {
            "board": [" "] * 9,
            "players": [host_id, guest_id],   # players[0] -> ❌, players[1] -> ⭕
            "names": {host_id: host_name, guest_id: guest_name},
            "scores": {host_id: 0, guest_id: 0},
            # make guest (⭕) go first to match example "Ходит: ⭕"
            "turn": guest_id
        }

        game = inline_ttt_games[gid]
        text = ttt_render_header(game) + ttt_render_board(game["board"])
        kb = ttt_build_keyboard(gid, game["board"])

        bot.edit_message_text(text, inline_message_id=call.inline_message_id, reply_markup=kb, parse_mode=None)
        bot.answer_callback_query(call.id, "Игра началась! Удачи.")
    except Exception as e:
        print("TTT JOIN ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка при создании игры TTT.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_move_"))
def ttt_move(call):
    try:
        # data: ttt_move_{gid}_{cell}
        parts = call.data.split("_")
        if len(parts) < 4:
            bot.answer_callback_query(call.id, "Неверные данные хода.")
            return
        gid = parts[2]
        cell = int(parts[3])
        game = inline_ttt_games.get(gid)
        if not game:
            bot.answer_callback_query(call.id, "Игра не найдена или завершена.")
            return

        uid = call.from_user.id
        if uid not in game["players"]:
            bot.answer_callback_query(call.id, "Вы не участник этой игры.")
            return

        if uid != game["turn"]:
            bot.answer_callback_query(call.id, "Сейчас не ваш ход!")
            return

        if not (0 <= cell < 9):
            bot.answer_callback_query(call.id, "Неверная клетка.")
            return

        if game["board"][cell].strip():
            bot.answer_callback_query(call.id, "Клетка уже занята!")
            return

        # decide symbol
        symbol = "❌" if uid == game["players"][0] else "⭕"
        game["board"][cell] = symbol

        # check win
        b = game["board"]
        def win(bd, s):
            patterns = [
                (0,1,2),(3,4,5),(6,7,8),
                (0,3,6),(1,4,7),(2,5,8),
                (0,4,8),(2,4,6)
            ]
            for a,bp,c in patterns:
                if bd[a] == bd[bp] == bd[c] == s:
                    return True
            return False

        if win(b, symbol):
            # increment winner score
            winner_id = uid
            game["scores"][winner_id] = game["scores"].get(winner_id, 0) + 1
            title = f"🎉 Победил {symbol} — {game['names'].get(winner_id, _user_display_name_from_id(winner_id))}!"
            # show final board and scores
            text = title + "\n\n" + ttt_render_header(game) + ttt_render_board(game["board"])
            # keep scores but reset board for next round only on restart; here we display final and keep game entry to allow restart
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔁 Сыграть ещё", callback_data=f"ttt_restart_{gid}"))
            bot.edit_message_text(text, inline_message_id=call.inline_message_id, reply_markup=kb)
            # remove the game board but keep scores so restart can reuse
            game["board"] = [" "] * 9
            game["turn"] = game["players"][0]  # default who starts next (you can change)
            bot.answer_callback_query(call.id, "Победа!")
            return

        # check draw
        if " " not in b:
            text = "🤝 Ничья!\n\n" + ttt_render_header(game) + ttt_render_board(game["board"])
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔁 Сыграть ещё", callback_data=f"ttt_restart_{gid}"))
            bot.edit_message_text(text, inline_message_id=call.inline_message_id, reply_markup=kb)
            game["board"] = [" "] * 9
            game["turn"] = game["players"][0]
            bot.answer_callback_query(call.id, "Ничья!")
            return

        # next turn
        game["turn"] = game["players"][1] if uid == game["players"][0] else game["players"][0]

        # render updated board
        text = ttt_render_header(game) + ttt_render_board(game["board"])
        kb = ttt_build_keyboard(gid, game["board"])
        bot.edit_message_text(text, inline_message_id=call.inline_message_id, reply_markup=kb)
        bot.answer_callback_query(call.id, "Ход сделан.")
    except Exception as e:
        print("TTT MOVE ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка в ходе крестиков-ноликов.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_restart_"))
def ttt_restart(call):
    try:
        parts = call.data.split("_")
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "Неверные данные рестарта.")
            return
        gid = parts[2]
        game = inline_ttt_games.get(gid)
        if not game:
            bot.answer_callback_query(call.id, "Игра не найдена.")
            return
        # reset board but keep scores and names
        game["board"] = [" "] * 9
        # let O (players[1]) start next as before or alternate if you like
        game["turn"] = game["players"][1]
        text = ttt_render_header(game) + ttt_render_board(game["board"])
        kb = ttt_build_keyboard(gid, game["board"])
        bot.edit_message_text(text, inline_message_id=call.inline_message_id, reply_markup=kb)
        bot.answer_callback_query(call.id, "Новая партия — удачи!")
    except Exception as e:
        print("TTT RESTART ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка при рестарте игры.")

# ------------------- 2048 -------------------
def spawn_tile(board):
    empty = [(y, x) for y in range(4) for x in range(4) if board[y][x] == 0]
    if not empty:
        return board
    y, x = random.choice(empty)
    board[y][x] = 2 if random.random() < 0.9 else 4
    return board

def render_2048(board):
    COLORS = {
        0:   "⬜",   # пустая
        2:   "🟫",
        4:   "🟫",
        8:   "🟧",
        16:  "🟧",
        32:  "🟧",
        64:  "🟨",
        128: "🟨",
        256: "🟦",
        512: "🟦",
        1024: "🟪",
        2048: "🟧"
    }

    def cell(n):
        color = COLORS.get(n, "🟪")
        num = str(n) if n != 0 else ""
        return f"{color}{num.center(4)}{color}"

    top = "┌" + "───────" * 4 + "┐"
    sep = "├" + "───────" * 4 + "┤"
    bot = "└" + "───────" * 4 + "┘"

    lines = [top]
    for i, row in enumerate(board):
        line = "│"
        for c in row:
            line += cell(c)
        line += "│"
        lines.append(line)
        if i < 3:
            lines.append(sep)
    lines.append(bot)

    return "\n".join(lines)

def move_row_left(row):
    new = [v for v in row if v != 0]
    res = []
    i = 0
    while i < len(new):
        if i+1 < len(new) and new[i] == new[i+1]:
            res.append(new[i]*2)
            i += 2
        else:
            res.append(new[i])
            i += 1
    res += [0]*(4-len(res))
    return res

def move_board(board, direction):
    moved = False
    new = [[board[y][x] for x in range(4)] for y in range(4)]
    if direction in ("left","right"):
        for y in range(4):
            row = list(new[y])
            if direction == "right":
                row = row[::-1]
            moved_row = move_row_left(row)
            if direction == "right":
                moved_row = moved_row[::-1]
            if moved_row != new[y]:
                moved = True
            new[y] = moved_row
    else:
        cols = [[new[y][x] for y in range(4)] for x in range(4)]
        for x in range(4):
            col = cols[x]
            if direction == "down":
                col = col[::-1]
            moved_col = move_row_left(col)
            if direction == "down":
                moved_col = moved_col[::-1]
            for y in range(4):
                if new[y][x] != moved_col[y]:
                    moved = True
                new[y][x] = moved_col[y]
    return new, moved

@bot.inline_handler(lambda q: q.query.lower() == "2048" or q.query.strip() == "2048")
def inline_2048(query):
    board = [[0]*4 for _ in range(4)]
    board = spawn_tile(board); board = spawn_tile(board)
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("⬆️", callback_data="g2048_new_up"))
    markup.row(types.InlineKeyboardButton("⬅️", callback_data="g2048_new_left"),
               types.InlineKeyboardButton("➡️", callback_data="g2048_new_right"))
    markup.row(types.InlineKeyboardButton("⬇️", callback_data="g2048_new_down"))
    results = [types.InlineQueryResultArticle(
        id=f"g2048_preview_{short_id()}",
        title="🔢 2048",
        description="Нажми стрелку, чтобы начать",
        input_message_content=types.InputTextMessageContent("🔢 2048\nНажми кнопку, чтобы начать."),
        reply_markup=markup
    )]
    bot.answer_inline_query(query.id, results, cache_time=1, is_personal=True)

@bot.callback_query_handler(func=lambda c: c.data in ["set_msg", "set_btn", "set_title", "set_gui"])
def sys_set_field(call):
    field = call.data.replace("set_", "")  # msg, btn, title, gui
    uid = call.from_user.id

    system_notify_wait[uid] = field
    bot.answer_callback_query(call.id)
    bot.send_message(uid, f"✏ Введите новое значение для поля: {field}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("g2048_"))
def g2048_callback(call):
    try:
        parts = call.data.split("_", 2)
        # g2048_new_left OR g2048_<gid>_left
        if parts[1] == "new":
            gid = short_id()
            board = [[0]*4 for _ in range(4)]
            board = spawn_tile(board); board = spawn_tile(board)
            games_2048[gid] = {"board": board}
            direction = parts[2]
        else:
            gid = parts[1]
            direction = parts[2]
            if gid not in games_2048:
                bot.answer_callback_query(call.id, "Игра не найдена")
                return
            board = games_2048[gid]["board"]

        new_board, moved = move_board(board, direction)
        if moved:
            new_board = spawn_tile(new_board)
        games_2048[gid] = {"board": new_board}

        flat = sum(new_board, [])
        if 2048 in flat:
            bot.edit_message_text("🎉 Вы собрали 2048! Победа!", inline_message_id=call.inline_message_id)
            games_2048.pop(gid, None)
            bot.answer_callback_query(call.id)
            return

        moves_possible = False
        for y in range(4):
            for x in range(4):
                if new_board[y][x] == 0:
                    moves_possible = True
                if x<3 and new_board[y][x] == new_board[y][x+1]:
                    moves_possible = True
                if y<3 and new_board[y][x] == new_board[y+1][x]:
                    moves_possible = True
        if not moves_possible:
            bot.edit_message_text("💀 Game over — ходов нет.", inline_message_id=call.inline_message_id)
            games_2048.pop(gid, None)
            bot.answer_callback_query(call.id)
            return

        # render controls
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("⬆️", callback_data=f"g2048_{gid}_up"))
        markup.row(types.InlineKeyboardButton("⬅️", callback_data=f"g2048_{gid}_left"),
                   types.InlineKeyboardButton("➡️", callback_data=f"g2048_{gid}_right"))
        markup.row(types.InlineKeyboardButton("⬇️", callback_data=f"g2048_{gid}_down"))
        bot.edit_message_text(f"🔢 2048\n\n{render_2048(new_board)}", inline_message_id=call.inline_message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print("2048 ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка 2048")

# ------------------- Pong (2 players) -------------------
def render_pong_state(state):
    W, H = 11, 7
    field = [["⬛" for _ in range(W)] for _ in range(H)]
    p1x, p2x = 1, 9
    p1pos, p2pos = state["paddles"][0], state["paddles"][1]
    if 0 <= p1pos < H:
        field[p1pos][p1x] = "🟦"
    if 0 <= p2pos < H:
        field[p2pos][p2x] = "🟩"
    bx, by = state["ball"][0], state["ball"][1]
    if 0 <= bx < W and 0 <= by < H:
        field[by][bx] = "⚪"
    return "\n".join("".join(r) for r in field)

@bot.inline_handler(lambda q: q.query.lower() == "pong" or q.query.strip() == "pong" or q.query.lower() == "ping-pong")
def inline_pong(query):
    gid = short_id()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Присоединиться", callback_data=f"pong_{gid}_join"))
    results = [types.InlineQueryResultArticle(
        id=f"pong_preview_{gid}",
        title="🏓 Пинг-понг (2 игрока)",
        description="Нажмите 'Присоединиться' чтобы стать игроком",
        input_message_content=types.InputTextMessageContent("🏓 Пинг-понг\nНажмите 'Присоединиться' чтобы игра началась."),
        reply_markup=markup
    )]
    bot.answer_inline_query(query.id, results, cache_time=1, is_personal=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pong_"))
def pong_callback(call):
    try:
        parts = call.data.split("_", 2)
        gid = parts[1]
        action = parts[2] if len(parts) > 2 else ""
        state = games_pong.get(gid)
        if action == "join":
            if state is None:
                state = {"players":[None,None], "paddles":[3,3], "ball":[5,3,-1,0], "started":False}
                games_pong[gid] = state
            uid = call.from_user.id
            if uid in state["players"]:
                bot.answer_callback_query(call.id, "Вы уже в игре")
                return
            if state["players"][0] is None:
                state["players"][0] = uid
                msg = "Вы — Игрок 1 (слева)"
            elif state["players"][1] is None:
                state["players"][1] = uid
                msg = "Вы — Игрок 2 (справа)"
            else:
                bot.answer_callback_query(call.id, "Комната полна")
                return
            if state["players"][0] and state["players"][1]:
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton("⬅️", callback_data=f"pong_{gid}_L"),
                           types.InlineKeyboardButton("➡️", callback_data=f"pong_{gid}_R"))
                markup.add(types.InlineKeyboardButton("Старт", callback_data=f"pong_{gid}_start"))
                bot.edit_message_text("Игроки присоединились. Нажмите Старт.", inline_message_id=call.inline_message_id, reply_markup=markup)
            else:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("Присоединиться", callback_data=f"pong_{gid}_join"))
                bot.edit_message_text(f"{msg}\nОжидаем второго игрока...", inline_message_id=call.inline_message_id, reply_markup=markup)
            bot.answer_callback_query(call.id, msg)
            return

        if state is None:
            bot.answer_callback_query(call.id, "Игра не найдена")
            return
        uid = call.from_user.id
        if uid not in state["players"]:
            bot.answer_callback_query(call.id, "Вы не участник игры")
            return

        if action in ("L","R"):
            pidx = 0 if uid == state["players"][0] else 1
            if action == "L":
                state["paddles"][pidx] = max(0, state["paddles"][pidx] - 1)
            else:
                state["paddles"][pidx] = min(6, state["paddles"][pidx] + 1)
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("⬅️", callback_data=f"pong_{gid}_L"),
                       types.InlineKeyboardButton("➡️", callback_data=f"pong_{gid}_R"))
            bot.edit_message_text(render_pong_state(state), inline_message_id=call.inline_message_id, reply_markup=markup)
            bot.answer_callback_query(call.id, "Paddle moved")
            return

        if action == "start":
            if state["started"]:
                bot.answer_callback_query(call.id, "Игра уже запущена")
                return
            state["started"] = True
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("⬅️", callback_data=f"pong_{gid}_L"),
                       types.InlineKeyboardButton("➡️", callback_data=f"pong_{gid}_R"))
            bot.edit_message_text(render_pong_state(state), inline_message_id=call.inline_message_id, reply_markup=markup)
            bot.answer_callback_query(call.id, "Старт!")
            return

        bot.answer_callback_query(call.id)
    except Exception as e:
        print("PONG ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка Pong")

# ------------------- MILLIONAIRE HANDLER -------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("millionaire_"))
def millionaire_callback(call):
    try:
        _, game_id, index = call.data.split("_")
        index = int(index)
        game = millionaire_games.get(game_id)
        if not game:
            bot.answer_callback_query(call.id, "Игра завершена!")
            return
        question = game["question"]
        answer = question["options"][index]
        if answer == question["answer"]:
            bot.edit_message_text(f"🎉 Правильно! Ответ: {answer}", inline_message_id=call.inline_message_id)
            millionaire_games.pop(game_id, None)
            return
        game["attempts"] -= 1
        if game["attempts"] == 0:
            bot.edit_message_text(f"💀 Вы проиграли!\nПравильный ответ: {question['answer']}", inline_message_id=call.inline_message_id)
            millionaire_games.pop(game_id, None)
            return
        markup = types.InlineKeyboardMarkup()
        for i, option in enumerate(question["options"]):
            markup.add(types.InlineKeyboardButton(option, callback_data=f"millionaire_{game_id}_{i}"))
        bot.edit_message_text(f"💰 {question['question']}\nОсталось попыток: {game['attempts']}", inline_message_id=call.inline_message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print("MILL ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка Миллионера")

# ------------------- MINESWEEPER -------------------
minesweeper_games = {}

def generate_minesweeper_board(size=5, mines=5):
    board = [[0 for _ in range(size)] for _ in range(size)]
    mine_positions = random.sample([(i, j) for i in range(size) for j in range(size)], mines)
    for x, y in mine_positions:
        board[x][y] = -1
        for dx in [-1,0,1]:
            for dy in [-1,0,1]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < size and 0 <= ny < size and board[nx][ny] != -1:
                    board[nx][ny] += 1
    return board, mine_positions

def render_minesweeper_board(board, revealed):
    size = len(board)
    display = ""
    for i in range(size):
        for j in range(size):
            if (i, j) in revealed:
                if board[i][j] == -1:
                    display += "💣 "
                elif board[i][j] == 0:
                    display += "⬜ "
                else:
                    display += f"{board[i][j]}️⃣ "
            else:
                display += "⬛ "
        display += "\n"
    return display

@bot.inline_handler(lambda q: q.query.lower() == "minesweeper")
def inline_minesweeper(query):
    size = 5
    mines = 5
    board, mine_positions = generate_minesweeper_board(size, mines)
    gid = short_id()
    minesweeper_games[gid] = {"board": board, "revealed": set(), "mine_positions": mine_positions}
    markup = types.InlineKeyboardMarkup()
    for i in range(size):
        row = []
        for j in range(size):
            row.append(types.InlineKeyboardButton("⬛", callback_data=f"minesweeper_{gid}_{i}_{j}"))
        markup.row(*row)
    results = [types.InlineQueryResultArticle(
        id=f"minesweeper_{gid}",
        title="💣 Сапёр",
        description="Откройте клетки, избегая мин!",
        input_message_content=types.InputTextMessageContent(f"💣 Сапёр\n{render_minesweeper_board(board, set())}"),
        reply_markup=markup
    )]
    bot.answer_inline_query(query.id, results, cache_time=1, is_personal=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("minesweeper_"))
def minesweeper_callback(call):
    try:
        _, gid, x, y = call.data.split("_")
        x, y = int(x), int(y)
        game = minesweeper_games.get(gid)
        if not game:
            bot.answer_callback_query(call.id, "Игра завершена!")
            return
        board = game["board"]; revealed = game["revealed"]; mine_positions = game["mine_positions"]
        if (x, y) in mine_positions:
            bot.edit_message_text(f"💥 Вы наткнулись на мину!\n\n{render_minesweeper_board(board, revealed.union(mine_positions))}", inline_message_id=call.inline_message_id)
            minesweeper_games.pop(gid, None)
            return
        revealed.add((x, y))
        if len(revealed) == len(board)*len(board) - len(mine_positions):
            bot.edit_message_text(f"🎉 Вы выиграли!\n\n{render_minesweeper_board(board, revealed.union(mine_positions))}", inline_message_id=call.inline_message_id)
            minesweeper_games.pop(gid, None)
            return
        markup = types.InlineKeyboardMarkup()
        for i in range(len(board)):
            row = []
            for j in range(len(board)):
                if (i, j) in revealed:
                    row.append(types.InlineKeyboardButton("⬜", callback_data="none"))
                else:
                    row.append(types.InlineKeyboardButton("⬛", callback_data=f"minesweeper_{gid}_{i}_{j}"))
            markup.row(*row)
        bot.edit_message_text(f"💣 Сапёр\n{render_minesweeper_board(board, revealed)}", inline_message_id=call.inline_message_id, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print("MINE ERROR:", e)
        bot.answer_callback_query(call.id, "Ошибка сапёра")

# ------------------- Easter / Coin / Slot / Snake handlers (minimal) -------------------
@bot.callback_query_handler(func=lambda c: c.data == "easter_egg")
def easter_inline(call):
    bot.answer_callback_query(call.id, "🐣 Пасхалка!")
    Thread(target=play_inline_easter_egg, args=(call.inline_message_id,)).start()

@bot.callback_query_handler(func=lambda c: c.data.startswith("sysopen_"))
def sys_open(call):
    uid = int(call.data.split("_")[1])

    if uid not in user_sys_settings:
        bot.answer_callback_query(call.id, "Данные не найдены.")
        return

    gui_text = user_sys_settings[uid].get("gui", "Пусто")

    bot.answer_callback_query(call.id)
    bot.send_message(call.from_user.id, f"📌 *GUI окно:*\n{gui_text}", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data == "coin_flip")
def coin_flip(call):
    res = random.choice(["🪙 Орёл","🪙 Решка"])
    bot.edit_message_text(f"Результат: {res}", inline_message_id=call.inline_message_id)
    bot.answer_callback_query(call.id, res)

@bot.callback_query_handler(func=lambda c: c.data == "slot_spin")
def slot_spin(call):
    symbols = ["🍒", "🍋", "🍉", "⭐", "💎", "7️⃣"]
    roll = [random.choice(symbols) for _ in range(3)]
    text = f"| {' | '.join(roll)} |"
    if roll.count("7️⃣") == 3:
        text += "\n🎉 Джекпот!"
    elif len(set(roll)) == 1:
        text += "\n🎉 Три одинаковых!"
    bot.edit_message_text(f"🎰 результат\n {text}\n", inline_message_id=call.inline_message_id,
                          reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🎰 Ещё раз", callback_data="slot_spin")))
    bot.answer_callback_query(call.id, "Крутим 🎲")

# ------------------- small helpers used earlier -------------------
def play_inline_easter_egg(inline_id):
    frames = [
    "8=✊===D 🤨",
    "8==✊==D 🤨",
    "8===✊=D 🤨",
    "8====✊D 🤨",
    "8===✊=D 🤨",
    "8==✊==D 🤨",
    "8=✊===D 🤨",
    "8==✊==D 🥲",
    "8===✊=D 🥲",
    "8====✊D💦 🥲",
    "8===✊=D 🥲",
    "8====✊D💦 ☺️",
    "8===✊=D 😊",
    "8====✊D💦 😊",
    "8=====D ☺️",
    "конец "
    ]
    for frame in frames:
        try:
            bot.edit_message_text(frame, inline_message_id=inline_id)
            time.sleep(0.5)
        except:
            break

@bot.message_handler(func=lambda m: m.from_user.id in system_notify_wait)
def sys_save_value(message):
    uid = message.from_user.id
    field = system_notify_wait.pop(uid)

    if uid not in user_sys_settings:
        user_sys_settings[uid] = {"msg": "", "btn": "", "title": "", "gui": ""}

    user_sys_settings[uid][field] = message.text
    bot.send_message(uid, "✅ Сохранено!")


# ------------------- Flask keepalive -------------------
app = Flask('')
@app.route('/')
def home(): return "✅ если ты это видишь - Бот работает"
def run_flask(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    import requests, time
    url = "https://d249d7e4-7f3e-4dad-9329-793903bd08c3-00-q6aqz7jdva7t.riker.replit.dev/"
    while True:
        try: requests.get(url)
        except: pass
        time.sleep(300)

# ------------------- START -------------------
if __name__ == "__main__":
    start_premium_watcher(bot)  # запустится фоновой нитью
    Thread(target=run_flask).start()
    Thread(target=keep_alive, daemon=True).start()
    print("✅ Бот запущен")
    bot.infinity_polling()
