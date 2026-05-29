import os
import time
import asyncio
import threading
import requests
from flask import Flask
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ======================
# 🌐 FLASK (ALIVE SERVER)
# ======================
app_flask = Flask(__name__)
RENDER_URL = os.getenv("RENDER_URL", "https://vpn-bot-z9rj.onrender.com")

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

# ======================
# 🔐 CONFIG
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "7846603711:AAHGCm_uX7NmzHPFcRigI6ERNtCa91SXxZY")
KURUCU_ID = int(os.getenv("KURUCU_ID", "7523674506"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")

mongo = MongoClient(MONGO_URI)
db = mongo["vpn_bot"]
admins_col = db["admins"]
channels_col = db["channels"]
settings_col = db["settings"]

# ======================
# 👮 ADMIN CHECK & COUNTER
# ======================
def is_admin(user_id):
    if user_id == KURUCU_ID:
        return True
    return admins_col.find_one({"user_id": int(user_id)}) is not None

def increment_admin_counter(user_id):
    if user_id == KURUCU_ID:
        admins_col.update_one(
            {"user_id": KURUCU_ID},
            {"$inc": {"sent_count": 1}, "$set": {"is_kurucu": True}},
            upsert=True
        )
    else:
        admins_col.update_one(
            {"user_id": int(user_id)},
            {"$inc": {"sent_count": 1}},
            upsert=True
        )

# ======================
# ⏳ SON PAYLAŞIM BİLGİSİ
# ======================
def get_last_share_text():
    data = settings_col.find_one({"key": "last_share"})
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

# ======================
# 🏠 ANA MENÜ KEYBOARD
# ======================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 VPN Paýlaş", callback_data="vpn")],
        [InlineKeyboardButton("➕ Kanal Goş", callback_data="add")],
        [InlineKeyboardButton("🗑️ Kanallary Dolandyr", callback_data="manage_channels")],
        [InlineKeyboardButton("👮 Adminleri Dolandyr", callback_data="manage_admins")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ])

# ======================
# 🚀 START PANEL
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text("⛔ Size rugsat berilmedi!")
        return

    context.user_data.clear()
    last_share_info = get_last_share_text()

    await update.message.reply_text(
        f"🤖 **VPN BOT PANELI**\n\n{last_share_info}\n\nLütfen amaly saýlaň:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ======================
# 💬 TEXT HANDLER
# ======================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    state = context.user_data.get("state")
    text = update.message.text.strip()

    # ➕ KANAL GOŞMAK
    if state == "ADD":
        try:
            parts = text.split("|", 1)
            if len(parts) != 2:
                raise ValueError("Format hatası")

            cid = parts[0].strip()
            link = parts[1].strip()

            if not cid or not link:
                raise ValueError("Boş alan")

            channels_col.update_one(
                {"channel_id": cid},
                {"$set": {"channel_id": cid, "link": link}},
                upsert=True
            )
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ Kanal üstünlikli goşuldy!\n📢 ID: `{cid}`\n🔗 Link: {link}",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(
                "❌ Format ýalňyş!\n\nDogry format:\n`-1001234567890 | https://t.me/kanal_adi`",
                parse_mode="Markdown"
            )

    # 👮 ADMIN GOŞMAK
    elif state == "ADD_ADMIN":
        if not text.isdigit() and not (text.startswith('-') and text[1:].isdigit()):
            await update.message.reply_text("❌ Ýalňyş ID! Diňe san ugradyň:")
            return

        target_id = int(text)

        if target_id == KURUCU_ID:
            await update.message.reply_text("⚠️ Kurucu eýýäm admin!")
            return

        admins_col.update_one(
            {"user_id": target_id},
            {"$setOnInsert": {"user_id": target_id, "sent_count": 0}},
            upsert=True
        )
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ ID: `{target_id}` bolan admin üstünlikli goşuldy!",
            parse_mode="Markdown"
        )

    # 🔗 VPN LINK
    elif state == "VPN":
        context.user_data["vpn"] = text
        context.user_data["state"] = "DESC"
        await update.message.reply_text("📝 Indi bolsa düşündirişini (Description) ugradyň:")

    # 📝 DESC → SEND
    elif state == "DESC":
        context.user_data["desc"] = text
        asyncio.create_task(awto_goyber_prosesi(update, context, uid))

    else:
        # Durum yoksa ana menüye yönlendir
        last_share_info = get_last_share_text()
        await update.message.reply_text(
            f"🤖 **VPN BOT PANELI**\n\n{last_share_info}\n\nLütfen amaly saýlaň:",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )

