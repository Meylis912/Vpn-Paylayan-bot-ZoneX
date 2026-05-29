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

# =========================
# 🌐 FLASK SERVER
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
            requests.get(
                RENDER_URL,
                timeout=10
            )

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

# Unique index
try:
    channels.create_index(
        "channel_id",
        unique=True
    )
except:
    pass

# =========================
# 👮 ADMIN CHECK
# =========================
def is_admin(user_id):

    if user_id == KURUCU_ID:
        return True

    return admins.find_one({
        "user_id": int(user_id)
    }) is not None

# =========================
# 📈 ADMIN COUNTER
# =========================
def increment_admin_counter(user_id):

    if user_id == KURUCU_ID:

        admins.update_one(
            {"user_id": KURUCU_ID},
            {
                "$inc": {
                    "sent_count": 1
                },

                "$set": {
                    "is_kurucu": True
                }
            },
            upsert=True
        )

    else:

        admins.update_one(
            {"user_id": int(user_id)},
            {
                "$inc": {
                    "sent_count": 1
                }
            },
            upsert=True
        )

# =========================
# ⏳ LAST SHARE INFO
# =========================
def get_last_share_text():

    data = settings.find_one({
        "key": "last_share"
    })

    if not data:
        return "ℹ️ Entek hiç hili VPN paýlaşylmady."

    sender = data.get("sender_id")
    share_time_ts = data.get("timestamp")

    diff_seconds = int(
        time.time() - share_time_ts
    )

    if diff_seconds < 60:
        wagt_text = "ýaňyja"

    elif diff_seconds < 3600:
        wagt_text = f"{diff_seconds // 60} minut öň"

    elif diff_seconds < 86400:
        wagt_text = f"{diff_seconds // 3600} sagat öň"

    else:
        wagt_text = f"{diff_seconds // 86400} gün öň"

    return (
        f"👤 **Iň soňky paýlaşan:** `{sender}`\n"
        f"⏱️ **Wagty:** {wagt_text}"
    )

# =========================
# 🚀 START
# =========================
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    uid = update.effective_user.id

    if not is_admin(uid):

        await update.message.reply_text(
            "⛔ Size rugsat berilmedi!"
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "🔗 VPN Paýlaş",
                callback_data="vpn"
            )
        ],

        [
            InlineKeyboardButton(
                "➕ Kanal Goş",
                callback_data="add"
            )
        ],

        [
            InlineKeyboardButton(
                "🗑️ Kanallary Dolandyr",
                callback_data="manage_channels"
            )
        ],

        [
            InlineKeyboardButton(
                "👮 Adminleri Dolandyr",
                callback_data="manage_admins"
            )
        ],

        [
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="stats"
            )
        ]
    ]

    last_share_info = get_last_share_text()

    await update.message.reply_text(
        f"🤖 **VPN BOT PANELI**\n\n"
        f"{last_share_info}\n\n"
        f"Lütfen amaly saýlaň:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="Markdown"
    )

# =========================
# 💬 TEXT HANDLER
# =========================
async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    uid = update.effective_user.id

    if not is_admin(uid):
        return

    state = context.user_data.get("state")
    text = update.message.text.strip()

    # =========================
    # ➕ ADD CHANNEL ID
    # =========================
    if state == "ADD_ID":

        is_valid_id = False

        if text.startswith("-") and text[1:].isdigit():
            is_valid_id = True

        elif text.isdigit():
            is_valid_id = True

        if not is_valid_id:

            await update.message.reply_text(
                "❌ Dogry Kanal ID ugradyň:\n\n"
                "`-1003262094319`",
                parse_mode="Markdown"
            )

            return

        context.user_data["temp_channel_id"] = text
        context.user_data["state"] = "ADD_LINK"

        await update.message.reply_text(
            "🔗 Kanal linkini ugradyň:\n\n"
            "`https://t.me/...`",
            parse_mode="Markdown"
        )

    # =========================
    # ➕ ADD CHANNEL LINK
    # =========================
    elif state == "ADD_LINK":

        if not (
            text.startswith("http://")
            or text.startswith("https://")
            or text.startswith("t.me/")
        ):

            await update.message.reply_text(
                "❌ Dogry kanal linkini ugradyň!"
            )

            return

        channel_id_str = context.user_data.get(
            "temp_channel_id"
        )

        # OLD + NEW SYSTEM CHECK
        existing = channels.find_one({
            "$or": [
                {
                    "channel_id": channel_id_str
                },
                {
                    "_id": channel_id_str
                }
            ]
        })

        if existing:

            await update.message.reply_text(
                "⚠️ Bu kanal öň goşulan!"
            )

            context.user_data.clear()
            return

        # SAVE NEW CHANNEL
        channels.insert_one({
            "channel_id": channel_id_str,
            "link": text,
            "added_at": time.time()
        })

        await update.message.reply_text(
            "✅ Kanal üstünlikli goşuldy!"
        )

        context.user_data.clear()

    # =========================
    # 👮 ADD ADMIN
    # =========================
    elif state == "ADD_ADMIN":

        if not text.isdigit():

            await update.message.reply_text(
                "❌ Diňe san görnüşinde ID ugradyň!"
            )

            return

        target_id = int(text)

        admins.update_one(
            {
                "user_id": target_id
            },

            {
                "$setOnInsert": {
                    "sent_count": 0
                }
            },

            upsert=True
        )

        await update.message.reply_text(
            f"✅ `{target_id}` admin boldy!",
            parse_mode="Markdown"
        )

        context.user_data.clear()

    # =========================
    # 🔗 VPN
    # =========================
    elif state == "VPN":

        context.user_data["vpn"] = text
        context.user_data["state"] = "DESC"

        await update.message.reply_text(
            "📝 Düşündiriş ugradyň:"
        )

    # =========================
    # 📝 DESCRIPTION
    # =========================
    elif state == "DESC":

        context.user_data["desc"] = text

        asyncio.create_task(
            awto_goyber_prosesi(
                update,
                context,
                uid
            )
        )

