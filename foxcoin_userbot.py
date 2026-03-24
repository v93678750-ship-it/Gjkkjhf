"""
FOX Coin Userbot — финальный правильный флоу:

1. Пользователь пишет реплаем на Иру: "Перевод 100" или "Перевод вб"
2. FOX Coin спрашивает у ПОЛЬЗОВАТЕЛЯ подтверждение → пользователь жмёт Да сам
3. FOX бот пишет в ЛС Иры о входящем переводе
4. Розыгрыш:
   - Выиграл → бот пишет реплаем пользователю: "Перевод <сумма> вб"
             → FOX Coin спрашивает у ИРЫ подтверждение → БОТ жмёт Да
             → деньги у пользователя
   - Проиграл → бот пишет реплаем: "😢 Попробуй в следующий раз"

Установка: pip install telethon
Запуск:    python foxcoin_userbot.py
"""

from telethon import TelegramClient, events
from aiohttp import web
import random
import json
import os
import asyncio
import re

# ─── НАСТРОЙКИ ───────────────────────────────────────────────────────────────
API_ID    = 22883217
API_HASH  = "2e90015ceac9c7f35b79860ce38b48c1"
SESSION   = "ira_fox"
ADMIN_ID  = 8543349402

FOX_BOT_USERNAME = "foxcoingame_bot"

DEFAULT_WIN_CHANCE = 30

MULTIPLIERS = [2,  3,  5,  10, 15, 20, 50, 100]
WEIGHTS     = [30, 25, 18, 10,  7,  5,  3,   2]

DATA_FILE = "foxcoin_data.json"
# ─────────────────────────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"win_chance": DEFAULT_WIN_CHANCE}

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def fmt(num):
    num = float(num)
    if num == int(num):
        return str(int(num))
    return f"{num:.2f}".rstrip("0").rstrip(".")

client = TelegramClient(SESSION, API_ID, API_HASH)
data = load_data()

# username -> {"chat_id", "reply_id", "from_name"}
# Сохраняем когда пользователь написал "Перевод ..."
user_context = {}

# True когда бот написал "Перевод вб" и ждёт подтверждения от FOX
# чтобы нажать Да именно на ЭТОТ запрос, а не на чужой
waiting_our_confirm = False


# ═══════════════════════════════════════════════════════════════
#  ШАГ 1: Пользователь пишет "Перевод <сумма>" реплаем на Иру
# ═══════════════════════════════════════════════════════════════

@client.on(events.NewMessage())
async def watch_perervod(event):
    if event.is_private:
        return

    text = (event.raw_text or "").strip()

    # Команда перевода (любой регистр, с суммой или "вб")
    if not re.match(r"(?i)^перевод\s+(\d[\d\s.,]*|вб)$", text):
        return

    # Должен быть реплай на наш аккаунт @FO_X100
    if not event.is_reply:
        return

    reply_msg = await event.get_reply_message()
    if reply_msg is None:
        return

    me = await client.get_me()
    if reply_msg.sender_id != me.id:
        return

    sender = await event.get_sender()
    if sender is None:
        return

    # Игнорируем сообщения от самого себя
    if sender.id == me.id:
        return

    username = (sender.username or str(sender.id)).lower()
    from_name = sender.first_name or f"@{username}"

    user_context[username] = {
        "chat_id": event.chat_id,
        "reply_id": event.id,
        "from_name": from_name
    }
    print(f"[CTX] ✅ @{username} ({from_name}) написал Перевод в чате {event.chat_id}")


# ═══════════════════════════════════════════════════════════════
#  ШАГ 3: FOX бот сообщает о входящем переводе → розыгрыш
# ═══════════════════════════════════════════════════════════════

