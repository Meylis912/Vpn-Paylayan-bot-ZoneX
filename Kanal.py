import asyncio
import logging
import os
import random
import re
import string
import threading
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from flask import Flask
from motor.motor_asyncio import AsyncIOMotorClient

# ============================ AYARLAR ============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8628291859:AAGqvsXf46KZAb397R62uKbdi68X6QKsPY0")
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")  # <-- MongoDB
DB_NAME = os.getenv("DB_NAME", "marzban_bot")
RENDER_URL = os.getenv("RENDER_URL", "https://SENIN-APP.onrender.com")  # <-- Flask / Render URL
PORT = int(os.getenv("PORT", "10000"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ashgabat")  # saat ayari bu saat dilimine gore
VERIFY_SSL = False  # Marzban self-signed sertifika kullaniyorsa False; gercek sertifika varsa True yap
# =================================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("marzban_bot")

db = AsyncIOMotorClient(MONGO_URI)[DB_NAME]
router = Router()
router.message.filter(F.chat.type == "private")

# ------------------------- Flask (Render) ------------------------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot calisiyor"


def run_flask():
    app.run(host="0.0.0.0", port=PORT)


async def keep_alive():
    """Render'in uyumasini engellemek icin 10 dakikada bir kendi URL'ine istek atar."""
    if "SENIN-APP" in RENDER_URL:
        return
    while True:
        await asyncio.sleep(600)
        try:
            async with aiohttp.ClientSession() as s:
                await s.get(RENDER_URL, timeout=aiohttp.ClientTimeout(total=15))
        except Exception as e:
            log.warning("keep_alive hata: %s", e)


# --------------------------- Marzban API -------------------------
class PanelError(Exception):
    pass


async def api(panel: dict, method: str, path: str, token: str | None = None, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    connector = aiohttp.TCPConnector(ssl=VERIFY_SSL)
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30), connector=connector
    ) as s:
        async with s.request(method, panel["url"] + path, headers=headers, **kw) as r:
            try:
                data = await r.json(content_type=None)
            except Exception:
                data = None
            return r.status, data


async def panel_login(panel: dict) -> str:
    try:
        status, data = await api(
            panel,
            "POST",
            "/api/admin/token",
            data={"username": panel["username"], "password": panel["password"]},
        )
    except Exception as e:
        raise PanelError(f"Panele baglanilamadi: {e}")
    if status != 200 or not data or "access_token" not in data:
        raise PanelError("URL, kullanici adi veya parola yanlis.")
    return data["access_token"]


def rand_username() -> str:
    return "vpn_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


async def rotate_user(owner: dict) -> list[str]:
    """Eski useri sil, yeni user kur, VPN linklerini dondur."""
    panel = owner["panel"]
    token = await panel_login(panel)

    old = owner.get("current_user")
    if old:
        await api(panel, "DELETE", f"/api/user/{old}", token)

    status, inbounds = await api(panel, "GET", "/api/inbounds", token)
    if status != 200 or not inbounds:
        raise PanelError("Panelden inbound listesi alinamadi.")

    payload_proxies = {proto: {} for proto in inbounds}
    payload_inbounds = {proto: [i["tag"] for i in items] for proto, items in inbounds.items()}

    username = rand_username()
    status, data = await api(
        panel,
        "POST",
        "/api/user",
        token,
        json={
            "username": username,
            "proxies": payload_proxies,
            "inbounds": payload_inbounds,
            "expire": 0,
            "data_limit": 0,
            "status": "active",
        },
    )
    if status != 200 or not data:
        raise PanelError(f"User olusturulamadi ({status}): {data}")

    links = data.get("links") or []
    if not links:
        raise PanelError("Panel VPN linki dondurmedi.")

    await db.owners.update_one({"_id": owner["_id"]}, {"$set": {"current_user": username}})
    return links


def build_messages(links: list[str]) -> list[str]:
    """<code> icinde -> dokununca kopyalanir. 4096 limitine gore parcalar."""
    head = "🔐 <b>VPN linkleri</b>\n<i>Dokunup kopyalayin</i>\n\n"
    msgs, cur = [], head
    for link in links:
        block = f"<code>{escape(link)}</code>\n\n"
        if len(cur) + len(block) > 3900:
            msgs.append(cur)
            cur = ""
        cur += block
    msgs.append(cur)
    return msgs


async def distribute(bot: Bot, owner_id: int, notify: bool = True):
    owner = await db.owners.find_one({"_id": owner_id})
    if not owner or "panel" not in owner:
        if notify:
            await bot.send_message(owner_id, "❌ Once Marzban panelini bagla.")
        return
    channels = [c async for c in db.channels.find({"owner_id": owner_id})]
    if not channels:
        if notify:
            await bot.send_message(owner_id, "❌ Kanal yok. Once kanal ekle.")
        return
    try:
        links = await rotate_user(owner)
    except PanelError as e:
        await bot.send_message(owner_id, f"❌ {escape(str(e))}")
        return

    msgs = build_messages(links)
    ok, fail = 0, []
    for ch in channels:
        try:
            for m in msgs:
                await bot.send_message(ch["_id"], m)
            ok += 1
        except Exception as e:
            fail.append(f"{ch.get('title', ch['_id'])}: {e}")
        await asyncio.sleep(0.5)

    text = f"✅ VPN linkleri {ok}/{len(channels)} kanala gonderildi."
    if fail:
        text += "\n\n⚠️ Hatalar:\n" + "\n".join(escape(f) for f in fail)
    await bot.send_message(owner_id, text)


# --------------------------- Zamanlayici -------------------------
async def scheduler(bot: Bot):
    while True:
        try:
            now = datetime.now(ZoneInfo(TIMEZONE))
            hm, today = now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
            q = {"time": {"$lte": hm}, "last_run": {"$ne": today}, "panel": {"$exists": True}}
            async for o in db.owners.find(q):
                await db.owners.update_one({"_id": o["_id"]}, {"$set": {"last_run": today}})
                asyncio.create_task(distribute(bot, o["_id"], notify=False))
        except Exception as e:
            log.error("scheduler hata: %s", e)
        await asyncio.sleep(20)


# ------------------------------ UI -------------------------------
def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Marzban panel bağla", callback_data="panel")],
            [InlineKeyboardButton(text="🚀 VPN linki dağıt", callback_data="send")],
            [InlineKeyboardButton(text="⏰ Saat ayarla", callback_data="time")],
            [
                InlineKeyboardButton(text="➕ Kanal ekle", callback_data="addch"),
                InlineKeyboardButton(text="📋 Kanallarım", callback_data="channels"),
            ],
        ]
    )


