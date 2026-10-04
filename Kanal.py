import asyncio
import logging
import os
import random
import re
import string
import threading
import uuid
from datetime import datetime
from html import escape
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)
from flask import Flask
from motor.motor_asyncio import AsyncIOMotorClient

# ============================ AYARLAR ============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8628291859:AAGqvsXf46KZAb397R62uKbdi68X6QKsPY0")
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")  # <-- MongoDB
DB_NAME = os.getenv("DB_NAME", "marzban_bot")
RENDER_URL = os.getenv("RENDER_URL", "https://vpn-paylayan-bot-zonex-2z3p.onrender.com")  # <-- Flask / Render URL
PORT = int(os.getenv("PORT", "10000"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ashgabat")
VERIFY_SSL = False  # self-signed sertifika icin False; gercek sertifika varsa True
DEFAULT_LANG = "tr"  # "tr" veya "tk"
FOOTER_MAX = 1000
# =================================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("marzban_bot")

db = AsyncIOMotorClient(MONGO_URI)[DB_NAME]
router = Router()
router.message.filter(F.chat.type == "private")
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

# ============================ DIL (TR / TK) =======================
LANGS = {"tr": "🇹🇷 Türkçe", "tk": "🇹🇲 Türkmençe"}

S = {
    "tr": {
        "menu_title": "Merhaba! Ne yapmak istersin?",
        "b_addp": "🔗 Marzban ekle",
        "b_delp": "🗑 Marzban sil",
        "b_send": "🚀 VPN linki dağıt",
        "b_time": "⏰ Saat ayarla",
        "b_footer": "✏️ Post metni",
        "b_addch": "➕ Kanal ekle",
        "b_chs": "📋 Kanallarım",
        "b_quote_on": "📦 Alıntı: daraltılmış ✅",
        "b_quote_off": "📦 Alıntı: açık",
        "b_lang": "🌐 Dil",
        "b_connect": "🔗 Marzban panel bağla",
        "ask_url": "Panel URL'sini yaz (örnek: http://1.2.3.4:8000)",
        "panel_addr": "Panel adresi: <code>{url}</code>\nKullanıcı adını yaz:",
        "ask_pass": "Parolayı yaz:",
        "ok_panel": "✅ Doğrulama başarılı! Panel eklendi.",
        "fail_panel": "❌ {err}\nTekrar denemek için /menu",
        "no_panel": "❌ Önce Marzban paneli ekle.",
        "no_channels": "❌ Kanal yok. Önce kanal ekle.",
        "sent": "✅ VPN linkleri {ok}/{total} kanala gönderildi.",
        "errs_title": "⚠️ Hatalar:",
        "time_cur": "Şu anki saat: <b>{cur}</b> ({tz})\nHer gün VPN linki konacak saati yaz (örnek: 12:00)\nKapatmak için: <code>kapat</code>",
        "not_set": "ayarlanmadı",
        "time_bad": "Format yanlış. Örnek: 12:00",
        "time_set": "✅ Her gün <b>{t}</b> saatinde VPN linki kanallara konacak.",
        "time_off": "⏰ Otomatik gönderim kapatıldı.",
        "ask_chat": "Kanal @username veya ID yaz (bot o kanalda admin olmalı).\nBotu kanala admin yaparsan otomatik de eklenir.",
        "ch_added": "✅ <b>{title}</b> eklendi.",
        "bot_not_admin": "Bot bu kanalda admin değil.",
        "you_not_admin": "Sen bu kanalın admini değilsin.",
        "ch_none": "Henüz kanal yok.",
        "ch_list": "📋 Kanallar:",
        "admin_done": "✅ Bot <b>{title}</b> kanalında admin yapıldı.",
        "footer_ask": "Alıntının altına konacak metni yaz.\nTelegram'da biçimlendirebilirsin (kalın, italik, link vb.), aynen korunur.\nSilmek için: <code>sil</code>",
        "footer_cur": "\n\nŞu anki metin:\n{cur}",
        "footer_saved": "✅ Metin kaydedildi. Görünüm:",
        "footer_cleared": "✅ Metin silindi.",
        "footer_bad": "❌ Metin geçersiz: {err}",
        "footer_long": "❌ Metin çok uzun (en fazla {n} karakter).",
        "footer_text_only": "Sadece metin gönder.",
        "del_which": "Hangi paneli silmek istiyorsun?",
        "del_none": "Panel yok.",
        "del_done": "🗑 Panel silindi: {url}",
        "quote_on_msg": "📦 Linkler daraltılmış alıntı içinde gidecek.",
        "quote_off_msg": "📦 Linkler açık alıntı içinde gidecek.",
        "lang_pick": "Dil seç:",
        "lang_set": "✅ Dil değiştirildi.",
        "err_login": "Kullanıcı adı veya parola yanlış.",
        "err_unexpected": "Panel beklenen cevabı vermedi (HTTP {status}). URL'yi kontrol et: {url}",
        "err_conn": "Panele bağlanılamadı: {err}",
        "err_inbounds": "Panelden inbound listesi alınamadı.",
        "err_create": "User oluşturulamadı ({status}): {err}",
        "err_nolinks": "Panel VPN linki döndürmedi.",
    },
    "tk": {
        "menu_title": "Salam! Näme etmek isleýärsiň?",
        "b_addp": "🔗 Marzban goş",
        "b_delp": "🗑 Marzban poz",
        "b_send": "🚀 VPN link paýla",
        "b_time": "⏰ Wagt sazla",
        "b_footer": "✏️ Post teksti",
        "b_addch": "➕ Kanal goş",
        "b_chs": "📋 Kanallarym",
        "b_quote_on": "📦 Sitata: ýygnalan ✅",
        "b_quote_off": "📦 Sitata: açyk",
        "b_lang": "🌐 Dil",
        "b_connect": "🔗 Marzban paneli birikdir",
        "ask_url": "Panel URL-ni ýaz (mysal: http://1.2.3.4:8000)",
        "panel_addr": "Panel salgysy: <code>{url}</code>\nUlanyjy adyňy ýaz:",
        "ask_pass": "Paroly ýaz:",
        "ok_panel": "✅ Barlag üstünlikli! Panel goşuldy.",
        "fail_panel": "❌ {err}\nÝene synanyşmak üçin /menu",
        "no_panel": "❌ Ilki Marzban paneli goş.",
        "no_channels": "❌ Kanal ýok. Ilki kanal goş.",
        "sent": "✅ VPN linkler {ok}/{total} kanala iberildi.",
        "errs_title": "⚠️ Näsazlyklar:",
        "time_cur": "Häzirki wagt: <b>{cur}</b> ({tz})\nHer gün VPN link goýuljak wagty ýaz (mysal: 12:00)\nÖçürmek üçin: <code>ýap</code>",
        "not_set": "sazlanmady",
        "time_bad": "Format ýalňyş. Mysal: 12:00",
        "time_set": "✅ Her gün <b>{t}</b> wagtynda VPN link kanallara goýular.",
        "time_off": "⏰ Awtomatik ibermek öçürildi.",
        "ask_chat": "Kanalyň @username ýa-da ID-sini ýaz (bot şol kanalda admin bolmaly).\nBotu kanala admin etseň, awtomatik hem goşular.",
        "ch_added": "✅ <b>{title}</b> goşuldy.",
        "bot_not_admin": "Bot bu kanalda admin däl.",
        "you_not_admin": "Sen bu kanalyň admini däl.",
        "ch_none": "Heniz kanal ýok.",
        "ch_list": "📋 Kanallar:",
        "admin_done": "✅ Bot <b>{title}</b> kanalynda admin edildi.",
        "footer_ask": "Sitatanyň aşagyna goýuljak teksti ýaz.\nTelegramda formatlap bilersiň (galyň, ýapgyt, link we ş.m.), şol bolşy ýaly saklanar.\nÖçürmek üçin: <code>poz</code>",
        "footer_cur": "\n\nHäzirki tekst:\n{cur}",
        "footer_saved": "✅ Tekst saklandy. Görnüşi:",
        "footer_cleared": "✅ Tekst öçürildi.",
        "footer_bad": "❌ Tekst nädogry: {err}",
        "footer_long": "❌ Tekst gaty uzyn (iň köp {n} simwol).",
        "footer_text_only": "Diňe tekst iber.",
        "del_which": "Haýsy paneli pozmaly?",
        "del_none": "Panel ýok.",
        "del_done": "🗑 Panel pozuldy: {url}",
        "quote_on_msg": "📦 Linkler ýygnalan sitatanyň içinde iberiler.",
        "quote_off_msg": "📦 Linkler açyk sitatanyň içinde iberiler.",
        "lang_pick": "Dil saýla:",
        "lang_set": "✅ Dil üýtgedildi.",
        "err_login": "Ulanyjy ady ýa-da parol ýalňyş.",
        "err_unexpected": "Panel garaşylýan jogaby bermedi (HTTP {status}). URL-ni barla: {url}",
        "err_conn": "Panele birikip bolmady: {err}",
        "err_inbounds": "Panelden inbound sanawy alyp bolmady.",
        "err_create": "User döredip bolmady ({status}): {err}",
        "err_nolinks": "Panel VPN link bermedi.",
    },
}


def t(L: str, key: str, **kw) -> str:
    return S.get(L, S[DEFAULT_LANG])[key].format(**kw)


# ------------------------- Flask (Render) ------------------------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot calisiyor"


def run_flask():
    app.run(host="0.0.0.0", port=PORT)


async def keep_alive():
    if "SENIN-APP" in RENDER_URL or not RENDER_URL:
        return
    while True:
        await asyncio.sleep(600)
        try:
            async with aiohttp.ClientSession() as s:
                await s.get(RENDER_URL, timeout=aiohttp.ClientTimeout(total=15))
        except Exception as e:
            log.warning("keep_alive hata: %s", e)


# ----------------------------- DB helpers ------------------------
def new_id() -> str:
    return uuid.uuid4().hex[:8]


async def get_owner(uid: int) -> dict:
    o = await db.owners.find_one({"_id": uid}) or {"_id": uid}
    if o.get("panel") and not o.get("panels"):  # eski tek-panel kaydini tasi
        p = dict(o["panel"])
        p["id"] = new_id()
        p["current_user"] = o.get("current_user")
        await db.owners.update_one(
            {"_id": uid},
            {"$set": {"panels": [p]}, "$unset": {"panel": "", "current_user": ""}},
        )
        o["panels"] = [p]
        o.pop("panel", None)
        o.pop("current_user", None)
    o.setdefault("panels", [])
    return o


async def get_lang(uid: int) -> str:
    o = await db.owners.find_one({"_id": uid}, {"lang": 1})
    return (o or {}).get("lang", DEFAULT_LANG)


# --------------------------- Marzban API -------------------------
class PanelError(Exception):
    def __init__(self, key: str, **kw):
        self.key, self.kw = key, kw
        super().__init__(key)

    def text(self, L: str) -> str:
        return t(L, self.key, **self.kw)


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
        raise PanelError("err_conn", err=escape(str(e)))
    if status in (401, 403):
        raise PanelError("err_login")
    if status != 200 or not data or "access_token" not in data:
        raise PanelError("err_unexpected", status=status, url=escape(panel["url"]))
    return data["access_token"]


def rand_username() -> str:
    return "vpn_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


async def rotate_user(uid: int, panel: dict) -> list[str]:
    """Bu panelde eski useri sil, yeni user kur, VPN linklerini dondur."""
    token = await panel_login(panel)

    old = panel.get("current_user")
    if old:
        await api(panel, "DELETE", f"/api/user/{old}", token)

    status, inbounds = await api(panel, "GET", "/api/inbounds", token)
    if status != 200 or not inbounds:
        raise PanelError("err_inbounds")

    username = rand_username()
    status, data = await api(
        panel,
        "POST",
        "/api/user",
        token,
        json={
            "username": username,
            "proxies": {proto: {} for proto in inbounds},
            "inbounds": {proto: [i["tag"] for i in items] for proto, items in inbounds.items()},
            "expire": 0,
            "data_limit": 0,
            "status": "active",
        },
    )
    if status != 200 or not data:
        raise PanelError("err_create", status=status, err=escape(str(data)[:200]))

    links = data.get("links") or []
    if not links:
        raise PanelError("err_nolinks")

    await db.owners.update_one(
        {"_id": uid, "panels.id": panel["id"]},
        {"$set": {"panels.$.current_user": username}},
    )
    return links


# ------------------------ Post olusturma -------------------------
def build_messages(links: list[str], footer: str, expandable: bool) -> list[str]:
    """Linkler daraltilabilir alintinin icinde, her biri <code> (dokununca kopyalanir).
    Alintinin altina footer metni gelir (son mesajda)."""
    open_tag = "<blockquote expandable>" if expandable else "<blockquote>"
    limit = 3800 - len(footer)
    chunks, cur, size = [], [], 0
    for link in links:
        block = f"<code>{escape(link)}</code>"
        if cur and size + len(block) > limit:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(block)
        size += len(block) + 2
    if cur:
        chunks.append(cur)

    msgs = []
    for i, ch in enumerate(chunks):
        text = f"{open_tag}" + "\n\n".join(ch) + "</blockquote>"
        if footer and i == len(chunks) - 1:
            text += "\n\n" + footer
        msgs.append(text)
    return msgs


async def distribute(bot: Bot, uid: int, notify: bool = True):
    o = await get_owner(uid)
    L = o.get("lang", DEFAULT_LANG)
    if not o["panels"]:
        if notify:
            await bot.send_message(uid, t(L, "no_panel"))
        return
    channels = [c async for c in db.channels.find({"owner_id": uid})]
    if not channels:
        if notify:
            await bot.send_message(uid, t(L, "no_channels"))
        return

    all_links, errs = [], []
    for p in o["panels"]:
        try:
            all_links += await rotate_user(uid, p)
        except PanelError as e:
            errs.append(f"{escape(p['url'])}: {e.text(L)}")
        except Exception as e:
            errs.append(f"{escape(p['url'])}: {escape(str(e))}")

    if not all_links:
        await bot.send_message(uid, "❌ " + "\n".join(errs))
        return

    msgs = build_messages(all_links, o.get("footer", ""), o.get("expandable", True))
    ok, fail = 0, []
    for ch in channels:
        try:
            for m in msgs:
                await bot.send_message(ch["_id"], m, link_preview_options=NO_PREVIEW)
            ok += 1
        except Exception as e:
            fail.append(f"{escape(ch.get('title') or str(ch['_id']))}: {escape(str(e))}")
        await asyncio.sleep(0.5)

    text = t(L, "sent", ok=ok, total=len(channels))
    if errs or fail:
        text += "\n\n" + t(L, "errs_title") + "\n" + "\n".join(errs + fail)
    await bot.send_message(uid, text)


# --------------------------- Zamanlayici -------------------------
async def scheduler(bot: Bot):
    while True:
        try:
            now = datetime.now(ZoneInfo(TIMEZONE))
            hm, today = now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
            q = {"time": {"$lte": hm}, "last_run": {"$ne": today}, "panels.0": {"$exists": True}}
            async for o in db.owners.find(q):
                await db.owners.update_one({"_id": o["_id"]}, {"$set": {"last_run": today}})
                asyncio.create_task(distribute(bot, o["_id"], notify=False))
        except Exception as e:
            log.error("scheduler hata: %s", e)
        await asyncio.sleep(20)


# ------------------------------ UI -------------------------------
def B(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


async def main_kb(uid: int) -> InlineKeyboardMarkup:
    o = await get_owner(uid)
    L = o.get("lang", DEFAULT_LANG)
    exp = o.get("expandable", True)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [B(t(L, "b_addp"), "addp"), B(t(L, "b_delp"), "delp")],
            [B(t(L, "b_send"), "send")],
            [B(t(L, "b_time"), "time"), B(t(L, "b_footer"), "footer")],
            [B(t(L, "b_addch"), "addch"), B(t(L, "b_chs"), "channels")],
            [B(t(L, "b_quote_on" if exp else "b_quote_off"), "quote"), B(t(L, "b_lang"), "lang")],
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


class FooterForm(StatesGroup):
    text = State()


async def show_menu(target: Message, uid: int):
    L = await get_lang(uid)
    await target.answer(t(L, "menu_title"), reply_markup=await main_kb(uid))


@router.message(CommandStart())
@router.message(Command("menu"))
async def start(m: Message, state: FSMContext):
    await state.clear()
    await db.owners.update_one({"_id": m.from_user.id}, {"$setOnInsert": {"expandable": True}}, upsert=True)
    await show_menu(m, m.from_user.id)


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
        L = await get_lang(who)
        try:
            await bot.send_message(
                who,
                t(L, "admin_done", title=escape(event.chat.title or "")),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[B(t(L, "b_connect"), "addp")]]),
            )
        except Exception as e:
            log.warning("Sahibe mesaj gonderilemedi (once /start yazmali): %s", e)
    elif status in ("left", "kicked"):
        await db.channels.delete_one({"_id": event.chat.id})


# ------------------------ Panel ekle -----------------------------
@router.callback_query(F.data == "addp")
async def panel_start(c: CallbackQuery, state: FSMContext):
    L = await get_lang(c.from_user.id)
    await state.set_state(PanelForm.url)
    await c.message.answer(t(L, "ask_url"))
    await c.answer()


@router.message(PanelForm.url)
async def panel_url(m: Message, state: FSMContext):
    L = await get_lang(m.from_user.id)
    url = (m.text or "").strip()
    if not url.startswith("http"):
        url = "http://" + url
    u = urlparse(url)
    url = f"{u.scheme}://{u.netloc}"  # /dashboard/login gibi yollari at
    await state.update_data(url=url)
    await state.set_state(PanelForm.username)
    await m.answer(t(L, "panel_addr", url=escape(url)))


@router.message(PanelForm.username)
async def panel_user(m: Message, state: FSMContext):
    L = await get_lang(m.from_user.id)
    await state.update_data(username=(m.text or "").strip())
    await state.set_state(PanelForm.password)
    await m.answer(t(L, "ask_pass"))


@router.message(PanelForm.password)
async def panel_pass(m: Message, state: FSMContext):
    uid = m.from_user.id
    L = await get_lang(uid)
    data = await state.get_data()
    panel = {
        "id": new_id(),
        "url": data["url"],
        "username": data["username"],
        "password": (m.text or "").strip(),
        "current_user": None,
    }
    try:
        await m.delete()  # parola mesajini sil
    except Exception:
        pass
    await state.clear()
    try:
        await panel_login(panel)
    except PanelError as e:
        await m.answer(t(L, "fail_panel", err=e.text(L)), reply_markup=await main_kb(uid))
        return
    # ayni url+kullanici varsa degistir
    await db.owners.update_one(
        {"_id": uid}, {"$pull": {"panels": {"url": panel["url"], "username": panel["username"]}}}
    )
    await db.owners.update_one({"_id": uid}, {"$push": {"panels": panel}}, upsert=True)
    await m.answer(t(L, "ok_panel"), reply_markup=await main_kb(uid))


# ------------------------ Panel sil ------------------------------
@router.callback_query(F.data == "delp")
async def panel_del_list(c: CallbackQuery):
    o = await get_owner(c.from_user.id)
    L = o.get("lang", DEFAULT_LANG)
    if not o["panels"]:
        await c.message.answer(t(L, "del_none"))
    else:
        rows = [[B(f"🗑 {p['url']} ({p['username']})", f"delp:{p['id']}")] for p in o["panels"]]
        await c.message.answer(t(L, "del_which"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()


@router.callback_query(F.data.startswith("delp:"))
async def panel_del(c: CallbackQuery):
    uid = c.from_user.id
    pid = c.data.split(":", 1)[1]
    o = await get_owner(uid)
    L = o.get("lang", DEFAULT_LANG)
    panel = next((p for p in o["panels"] if p["id"] == pid), None)
    if not panel:
        await c.answer()
        return
    if panel.get("current_user"):  # panelde acik kalan user'i da temizle
        try:
            token = await panel_login(panel)
            await api(panel, "DELETE", f"/api/user/{panel['current_user']}", token)
        except Exception:
            pass
    await db.owners.update_one({"_id": uid}, {"$pull": {"panels": {"id": pid}}})
    await c.message.edit_text(t(L, "del_done", url=escape(panel["url"])))
    await c.answer()


# ------------------------- VPN dagit -----------------------------
@router.callback_query(F.data == "send")
async def send_now(c: CallbackQuery, bot: Bot):
    await c.answer("...")
    await distribute(bot, c.from_user.id)


# ------------------------- Saat ayari ----------------------------
@router.callback_query(F.data == "time")
async def time_start(c: CallbackQuery, state: FSMContext):
    o = await get_owner(c.from_user.id)
    L = o.get("lang", DEFAULT_LANG)
    await state.set_state(TimeForm.time)
    await c.message.answer(t(L, "time_cur", cur=o.get("time") or t(L, "not_set"), tz=TIMEZONE))
    await c.answer()


@router.message(TimeForm.time)
async def time_set(m: Message, state: FSMContext):
    uid = m.from_user.id
    L = await get_lang(uid)
    txt = (m.text or "").strip().lower()
    if txt in ("kapat", "ýap", "yap", "off"):
        await db.owners.update_one({"_id": uid}, {"$unset": {"time": ""}})
        await state.clear()
        await m.answer(t(L, "time_off"), reply_markup=await main_kb(uid))
        return
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", txt):
        await m.answer(t(L, "time_bad"))
        return
    now = datetime.now(ZoneInfo(TIMEZONE))
    upd = {"time": txt}
    if txt <= now.strftime("%H:%M"):
        upd["last_run"] = now.strftime("%Y-%m-%d")  # bugun gecmis saat -> hemen calismasin
    await db.owners.update_one({"_id": uid}, {"$set": upd}, upsert=True)
    await state.clear()
    await m.answer(t(L, "time_set", t=txt), reply_markup=await main_kb(uid))


# ------------------------ Post metni (footer) --------------------
@router.callback_query(F.data == "footer")
async def footer_start(c: CallbackQuery, state: FSMContext):
    o = await get_owner(c.from_user.id)
    L = o.get("lang", DEFAULT_LANG)
    await state.set_state(FooterForm.text)
    text = t(L, "footer_ask")
    if o.get("footer"):
        text += t(L, "footer_cur", cur=o["footer"])
    await c.message.answer(text, link_preview_options=NO_PREVIEW)
    await c.answer()


@router.message(FooterForm.text)
async def footer_set(m: Message, state: FSMContext, bot: Bot):
    uid = m.from_user.id
    L = await get_lang(uid)
    if not m.text:
        await m.answer(t(L, "footer_text_only"))
        return
    if m.text.strip().lower() in ("sil", "poz", "clear"):
        await db.owners.update_one({"_id": uid}, {"$unset": {"footer": ""}})
        await state.clear()
        await m.answer(t(L, "footer_cleared"), reply_markup=await main_kb(uid))
        return
    html = m.html_text  # Telegram'daki biçimlendirme (kalin, italik, link...) HTML olarak korunur
    if len(html) > FOOTER_MAX:
        await m.answer(t(L, "footer_long", n=FOOTER_MAX))
        return
    try:
        await bot.send_message(uid, html, link_preview_options=NO_PREVIEW)  # onizleme + dogrulama
    except TelegramBadRequest as e:
        await m.answer(t(L, "footer_bad", err=escape(str(e))))
        return
    await db.owners.update_one({"_id": uid}, {"$set": {"footer": html}}, upsert=True)
    await state.clear()
    await m.answer(t(L, "footer_saved"), reply_markup=await main_kb(uid))


# --------------------- Alinti acik/kapali ------------------------
@router.callback_query(F.data == "quote")
async def quote_toggle(c: CallbackQuery):
    uid = c.from_user.id
    o = await get_owner(uid)
    L = o.get("lang", DEFAULT_LANG)
    new = not o.get("expandable", True)
    await db.owners.update_one({"_id": uid}, {"$set": {"expandable": new}}, upsert=True)
    await c.message.edit_reply_markup(reply_markup=await main_kb(uid))
    await c.answer(t(L, "quote_on_msg" if new else "quote_off_msg"), show_alert=False)


# ----------------------------- Dil -------------------------------
@router.callback_query(F.data == "lang")
async def lang_pick(c: CallbackQuery):
    L = await get_lang(c.from_user.id)
    rows = [[B(name, f"setlang:{code}")] for code, name in LANGS.items()]
    await c.message.answer(t(L, "lang_pick"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def lang_set(c: CallbackQuery):
    uid = c.from_user.id
    code = c.data.split(":", 1)[1]
    if code not in LANGS:
        await c.answer()
        return
    await db.owners.update_one({"_id": uid}, {"$set": {"lang": code}}, upsert=True)
    await c.message.edit_text(t(code, "lang_set"))
    await show_menu(c.message, uid)
    await c.answer()


# ------------------------ Kanal ekle / liste ---------------------
@router.callback_query(F.data == "addch")
async def addch_start(c: CallbackQuery, state: FSMContext):
    L = await get_lang(c.from_user.id)
    await state.set_state(ChannelForm.chat)
    await c.message.answer(t(L, "ask_chat"))
    await c.answer()


@router.message(ChannelForm.chat)
async def addch_do(m: Message, state: FSMContext, bot: Bot):
    uid = m.from_user.id
    L = await get_lang(uid)
    ref = (m.text or "").strip()
    if ref.lstrip("-").isdigit():
        ref = int(ref)
    try:
        chat = await bot.get_chat(ref)
        me = await bot.get_chat_member(chat.id, bot.id)
        if me.status != "administrator":
            raise ValueError(t(L, "bot_not_admin"))
        you = await bot.get_chat_member(chat.id, uid)
        if you.status not in ("creator", "administrator"):
            raise ValueError(t(L, "you_not_admin"))
    except Exception as e:
        await m.answer(f"❌ {escape(str(e))}")
        return
    await db.channels.update_one(
        {"_id": chat.id}, {"$set": {"title": chat.title, "owner_id": uid}}, upsert=True
    )
    await state.clear()
    await m.answer(t(L, "ch_added", title=escape(chat.title or "")), reply_markup=await main_kb(uid))


@router.callback_query(F.data == "channels")
async def list_channels(c: CallbackQuery):
    L = await get_lang(c.from_user.id)
    items = [x async for x in db.channels.find({"owner_id": c.from_user.id})]
    if not items:
        await c.message.answer(t(L, "ch_none"))
    else:
        await c.message.answer(
            t(L, "ch_list") + "\n" + "\n".join(f"• {escape(x.get('title') or str(x['_id']))}" for x in items)
        )
    await c.answer()


# ------------------------------ main -----------------------------
async def migrate_old_panels():
    async for o in db.owners.find({"panel": {"$exists": True}}):
        await get_owner(o["_id"])


async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await migrate_old_panels()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    asyncio.create_task(scheduler(bot))
    asyncio.create_task(keep_alive())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