# =========================
# 🚀 SEND PROCESS
# =========================
async def awto_goyber_prosesi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    sender_id: int
):

    vpn = context.user_data.get("vpn")
    desc = context.user_data.get("desc")

    context.user_data.clear()

    status_msg = await update.message.reply_text(
        "⏳ VPN ähli kanallara ugradylýar..."
    )

    all_channels = list(
        channels.find({})
    )

    if not all_channels:

        await status_msg.edit_text(
            "❌ Kanal ýok!"
        )

        return

    settings.update_one(
        {"key": "last_share"},

        {
            "$set": {
                "sender_id": sender_id,
                "timestamp": time.time()
            }
        },

        upsert=True
    )

    ok_channels = []
    fail_channels = []

    for c in all_channels:

        cid = str(
            c.get("channel_id")
        ).strip()

        clink = c.get(
            "link",
            cid
        )

        try:

            if cid.startswith("-") and cid[1:].isdigit():
                target = int(cid)

            elif cid.isdigit():
                target = int(cid)

            else:
                target = cid

            await context.bot.send_message(
                chat_id=target,
                text=f"{vpn}\n\n{desc}"
            )

            ok_channels.append(
                f"🟢 {clink}"
            )

        except Exception as e:

            fail_channels.append(
                f"🔴 {clink}\n{str(e)}"
            )

    increment_admin_counter(sender_id)

    report = (
        "📊 **NETIJE**\n\n"
    )

    report += (
        f"✅ Şowly: {len(ok_channels)}\n"
    )

    report += (
        f"❌ Şowsuz: {len(fail_channels)}\n\n"
    )

    if fail_channels:

        report += (
            "❌ HATALAR:\n\n"
        )

        report += "\n\n".join(
            fail_channels[:10]
        )

    await status_msg.edit_text(
        report,
        parse_mode="Markdown"
    )

# =========================
# 🗑️ CHANNEL PANEL
# =========================
async def kanal_pozmak_paneli(
    message,
    is_callback=False
):

    all_channels = list(
        channels.find({})
    )

    keyboard = []

    if not all_channels:

        text = "📭 Kanal ýok."

    else:

        text = (
            "🗑️ Pozmak isleýän "
            "kanalyňy saýla:"
        )

        for c in all_channels:

            cid = str(
                c.get("channel_id")
            )

            clink = c.get(
                "link",
                cid
            )

            keyboard.append([
                InlineKeyboardButton(
                    clink,
                    callback_data="none"
                ),

                InlineKeyboardButton(
                    "❌ Poz",
                    callback_data=f"del_{cid}"
                )
            ])

    keyboard.append([
        InlineKeyboardButton(
            "⬅️ Baş Menýu",
            callback_data="back_main"
        )
    ])

    if is_callback:

        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

    else:

        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

# =========================
# 👮 ADMIN PANEL
# =========================
async def admin_dolandyr_paneli(
    message,
    is_callback=False
):

    all_admins = list(
        admins.find({
            "is_kurucu": {
                "$ne": True
            }
        })
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Admin Goş",
                callback_data="add_admin_btn"
            )
        ]
    ]

    text = (
        "👮 **ADMIN PANELI**\n\n"
    )

    text += (
        f"👑 Kurucu:\n`{KURUCU_ID}`\n\n"
    )

    for adm in all_admins:

        aid = str(
            adm["user_id"]
        )

        keyboard.append([
            InlineKeyboardButton(
                f"👤 {aid}",
                callback_data="none"
            ),

            InlineKeyboardButton(
                "❌ Poz",
                callback_data=f"del_adm_{aid}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "⬅️ Baş Menýu",
            callback_data="back_main"
        )
    ])

    if is_callback:

        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="Markdown"
        )

    else:

        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="Markdown"
        )

