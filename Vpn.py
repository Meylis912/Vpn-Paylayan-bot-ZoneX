import os
import time
import asyncio
import threading
import requests
from flask import Flask
from pymongo import MongoClient
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.helpers import escape_markdown

# =========================
# 🌐 FLASK SERVER (Keep Alive)
# =========================
app_flask = Flask(__name__)

RENDER_URL = os.getenv(
    "RENDER_URL",
    "https://vpn-bot-z9rj.onrender.com"
)

@app_flask.route("/")
def home():
    return "Bot is Alive!", 200

def keep_alive():
    time.sleep(15)
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
        except Exception:
            pass
        time.sleep(300)

# =========================
# 🔐 CONFIG
# =========================
BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "7846603711:AAHGCm_uX7NmzHPFcRigI6ERNtCa91SXxZY"
)

KURUCU_ID = int(
    os.getenv(
        "KURUCU_ID",
        "7523674506"
    )
)

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1"
)

# =========================
# 🍃 MONGO
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["vpn_bot"]

admins = db["admins"]
channels = db["channels"]
settings = db["settings"]

try:
    channels.create_index("channel_id", unique=True)
except:
    pass

# =========================
# 👮 YGTYÝARLYK BARLAGLARY
# =========================
def is_kurucu(user_id):
    return int(user_id) == KURUCU_ID

def is_admin(user_id):
    if is_kurucu(user_id):
        return True
    return admins.find_one({"user_id": int(user_id)}) is not None

# Adminiň paýlaşan sanyny artdyrmak
def increment_admin_counter(user_id):
    if is_kurucu(user_id):
        admins.update_one(
            {"user_id": KURUCU_ID},
            {"$inc": {"sent_count": 1}, "$set": {"is_kurucu": True}},
            upsert=True
        )
    else:
        admins.update_one(
            {"user_id": int(user_id)},
            {"$inc": {"sent_count": 1}},
            upsert=True
        )

# Iň soňky paýlaşylan maglumat
def get_last_share_text():
    data = settings.find_one({"key": "last_share"})
    if not data:
        return "ℹ️ Entek hiç hili VPN paýlaşylmady."

    sender = data.get("sender_id")
    share_time_ts = data.get("timestamp")
    diff_seconds = int(time.time() - share_time_ts)

    if diff_seconds < 60:
        wagt_text = "ýaňyja"
    elif diff_seconds < 3600:
        wagt_text = f"{diff_seconds // 60} minut öň"
    elif diff_seconds < 86400:
        wagt_text = f"{diff_seconds // 3600} sagat öň"
    else:
        wagt_text = f"{diff_seconds // 86400} gün öň"

    return f"👤 **Iň soňky paýlaşan:** `{sender}`\n⏱️ **Wagty:** {wagt_text}"

