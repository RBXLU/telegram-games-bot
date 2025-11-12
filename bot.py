import telebot
from telebot import types
import random
import time
import html

TOKEN = "8592750651:AAFuvdC6AIEXzD_WbJrx0p5Bq9wPO23bfwA"  # вставь сюда токен
bot = telebot.TeleBot(TOKEN)

# состояния inline-игр
inline_ttt_games = {}
inline_guess_games = {}

# ---------- крестики-нолики ----------
def ttt_create_board():
    return [" "] * 9

def ttt_render_buttons(board, finished=False):
    markup = types.InlineKeyboardMarkup()
    buttons = []
    for i, cell in enumerate(board):
        symbol = cell if cell != " " else "⬜"
        cb = f"ttt_move_{i}" if not finished and cell == " " else "none"
        buttons.append(types.InlineKeyboardButton(symbol, callback_data=cb))
    for r in range(0, 9, 3):
        markup.row(*buttons[r:r+3])
    if finished:
        markup.add(types.InlineKeyboardButton("🔁 Реванш", callback_data="ttt_rematch"))
    return markup

def ttt_check_win(b, s):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    return any(all(b[i] == s for i in w) for w in wins)

def ttt_board_text(b):
    row = lambda r: " ".join(b[r*3+i] if b[r*3+i] != " " else "⬜" for i in range(3))
    return f"{row(0)}\n{row(1)}\n{row(2)}"

# ---------- inline меню ----------
@bot.inline_handler(lambda q: True)
def inline_handler(query):
    user = query.from_user
    user_name = user.first_name or "Игрок"
    starter_id = user.id
    results = []

    # крестики-нолики
    join_markup = types.InlineKeyboardMarkup()
    join_markup.add(types.InlineKeyboardButton("Присоединиться ⭕", callback_data=f"ttt_join_{starter_id}"))
    ttext = f"🎮 Крестики-нолики\n❌ {html.escape(user_name)}\n⭕ — (ожидается)\n\nНажмите «Присоединиться ⭕», чтобы играть."
    results.append(types.InlineQueryResultArticle(
        id=f"ttt_{int(time.time()*1000)}",
        title="🎮 Крестики-нолики",
        description="Играть с другом (inline)",
        input_message_content=types.InputTextMessageContent(message_text=ttext, parse_mode="HTML"),
        reply_markup=join_markup
    ))

    # орёл-решка
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("Бросить 🪙", callback_data="coin_flip"))
    results.append(types.InlineQueryResultArticle(
        id=f"coin_{int(time.time()*1000)}",
        title="🪙 Орёл и решка",
        description="Подбрось монетку",
        input_message_content=types.InputTextMessageContent(message_text="🪙 Орёл или решка?"),
        reply_markup=m
    ))

    # угадай число
    guess_m = types.InlineKeyboardMarkup()
    row = []
    for i in range(1, 11):
        row.append(types.InlineKeyboardButton(str(i), callback_data=f"guess_inline_{i}"))
        if i % 5 == 0:
            guess_m.row(*row); row=[]
    results.append(types.InlineQueryResultArticle(
        id=f"guess_{int(time.time()*1000)}",
        title="🔢 Угадай число",
        description="От 1 до 10",
        input_message_content=types.InputTextMessageContent(message_text="🔢 Угадай число (1–10)"),
        reply_markup=guess_m
    ))
    bot.answer_inline_query(query.id, results, cache_time=1, is_personal=True)

# ---------- join ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_join_"))
def ttt_join(call):
    iid = call.inline_message_id
    if not iid:
        bot.answer_callback_query(call.id, "Работает только inline.")
        return
    starter_id = int(call.data.split("_")[2])
    if call.from_user.id == starter_id:
        bot.answer_callback_query(call.id, "Ты уже ❌, жди соперника.")
        return
    if iid in inline_ttt_games and inline_ttt_games[iid].get("player_o"):
        bot.answer_callback_query(call.id, "Уже два игрока.")
        return

    game = {
        "board": ttt_create_board(),
        "player_x": starter_id,
        "player_x_name": f"Player_{starter_id}",
        "player_o": call.from_user.id,
        "player_o_name": call.from_user.first_name or "Игрок",
        "turn": "X",
        "scores": {starter_id: 0, call.from_user.id: 0}
    }
    inline_ttt_games[iid] = game
    txt = f"🎮 Крестики-нолики\n❌ {game['player_x_name']} — 0\n⭕ {game['player_o_name']} — 0\n\nХодит: ❌"
    bot.edit_message_text(txt, inline_message_id=iid, reply_markup=ttt_render_buttons(game["board"]))
    bot.answer_callback_query(call.id, "Вы присоединились!")