# =========================
# 📊 STATS
# =========================
async def statistika_paneli(
    message
):

    total_channels = channels.count_documents({})
    total_admins = admins.count_documents({
        "is_kurucu": {
            "$ne": True
        }
    })

    text = (
        "📊 **STATISTIKA**\n\n"
    )

    text += (
        f"📢 Kanallar: `{total_channels}`\n"
    )

    text += (
        f"👮 Adminler: `{total_admins}`\n"
    )

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Baş Menýu",
            callback_data="back_main"
        )
    ]]

    await message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="Markdown"
    )

# =========================
# 🔘 CALLBACKS
# =========================
async def callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    q = update.callback_query

    await q.answer()

    uid = q.from_user.id

    if not is_admin(uid):
        return

    data = q.data

    # =========================
    # ➕ ADD CHANNEL
    # =========================
    if data == "add":

        context.user_data["state"] = "ADD_ID"

        await q.message.reply_text(
            "🔢 Kanal ID ugradyň:",
            parse_mode="Markdown"
        )

        return

    # =========================
    # 🔗 VPN
    # =========================
    if data == "vpn":

        context.user_data["state"] = "VPN"

        await q.message.reply_text(
            "🔗 VPN link ugradyň:"
        )

        return

    # =========================
    # 🗑️ MANAGE CHANNELS
    # =========================
    if data == "manage_channels":

        await kanal_pozmak_paneli(
            q.message,
            is_callback=True
        )

        return

    # =========================
    # ❌ DELETE CHANNEL
    # =========================
    if data.startswith("del_") and not data.startswith("del_adm_"):

        target_cid = data.replace(
            "del_",
            ""
        )

        channels.delete_one({
            "$or": [
                {
                    "channel_id": target_cid
                },
                {
                    "_id": target_cid
                }
            ]
        })

        await kanal_pozmak_paneli(
            q.message,
            is_callback=True
        )

        return

    # =========================
    # 👮 ADMIN PANEL
    # =========================
    if data == "manage_admins":

        await admin_dolandyr_paneli(
            q.message,
            is_callback=True
        )

        return

    # =========================
    # ➕ ADD ADMIN
    # =========================
    if data == "add_admin_btn":

        context.user_data["state"] = "ADD_ADMIN"

        await q.message.reply_text(
            "👤 Admin ID ugradyň:"
        )

        return

    # =========================
    # ❌ DELETE ADMIN
    # =========================
    if data.startswith("del_adm_"):

        target_aid = int(
            data.replace(
                "del_adm_",
                ""
            )
        )

        admins.delete_one({
            "user_id": target_aid
        })

        await admin_dolandyr_paneli(
            q.message,
            is_callback=True
        )

        return

    # =========================
    # 📊 STATS
    # =========================
    if data == "stats":

        await statistika_paneli(
            q.message
        )

        return

    # =========================
    # ⬅️ BACK MAIN
    # =========================
    if data == "back_main":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔗 VPN Paýlaş",
                    callback_data="vpn"
                )
            ],

            [
                InlineKeyboardButton(
                    "➕ Kanal Goş",
                    callback_data="add"
                )
            ],

            [
                InlineKeyboardButton(
                    "🗑️ Kanallary Dolandyr",
                    callback_data="manage_channels"
                )
            ],

            [
                InlineKeyboardButton(
                    "👮 Adminleri Dolandyr",
                    callback_data="manage_admins"
                )
            ],

            [
                InlineKeyboardButton(
                    "📊 Statistika",
                    callback_data="stats"
                )
            ]
        ]

        last_share_info = get_last_share_text()

        await q.message.edit_text(
            f"🤖 **VPN BOT PANELI**\n\n"
            f"{last_share_info}\n\n"
            f"Lütfen amaly saýlaň:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="Markdown"
        )

# =========================
# 🤖 RUN BOT
# =========================
def run():

    app = Application.builder() \
        .token(BOT_TOKEN) \
        .build()

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            callback
        )
    )

    print(
        "✅ BOT BAŞLADY..."
    )

    app.run_polling()

# =========================
# 🚀 MAIN
# =========================
if __name__ == "__main__":

    threading.Thread(
        target=keep_alive,
        daemon=True
    ).start()

    threading.Thread(
        target=lambda: app_flask.run(
            host="0.0.0.0",
            port=int(
                os.getenv(
                    "PORT",
                    10000
                )
            )
        ),
        daemon=True
    ).start()

    run()