# =========================
# 🚀 START COMMAND
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text("⛔ Size rugsat berilmedi!")
        return

    # Ähli ulanyjylara (Admin we Kurucu) görünjek düwmeler
    keyboard = [
        [InlineKeyboardButton("🔗 VPN Paýlaş", callback_data="vpn")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ]

    # Diňe Kurucu üçin görünjek ýörite düwmeler
    if is_kurucu(uid):
        keyboard.insert(1, [InlineKeyboardButton("📣 Reklama Paýlaş", callback_data="reklama")])
        keyboard.insert(2, [InlineKeyboardButton("➕ Kanal Goş", callback_data="add")])
        keyboard.insert(3, [InlineKeyboardButton("🗑️ Kanallary Dolandyr", callback_data="manage_channels")])
        keyboard.insert(4, [InlineKeyboardButton("👮 Adminleri Dolandyr", callback_data="manage_admins")])

    last_share_info = get_last_share_text()

    await update.message.reply_text(
        f"🤖 **VPN BOT PANELI**\n\n"
        f"{last_share_info}\n\n"
        f"Lütfen amaly saýlaň:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# =========================
# 💬 TEXT / MEDIA HANDLER
# =========================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    state = context.user_data.get("state")
    text = update.message.text.strip() if update.message.text else ""

    # -------------------------
    # ➕ KANAL GOŞ (Diňe Kurucu)
    # -------------------------
    if state == "ADD_ID" and is_kurucu(uid):
        is_valid_id = False
        if text.startswith("-") and text[1:].isdigit():
            is_valid_id = True
        elif text.isdigit():
            is_valid_id = True

        if not is_valid_id:
            await update.message.reply_text("❌ Dogry Kanal ID ugradyň:\n\nMeselem: `-1003262094319`")
            return

        context.user_data["temp_channel_id"] = text
        context.user_data["state"] = "ADD_LINK"
        await update.message.reply_text("🔗 Kanal linkini ugradyň:\n\nMeselem: `https://t.me/...`")

    elif state == "ADD_LINK" and is_kurucu(uid):
        if not (text.startswith("http://") or text.startswith("https://") or text.startswith("t.me/")):
            await update.message.reply_text("❌ Dogry kanal linkini ugradyň!")
            return

        channel_id_str = context.user_data.get("temp_channel_id")
        existing = channels.find_one({"$or": [{"channel_id": channel_id_str}, {"_id": channel_id_str}]})

        if existing:
            await update.message.reply_text("⚠️ Bu kanal öň goşulan!")
            context.user_data.clear()
            return

        channels.insert_one({"channel_id": channel_id_str, "link": text, "added_at": time.time()})
        await update.message.reply_text("✅ Kanal üstünlikli goşuldy!")
        context.user_data.clear()

    # -------------------------
    # 👮 ADMIN GOŞ (Diňe Kurucu)
    # -------------------------
    elif state == "ADD_ADMIN" and is_kurucu(uid):
        if not text.isdigit():
            await update.message.reply_text("❌ Diňe san görnüşinde ID ugradyň!")
            return

        target_id = int(text)
        admins.update_one({"user_id": target_id}, {"$setOnInsert": {"sent_count": 0}}, upsert=True)
        await update.message.reply_text(f"✅ `{target_id}` admin boldy!")
        context.user_data.clear()

    # -------------------------
    # 🔗 VPN PAÝLAŞMAK (Adminler we Kurucu)
    # -------------------------
    elif state == "VPN":
        context.user_data["vpn"] = text
        context.user_data["state"] = "DESC"
        await update.message.reply_text("📝 Düşündiriş ugradyň:")

    elif state == "DESC":
        context.user_data["desc"] = text
        asyncio.create_task(awto_goyber_prosesi(update, context, uid))

    # -------------------------
    # 📣 REKLAMA PAÝLAŞMAK (🛡️ DIŇE KURUCU)
    # -------------------------
    elif state == "REKLAMA_MEDIA":
        if not is_kurucu(uid):
            context.user_data.clear()
            return

        if update.message.photo:
            context.user_data["rec_type"] = "photo"
            context.user_data["rec_file_id"] = update.message.photo[-1].file_id
            context.user_data["rec_caption"] = update.message.caption or ""
        elif update.message.video:
            context.user_data["rec_type"] = "video"
            context.user_data["rec_file_id"] = update.message.video.file_id
            context.user_data["rec_caption"] = update.message.caption or ""
        elif update.message.text:
            context.user_data["rec_type"] = "text"
            context.user_data["rec_text"] = text
        else:
            await update.message.reply_text("❌ Lütfen diňe Surat, Wideo ýa-da Tekst ugradyň!")
            return

        context.user_data["state"] = "REKLAMA_BUTTON"
        await update.message.reply_text(
            "🔘 Reklama düwmesini goşmak isleseňiz, aşakdaky formatda ugradyň:\n\n"
            "`Düwme Ady | https://t.me/link`\n\n"
            "Düwme goşmak islemeýän bolsaňiz **Bök** diýip ýazyň.",
            parse_mode="Markdown"
        )

    elif state == "REKLAMA_BUTTON":
        if not is_kurucu(uid):
            context.user_data.clear()
            return

        if text.lower() != "bök":
            if "|" not in text:
                await update.message.reply_text("❌ Format nädogry! Dogry format:\n`Düwme Ady | https://link.com`")
                return
            
            b_name, b_url = text.split("|", 1)
            context.user_data["btn_name"] = b_name.strip()
            context.user_data["btn_url"] = b_url.strip()
        
        asyncio.create_task(reklama_goyber_prosesi(update, context))

# =========================
# 🚀 VPN GOÝBERME PROSESI (Kopyalanabilir)
# =========================
async def awto_goyber_prosesi(update: Update, context: ContextTypes.DEFAULT_TYPE, sender_id: int):
    vpn = context.user_data.get("vpn")
    desc = context.user_data.get("desc")
    context.user_data.clear()

    status_msg = await update.message.reply_text("⏳ VPN ähli kanallara ugradylýar...")
    all_channels = list(channels.find({}))

    if not all_channels:
        await status_msg.edit_text("❌ Kanal ýok!")
        return

    settings.update_one({"key": "last_share"}, {"$set": {"sender_id": sender_id, "timestamp": time.time()}}, upsert=True)

    ok_channels = []
    fail_channels = []

    escaped_vpn = escape_markdown(vpn, version=2)
    escaped_desc = escape_markdown(desc, version=2)
    
    final_text = f"🔑 *VPN LINK:* `{escaped_vpn}`\n\n📝 *Düşündiriş:*\n{escaped_desc}"

    for c in all_channels:
        cid = str(c.get("channel_id")).strip()
        clink = c.get("link", cid)
        try:
            target = int(cid) if (cid.startswith("-") and cid[1:].isdigit()) or cid.isdigit() else cid
            await context.bot.send_message(chat_id=target, text=final_text, parse_mode="MarkdownV2")
            ok_channels.append(f"🟢 {clink}")
        except Exception as e:
            fail_channels.append(f"🔴 {clink}\n{str(e)}")

    increment_admin_counter(sender_id)

    report = f"📊 **NETIJE**\n\n✅ Şowly: {len(ok_channels)}\n❌ Şowsuz: {len(fail_channels)}\n\n"
    if fail_channels:
        report += "❌ HATALAR:\n\n" + "\n\n".join(fail_channels[:10])

    await status_msg.edit_text(report, parse_mode="Markdown")

# =========================
# 📣 REKLAMA GOÝBERME PROSESI (🛡️ DIŇE KURUCU)
# =========================
async def reklama_goyber_prosesi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rec_type = context.user_data.get("rec_type")
    btn_name = context.user_data.get("btn_name")
    btn_url = context.user_data.get("btn_url")
    
    reply_markup = None
    if btn_name and btn_url:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=btn_name, url=btn_url)]])

    status_msg = await update.message.reply_text("⏳ Reklama ähli kanallara ugradylýar...")
    all_channels = list(channels.find({}))
    
    ok_count = 0
    fail_count = 0

    for c in all_channels:
        cid = str(c.get("channel_id")).strip()
        try:
            target = int(cid) if (cid.startswith("-") and cid[1:].isdigit()) or cid.isdigit() else cid
            
            if rec_type == "photo":
                await context.bot.send_photo(chat_id=target, photo=context.user_data["rec_file_id"], caption=context.user_data["rec_caption"], reply_markup=reply_markup)
            elif rec_type == "video":
                await context.bot.send_video(chat_id=target, video=context.user_data["rec_file_id"], caption=context.user_data["rec_caption"], reply_markup=reply_markup)
            elif rec_type == "text":
                await context.bot.send_message(chat_id=target, text=context.user_data["rec_text"], reply_markup=reply_markup)
                
            ok_count += 1
        except Exception:
            fail_count += 1

    context.user_data.clear()
    await status_msg.edit_text(f"📊 **Reklama Netijesi:**\n\n✅ Şowly ugradylan: `{ok_count}`\n❌ Şowsuz: `{fail_count}`", parse_mode="Markdown")