# ---------- ходы ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_move_"))
def ttt_move(call):
    iid = call.inline_message_id
    if iid not in inline_ttt_games:
        bot.answer_callback_query(call.id, "Игра не найдена.")
        return
    g = inline_ttt_games[iid]
    pos = int(call.data.split("_")[2])
    if g["board"][pos] != " ":
        bot.answer_callback_query(call.id, "Занято.")
        return
    uid = call.from_user.id
    expected = g["player_x"] if g["turn"] == "X" else g["player_o"]
    if uid != expected:
        bot.answer_callback_query(call.id, "Не твой ход.")
        return

    sym = "❌" if g["turn"] == "X" else "⭕"
    g["board"][pos] = sym

    # проверка победы
    if ttt_check_win(g["board"], sym):
        winner_id = g["player_x"] if g["turn"] == "X" else g["player_o"]
        g["scores"][winner_id] += 1
        txt = f"🎉 Победил {sym} ({'❌' if g['turn']=='X' else '⭕'})!\n\n" \
              f"❌ {g['player_x_name']} — {g['scores'][g['player_x']]}\n" \
              f"⭕ {g['player_o_name']} — {g['scores'][g['player_o']]}\n\n" + ttt_board_text(g["board"])
        bot.edit_message_text(txt, inline_message_id=iid, reply_markup=ttt_render_buttons(g["board"], True))
        bot.answer_callback_query(call.id, "Победа!")
        return

    # ничья
    if " " not in g["board"]:
        txt = f"🤝 Ничья!\n\n❌ {g['player_x_name']} — {g['scores'][g['player_x']]}\n" \
              f"⭕ {g['player_o_name']} — {g['scores'][g['player_o']]}\n\n" + ttt_board_text(g["board"])
        bot.edit_message_text(txt, inline_message_id=iid, reply_markup=ttt_render_buttons(g["board"], True))
        bot.answer_callback_query(call.id, "Ничья!")
        return

    # следующий ход
    g["turn"] = "O" if g["turn"] == "X" else "X"
    txt = f"❌ {g['player_x_name']} — {g['scores'][g['player_x']]}\n" \
          f"⭕ {g['player_o_name']} — {g['scores'][g['player_o']]}\n\n" \
          f"Ходит: {'❌' if g['turn']=='X' else '⭕'}\n\n{ttt_board_text(g['board'])}"
    bot.edit_message_text(txt, inline_message_id=iid, reply_markup=ttt_render_buttons(g["board"]))
    bot.answer_callback_query(call.id)

# ---------- реванш ----------
@bot.callback_query_handler(func=lambda c: c.data == "ttt_rematch")
def ttt_rematch(call):
    iid = call.inline_message_id
    if iid not in inline_ttt_games:
        bot.answer_callback_query(call.id, "Игра не найдена.")
        return
    g = inline_ttt_games[iid]
    g["board"] = ttt_create_board()
    g["turn"] = "X"
    txt = f"🔁 Реванш!\n❌ {g['player_x_name']} — {g['scores'][g['player_x']]}\n" \
          f"⭕ {g['player_o_name']} — {g['scores'][g['player_o']]}\n\nХодит: ❌"
    bot.edit_message_text(txt, inline_message_id=iid, reply_markup=ttt_render_buttons(g["board"]))
    bot.answer_callback_query(call.id, "Новая партия!")

# ---------- орёл-решка ----------
@bot.callback_query_handler(func=lambda c: c.data == "coin_flip")
def coin_flip(call):
    iid = call.inline_message_id
    res = random.choice(["🪙 Орёл", "🪙 Решка"])
    try:
        bot.edit_message_text(f"Результат броска: {res}", inline_message_id=iid)
    except: pass
    bot.answer_callback_query(call.id, res)

# ---------- угадай число ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("guess_inline_"))
def guess_inline(call):
    iid = call.inline_message_id
    if iid not in inline_guess_games:
        inline_guess_games[iid] = random.randint(1,10)
    secret = inline_guess_games[iid]
    g = int(call.data.split("_")[2])
    if g == secret:
        bot.edit_message_text(f"🎉 Ты угадал число {secret}!", inline_message_id=iid)
        inline_guess_games.pop(iid, None)
        bot.answer_callback_query(call.id, "Верно!")
    else:
        bot.answer_callback_query(call.id, "❌ Не угадал!")

# ---------- запуск ----------
if __name__ == "__main__":
    print("Bot started")
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "✅ Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
keep_alive()