# ======================
# 🚀 OTOMATİK GÖNDERME
# ======================
async def awto_goyber_prosesi(update: Update, context: ContextTypes.DEFAULT_TYPE, sender_id: int):
    vpn = context.user_data.get("vpn", "")
    desc = context.user_data.get("desc", "")
    context.user_data.clear()

    status_msg = await update.message.reply_text("⏳ VPN ähli kanallara ugradylýar, garaşyň...")

    all_channels = list(channels_col.find({}))
    if not all_channels:
        await status_msg.edit_text("❌ Binada hiç hili kanal tapylmady!")
        return

    settings_col.update_one(
        {"key": "last_share"},
        {"$set": {"sender_id": sender_id, "timestamp": time.time()}},
        upsert=True
    )

    ok_channels = []
    fail_channels = []

    for c in all_channels:
        cid = str(c["channel_id"]).strip()
        clink = c.get("link", f"ID: {cid}")

        try:
            # Güvenli ID dönüşümü
            try:
                chat_target = int(cid)
            except ValueError:
                chat_target = cid  # @username gibi string ID'ler için

            await context.bot.send_message(
                chat_id=chat_target,
                text=f"{vpn}\n\n{desc}"
            )
            ok_channels.append(f"🟢 {clink}")
        except Exception as e:
            fail_channels.append(f"🔴 {clink}\n   ↳ Hata: `{str(e)[:80]}`")

    increment_admin_counter(sender_id)

    report = "📊 **GÖYBERLEN KANALLARYŇ NETIJESI:**\n\n"

    if ok_channels:
        report += f"✅ **Şowluy:** {len(ok_channels)} kanal\n"
        report += "\n".join(ok_channels) + "\n\n"
    else:
        report += "✅ **Şowluy ugradylan:** Ýok\n\n"

    if fail_channels:
        report += f"❌ **Şowsuz:** {len(fail_channels)} kanal\n"
        report += "\n".join(fail_channels)
    else:
        report += "❌ **Şowsuz:** Ýok — hemmesine üstünlikli gitdi! 🎉"

    await status_msg.edit_text(report, parse_mode="Markdown")