class PanelForm(StatesGroup):
    url = State()
    username = State()
    password = State()


class TimeForm(StatesGroup):
    time = State()


class ChannelForm(StatesGroup):
    chat = State()


@router.message(CommandStart())
@router.message(Command("menu"))
async def start(m: Message, state: FSMContext):
    await state.clear()
    await db.owners.update_one({"_id": m.from_user.id}, {"$setOnInsert": {}}, upsert=True)
    await m.answer("Merhaba! Ne yapmak istersin?", reply_markup=main_kb())


# --------------- Bot kanala admin yapildiginda ------------------
@router.my_chat_member()
async def on_admin_change(event: ChatMemberUpdated, bot: Bot):
    if event.chat.type != "channel":
        return
    status = event.new_chat_member.status
    if status == "administrator":
        who = event.from_user.id
        await db.channels.update_one(
            {"_id": event.chat.id},
            {"$set": {"title": event.chat.title, "owner_id": who}},
            upsert=True,
        )
        try:
            await bot.send_message(
                who,
                f"✅ Bot <b>{escape(event.chat.title or '')}</b> kanalında admin yapıldı.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔗 Marzban panel bağla", callback_data="panel")]
                    ]
                ),
            )
        except Exception as e:
            log.warning("Sahibe mesaj gonderilemedi (once /start yazmali): %s", e)
    elif status in ("left", "kicked"):
        await db.channels.delete_one({"_id": event.chat.id})


# ------------------------ Panel baglama --------------------------
@router.callback_query(F.data == "panel")
async def panel_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(PanelForm.url)
    await c.message.answer("Panel URL'sini yaz (ornek: https://panel.site.com:8000)")
    await c.answer()


@router.message(PanelForm.url)
async def panel_url(m: Message, state: FSMContext):
    url = (m.text or "").strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    await state.update_data(url=url)
    await state.set_state(PanelForm.username)
    await m.answer("Kullanici adini yaz:")


@router.message(PanelForm.username)
async def panel_user(m: Message, state: FSMContext):
    await state.update_data(username=(m.text or "").strip())
    await state.set_state(PanelForm.password)
    await m.answer("Parolayi yaz:")


