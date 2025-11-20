import telebot
from telebot import types
import random
import time
from threading import Thread
from flask import Flask
import html

# -----------------------------
# ВАЖНО: Если токен был скомпрометирован, смените его в BotFather.
# -----------------------------
TOKEN = "8592750651:AAFuvdC6AIEXzD_WbJrx0p5Bq9wPO23bfwA"
bot = telebot.TeleBot(TOKEN)
bot.delete_webhook()

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

millionaire_games = {}   # short_id -> {"question":..., "attempts":int}

# in-memory games
games_flappy = {}   # gid -> {"bird_y":int,"pipes":[(x,gap)],"score":int}
games_2048 = {}     # gid -> {"board": [[int]]}
games_pong = {}     # gid -> {"players":[id_or_None,id_or_None],"paddles":[y1,y2],"ball":[x,y,dx,dy],"started":bool}

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

# ------------------- /start -------------------
@bot.message_handler(commands=["start"])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 Играть")
    bot.send_message(message.chat.id, "🎮 Привет! Выбери игру:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎮 Играть")
def play(message):
    bot.send_message(message.chat.id, "Чтобы играть — используй инлайн через @YourBotUsername в любом чате!")

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
    Thread(target=run_flask).start()
    Thread(target=keep_alive, daemon=True).start()
    print("✅ Бот запущен")
    bot.infinity_polling()