# ======================
# 🗑️ KANAL YÖNETİM PANELİ
# ======================
async def kanal_pozmak_paneli(message, is_callback=False):
    all_channels = list(channels_col.find({}))
    keyboard = []

    if not all_channels:
        text = "📭 Binada hiç hili kanal ýok."
    else:
        text = "🗑️ **Pozmak isleýän kanalyňyzyň ýanyndaky ❌ düwmesine basyň:**"
        for c in all_channels:
            cid = str(c["channel_id"])
            clink = c.get("link", f"ID: {cid}")
            display = clink if len(clink) <= 30 else clink[:27] + "..."
            keyboard.append([
                InlineKeyboardButton(f"📢 {display}", callback_data="none"),
                InlineKeyboardButton("❌ Poz", callback_data=f"del_{cid}")
            ])

    keyboard.append([InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")])

    markup = InlineKeyboardMarkup(keyboard)
    try:
        if is_callback:
            await message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
        else:
            await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

# ======================
# 👮 ADMİN YÖNETİM PANELİ
# ======================
async def admin_dolandyr_paneli(message, is_callback=False):
    all_admins = list(admins_col.find({"is_kurucu": {"$ne": True}}))
    keyboard = [
        [InlineKeyboardButton("➕ Täze Admin Goş", callback_data="add_admin_btn")]
    ]

    text = f"👮 **Adminleri Dolandyryş Paneli:**\n\n"
    text += f"👑 **Esasy Kurucu:** `{KURUCU_ID}` (Goragly)\n\n"

    if all_admins:
        text += f"📋 **Adminler ({len(all_admins)} sany):**\n"
        for a in all_admins:
            aid = str(a["user_id"])
            count = a.get("sent_count", 0)
            keyboard.append([
                InlineKeyboardButton(f"👤 {aid} ({count} paýlaşma)", callback_data="none"),
                InlineKeyboardButton("❌ Poz", callback_data=f"del_adm_{aid}")
            ])
    else:
        text += "ℹ️ Goşmaça admin ýok."

    keyboard.append([InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")])

    markup = InlineKeyboardMarkup(keyboard)
    try:
        if is_callback:
            await message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
        else:
            await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

# ======================
# 📊 İSTATİSTİK PANELİ
# ======================
async def statistika_paneli(message):
    total_channels = channels_col.count_documents({})
    total_admins = admins_col.count_documents({"is_kurucu": {"$ne": True}})

    kurucu_data = admins_col.find_one({"user_id": KURUCU_ID})
    kurucu_count = kurucu_data.get("sent_count", 0) if kurucu_data else 0

    text = "📊 **BOTUŇ UMUMY STATISTIKASY**\n\n"
    text += f"📢 **Jemi Kanallar:** `{total_channels}` sany\n"
    text += f"👮 **Jemi Adminler:** `{total_admins}` sany\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "📈 **VPN Paýlaşyş Sanawy:**\n\n"
    text += f"👑 Kurucu (`{KURUCU_ID}`): **{kurucu_count} gezek**\n"

    all_registered = list(admins_col.find({"is_kurucu": {"$ne": True}}))
    for adm in all_registered:
        aid = adm["user_id"]
        count = adm.get("sent_count", 0)
        text += f"👤 Admin (`{aid}`): **{count} gezek**\n"

    keyboard = [[InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")]]
    try:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ======================
# 🔘 CALLBACK HANDLER
# ======================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    if not is_admin(uid):
        await q.answer("⛔ Size rugsat berilmedi!", show_alert=True)
        return

    data = q.data

    # Hiçbir işlem yapma butonu
    if data == "none":
        return

    # ➕ Kanal ekle
    if data == "add":
        context.user_data.clear()
        context.user_data["state"] = "ADD"
        await q.message.reply_text(
            "📢 Kanal maglumatyny ugradyň:\n\nDogry format:\n`-1001234567890 | https://t.me/kanal_adi`",
            parse_mode="Markdown"
        )
        return

    # 🔗 VPN paylaş
    if data == "vpn":
        context.user_data.clear()
        context.user_data["state"] = "VPN"
        await q.message.reply_text("🔗 Göni VPN linkini ugradyň:")
        return

    # 🗑️ Kanal yönet
    if data == "manage_channels":
        await kanal_pozmak_paneli(q.message, is_callback=True)
        return

    # ❌ Kanal sil
    if data.startswith("del_") and not data.startswith("del_adm_"):
        target_cid = data[4:]  # "del_" sonrasını al
        result = channels_col.delete_one({"channel_id": target_cid})
        if result.deleted_count > 0:
            await q.answer("✅ Kanal üstünlikli pozuldy!", show_alert=False)
        else:
            await q.answer("⚠️ Kanal tapylmady!", show_alert=True)
        await kanal_pozmak_paneli(q.message, is_callback=True)
        return

    # 👮 Admin yönet
    if data == "manage_admins":
        await admin_dolandyr_paneli(q.message, is_callback=True)
        return

    # ➕ Admin ekle butonu
    if data == "add_admin_btn":
        context.user_data.clear()
        context.user_data["state"] = "ADD_ADMIN"
        await q.message.reply_text(
            "👤 Täze adminiň **Telegram ID**-sini ugradyň:\n\nMisal: `123456789`",
            parse_mode="Markdown"
        )
        return

    # ❌ Admin sil
    if data.startswith("del_adm_"):
        target_aid_str = data[8:]  # "del_adm_" sonrasını al
        try:
            target_aid = int(target_aid_str)
        except ValueError:
            await q.answer("❌ Geçersiz ID!", show_alert=True)
            return

        if target_aid == KURUCU_ID:
            await q.answer("⛔ Kurucuny pozup bolmaýar!", show_alert=True)
            return

        result = admins_col.delete_one({"user_id": target_aid})
        if result.deleted_count > 0:
            await q.answer("✅ Admin üstünlikli pozuldy!", show_alert=False)
        else:
            await q.answer("⚠️ Admin tapylmady!", show_alert=True)
        await admin_dolandyr_paneli(q.message, is_callback=True)
        return

    # 📊 İstatistik
    if data == "stats":
        await statistika_paneli(q.message)
        return

    # ⬅️ Ana menüye dön
    if data == "back_main":
        context.user_data.clear()
        last_share_info = get_last_share_text()
        try:
            await q.message.edit_text(
                f"🤖 **VPN BOT PANELI**\n\n{last_share_info}\n\nLütfen amaly saýlaň:",
                reply_markup=main_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

# ======================
# 🤖 BOT BAŞLAT
# ======================
def run():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callback))
    print("✅ Bot durnukly yagdayda baslady...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(
        target=lambda: app_flask.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))),
        daemon=True
    ).start()
    run()
        