@client.on(events.NewMessage(from_users=FOX_BOT_USERNAME))
async def fox_listener(event):
    global waiting_our_confirm
    text = event.raw_text or ""
    print(f"[FOX BOT] {repr(text[:200])}")

    # ── Входящий перевод ──────────────────────────────────────
    is_incoming = (
        "входящий перевод" in text.lower()
        or ("✅" in text and "сумма" in text.lower() and "отправитель" in text.lower())
    )

    if is_incoming:
        amount_match = re.search(
            r"сумма[:\s]+([0-9][0-9\s\u00a0\xa0.,]*)\s*FC",
            text, re.IGNORECASE
        )
        sender_match = re.search(
            r"отправитель[:\s]+@?([A-Za-z0-9_]+)",
            text, re.IGNORECASE
        )

        if not amount_match or not sender_match:
            print(f"[FOX BOT] ⚠️ Не распарсил:\n{text}")
            return

        raw = re.sub(r"[\s\u00a0\xa0]", "", amount_match.group(1)).replace(",", ".")
        try:
            amount = float(raw)
        except ValueError:
            print(f"[FOX BOT] ⚠️ Ошибка суммы: {raw}")
            return

        username = sender_match.group(1).lower()
        print(f"[FOX BOT] 💰 {amount} FC от @{username}")

        await asyncio.sleep(1)

        ctx = user_context.get(username)
        win = random.randint(1, 100) <= data["win_chance"]

        if win:
            multiplier = random.choices(MULTIPLIERS, weights=WEIGHTS, k=1)[0]
            win_amount = round(amount * multiplier, 2)
            print(f"[GAME] 🎉 @{username} x{multiplier} = {win_amount} FC")

            if ctx:
                # Ставим флаг — следующее подтверждение от FOX это наше
                waiting_our_confirm = True

                # Пишем реплаем пользователю команду перевода
                await client.send_message(
                    ctx["chat_id"],
                    f"Перевод {fmt(win_amount)}",
                    reply_to=ctx["reply_id"]
                )

                user_context.pop(username, None)
            else:
                print(f"[GAME] ⚠️ Нет контекста для @{username}")
                await client.send_message(
                    ADMIN_ID,
                    f"⚠️ Нет контекста!\n"
                    f"@{username} выиграл x{multiplier} = {fmt(win_amount)} FC\n"
                    f"Нужен ручной перевод!"
                )
        else:
            print(f"[GAME] 😢 @{username} проиграл")

            if ctx:
                await client.send_message(
                    ctx["chat_id"],
                    f"😢 Попробуй в следующий раз",
                    reply_to=ctx["reply_id"]
                )
                user_context.pop(username, None)
            else:
                print(f"[GAME] ⚠️ Нет контекста для @{username}")

        return

    # ── FOX бот в ЛС спрашивает подтверждение нашего перевода ─
    if "подтвердить перевод" in text.lower() and event.message.reply_markup:
        if waiting_our_confirm:
            print(f"[FOX BOT ЛС] Подтверждение нашего перевода — жму Да")
            await asyncio.sleep(0.3)
            success = await click_yes(event.message)
            if success:
                waiting_our_confirm = False


# ═══════════════════════════════════════════════════════════════
#  ШАГ 4: FOX Coin в ГРУППЕ спрашивает подтверждение нашего перевода
# ═══════════════════════════════════════════════════════════════

@client.on(events.NewMessage())
async def watch_group_confirm(event):
    global waiting_our_confirm

    if event.is_private:
        return
    if not event.message.reply_markup:
        return

    text = event.raw_text or ""
    if "подтвердить перевод" not in text.lower():
        return

    # Это подтверждение для нашего аккаунта (Иры)?
    me = await client.get_me()
    my_first = (me.first_name or "").lower()
    my_user  = (me.username or "").lower()

    if my_first not in text.lower() and my_user not in text.lower():
        return  # это подтверждение для кого-то другого — не трогаем

    # Это наш перевод победителю?
    if not waiting_our_confirm:
        return  # не трогаем — это пользователь сам подтверждает свой перевод нам

    print(f"[GROUP] Подтверждение нашего перевода победителю — жму Да")
    await asyncio.sleep(0.3)
    success = await click_yes(event.message)
    if success:
        waiting_our_confirm = False


async def click_yes(message):
    """Нажать строго кнопку Да"""
    try:
        if not message.reply_markup:
            return False
        for row in message.reply_markup.rows:
            for button in row.buttons:
                btn_text = getattr(button, "text", "").strip()
                if btn_text.lower() in ["да", "yes", "✅ да", "✅"]:
                    await message.click(text=btn_text)
                    print(f"[CLICK] ✅ Нажата '{btn_text}'")
                    return True
        print(f"[CLICK] ⚠️ Кнопка Да не найдена")
        return False
    except Exception as e:
        print(f"[CLICK] ❌ {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  КОМАНДЫ АДМИНИСТРАТОРА
# ═══════════════════════════════════════════════════════════════

@client.on(events.NewMessage(pattern=r"(?i)\+шанс\s+(\d+)"))
async def cmd_chance(event):
    sender = await event.get_sender()
    if sender is None or sender.id != ADMIN_ID:
        return
    chance = int(event.pattern_match.group(1))
    if not (1 <= chance <= 99):
        await event.reply("❌ Шанс от 1 до 99.")
        return
    data["win_chance"] = chance
    save_data(data)
    await event.reply(f"✅ Шанс победы: **{chance}%**")


@client.on(events.NewMessage(pattern=r"(?i)\+статус"))
async def cmd_status(event):
    sender = await event.get_sender()
    if sender is None or sender.id != ADMIN_ID:
        return
    await event.reply(
        f"⚙️ **Статус:**\n"
        f"🎲 Шанс победы: **{data['win_chance']}%**\n"
        f"👥 Ждут розыгрыша: {len(user_context)}\n"
        f"⏳ Ждём подтверждения: {'Да' if waiting_our_confirm else 'Нет'}"
    )


# ═══════════════════════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
#  ВЕБ-СЕРВЕР — чтобы Render не усыплял
# ═══════════════════════════════════════════════════════════════

async def handle(request):
    return web.Response(text="🦊 FOX Coin Userbot работает!")

async def start_web():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Веб-сервер запущен на порту {port}")


# ═══════════════════════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════════════════════

async def main():
    print("=" * 50)
    print("🦊 FOX Coin Userbot — финальная версия")
    print("=" * 50)

    # Запускаем веб-сервер (для Render)
    await start_web()

    await client.start()
    me = await client.get_me()
    print(f"✅ Аккаунт: {me.first_name} (@{me.username})")
    print(f"🎲 Шанс победы: {data['win_chance']}%")
    print("=" * 50)
    print("Бот запущен! Жду переводов...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