# =========================
# 🗑️ KANAL POZMAK PANELI
# =========================
async def kanal_pozmak_paneli(message, is_callback=False):
    all_channels = list(channels.find({}))
    keyboard = []
    text = "🗑️ Pozmak isleýän kanalyňy saýla:" if all_channels else "📭 Kanal ýok."

    for c in all_channels:
        cid = str(c.get("channel_id"))
        clink = c.get("link", cid)
        keyboard.append([
            InlineKeyboardButton(clink, callback_data="none"),
            InlineKeyboardButton("❌ Poz", callback_data=f"del_{cid}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")])
    markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)

# =========================
# 👮 ADMIN PANEL
# =========================
async def admin_dolandyr_paneli(message, is_callback=False):
    all_admins = list(admins.find({"is_kurucu": {"$ne": True}}))
    keyboard = [[InlineKeyboardButton("➕ Admin Goş", callback_data="add_admin_btn")]]
    text = f"👮 **ADMIN PANELI**\n\n👑 Kurucu:\n`{KURUCU_ID}`\n\n"

    for adm in all_admins:
        aid = str(adm["user_id"])
        keyboard.append([
            InlineKeyboardButton(f"👤 {aid}", callback_data="none"),
            InlineKeyboardButton("❌ Poz", callback_data=f"del_adm_{aid}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")])
    markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        await message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# =========================