@router.message(PanelForm.password)
async def panel_pass(m: Message, state: FSMContext):
    data = await state.get_data()
    panel = {"url": data["url"], "username": data["username"], "password": (m.text or "").strip()}
    try:
        await m.delete()  # parola mesajini sohbetten sil
    except Exception:
        pass
    try:
        await panel_login(panel)
    except PanelError as e:
        await state.clear()
        await m.answer(f"❌ {escape(str(e))}\nTekrar denemek icin /menu", reply_markup=main_kb())
        return
    await db.owners.update_one(
        {"_id": m.from_user.id}, {"$set": {"panel": panel}}, upsert=True
    )
    await state.clear()
    await m.answer("✅ Doğrulama başarılı!", reply_markup=main_kb())


# ------------------------- VPN dagit -----------------------------
@router.callback_query(F.data == "send")
async def send_now(c: CallbackQuery, bot: Bot):
    await c.answer("Hazirlaniyor...")
    await distribute(bot, c.from_user.id)


# ------------------------- Saat ayari ----------------------------
@router.callback_query(F.data == "time")
async def time_start(c: CallbackQuery, state: FSMContext):
    owner = await db.owners.find_one({"_id": c.from_user.id}) or {}
    cur = owner.get("time", "ayarlanmadi")
    await state.set_state(TimeForm.time)
    await c.message.answer(
        f"Su anki saat: <b>{cur}</b> ({TIMEZONE})\n"
        "Her gun VPN linki konacak saati yaz (ornek: 12:00)\n"
        "Kapatmak icin: <code>kapat</code>"
    )
    await c.answer()


@router.message(TimeForm.time)
async def time_set(m: Message, state: FSMContext):
    txt = (m.text or "").strip().lower()
    if txt == "kapat":
        await db.owners.update_one({"_id": m.from_user.id}, {"$unset": {"time": ""}})
        await state.clear()
        await m.answer("⏰ Otomatik gonderim kapatildi.", reply_markup=main_kb())
        return
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", txt):
        await m.answer("Format yanlis. Ornek: 12:00")
        return
    now = datetime.now(ZoneInfo(TIMEZONE))
    upd = {"time": txt}
    if txt <= now.strftime("%H:%M"):
        upd["last_run"] = now.strftime("%Y-%m-%d")  # bugun gecmis saat -> hemen calismasin
    await db.owners.update_one({"_id": m.from_user.id}, {"$set": upd}, upsert=True)
    await state.clear()
    await m.answer(f"✅ Her gun <b>{txt}</b> saatinde VPN linki kanallara konacak.", reply_markup=main_kb())


# ------------------------ Kanal ekle / liste ---------------------
@router.callback_query(F.data == "addch")
async def addch_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(ChannelForm.chat)
    await c.message.answer(
        "Kanal @username veya ID yaz (bot o kanalda admin olmali).\n"
        "Botu kanala admin yaparsan otomatik de eklenir."
    )
    await c.answer()


@router.message(ChannelForm.chat)
async def addch_do(m: Message, state: FSMContext, bot: Bot):
    ref = (m.text or "").strip()
    if ref.lstrip("-").isdigit():
        ref = int(ref)
    try:
        chat = await bot.get_chat(ref)
        me = await bot.get_chat_member(chat.id, bot.id)
        if me.status != "administrator":
            raise ValueError("Bot bu kanalda admin degil.")
        you = await bot.get_chat_member(chat.id, m.from_user.id)
        if you.status not in ("creator", "administrator"):
            raise ValueError("Sen bu kanalin admini degilsin.")
    except Exception as e:
        await m.answer(f"❌ {escape(str(e))}")
        return
    await db.channels.update_one(
        {"_id": chat.id},
        {"$set": {"title": chat.title, "owner_id": m.from_user.id}},
        upsert=True,
    )
    await state.clear()
    await m.answer(f"✅ <b>{escape(chat.title or '')}</b> eklendi.", reply_markup=main_kb())


@router.callback_query(F.data == "channels")
async def list_channels(c: CallbackQuery):
    items = [x async for x in db.channels.find({"owner_id": c.from_user.id})]
    if not items:
        await c.message.answer("Henuz kanal yok.")
    else:
        await c.message.answer("📋 Kanallar:\n" + "\n".join(f"• {escape(x.get('title') or str(x['_id']))}" for x in items))
    await c.answer()


# ------------------------------ main -----------------------------
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    asyncio.create_task(scheduler(bot))
    asyncio.create_task(keep_alive())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