# 📊 STATS PANEL
# =========================
async def statistika_paneli(message):
    total_channels = channels.count_documents({})
    total_admins = admins.count_documents({"is_kurucu": {"$ne": True}})

    text = f"📊 **STATISTIKA**\n\n📢 Kanallar: `{total_channels}`\n👮 Adminler: `{total_admins}`\n"
    keyboard = [[InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")]]

    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# =========================
# 🔘 CALLBACK QUERY HANDLER
# =========================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if not is_admin(uid):
        return

    data = q.data

    # VPN Paýlaş (Ähli adminler we Kurucu)
    if data == "vpn":
        context.user_data["state"] = "VPN"
        await q.message.reply_text("🔗 VPN kody ýa-da linkini ugradyň:")
        return

    # Statistika (Ähli adminler we Kurucu)
    if data == "stats":
        await statistika_paneli(q.message)
        return

    # 🛑 BU ÝERDEN AŞAKDAKY FUNKSIÝALAR DIŇE KURUCU ÜÇIN (Adminler girip bilmez)
    if not is_kurucu(uid):
        return

    if data == "reklama":
        context.user_data["state"] = "REKLAMA_MEDIA"
        await q.message.reply_text("📣 Reklama boljak **Surat**, **Wideo** ýa-da **Tekst** ugradyň:")
        return

    if data == "add":
        context.user_data["state"] = "ADD_ID"
        await q.message.reply_text("🔢 Kanal ID ugradyň:")
        return

    if data == "manage_channels":
        await kanal_pozmak_paneli(q.message, is_callback=True)
        return

    if data.startswith("del_") and not data.startswith("del_adm_"):
        target_cid = data.replace("del_", "")
        channels.delete_one({"$or": [{"channel_id": target_cid}, {"_id": target_cid}]})
        await kanal_pozmak_paneli(q.message, is_callback=True)
        return

    if data == "manage_admins":
        await admin_dolandyr_paneli(q.message, is_callback=True)
        return

    if data == "add_admin_btn":
        context.user_data["state"] = "ADD_ADMIN"
        await q.message.reply_text("👤 Admin boljak ulanyjynyň ID-sini ugradyň:")
        return

    if data.startswith("del_adm_"):
        target_aid = int(data.replace("del_adm_", ""))
        admins.delete_one({"user_id": target_aid})
        await admin_dolandyr_paneli(q.message, is_callback=True)
        return

    if data == "back_main":
        keyboard = [
            [InlineKeyboardButton("🔗 VPN Paýlaş", callback_data="vpn")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
        ]
        if is_kurucu(uid):
            keyboard.insert(1, [InlineKeyboardButton("📣 Reklama Paýlaş", callback_data="reklama")])
            keyboard.insert(2, [InlineKeyboardButton("➕ Kanal Goş", callback_data="add")])
            keyboard.insert(3, [InlineKeyboardButton("🗑️ Kanallary Dolandyr", callback_data="manage_channels")])
            keyboard.insert(4, [InlineKeyboardButton("👮 Adminleri Dolandyr", callback_data="manage_admins")])

        last_share_info = get_last_share_text()
        await q.message.edit_text(
            f"🤖 **VPN BOT PANELI**\n\n"
            f"{last_share_info}\n\n"
            f"Lütfen amaly saýlaň:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# =========================
# 🤖 RUN BOT
# =========================
def run():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, text_handler))
    app.add_handler(CallbackQueryHandler(callback))

    print("✅ BOT BAŞLADY...")
    app.run_polling()

# =========================
# 🚀 MAIN MAIN
# =========================
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(
        target=lambda: app_flask.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))),
        daemon=True
    ).start()
    run()
    
