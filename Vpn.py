import logging
import sqlite3
import os
import time
import threading
import requests
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError

# Loglama
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- FLASK WE WEBSERVER ---
flask_app = Flask(__name__)
RENDER_URL = "https://vpn-bot-z9rj.onrender.com"  

@flask_app.route("/")
def home():
    return "Bot is Alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)

def self_ping():
    time.sleep(30)
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
        except Exception:
            pass
        time.sleep(300)

# --- ESASY SAZLAMALAR ---
BOT_TOKEN = "7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y"
KURUCU_ID = 7523674506  

# --- MAGLUMAT BINASY ---
def db_kur():
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS adminler (user_id INTEGER PRIMARY KEY, paylasim_sayisi INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kanallar (kanal_id TEXT PRIMARY KEY, kanal_link TEXT)''')
    conn.commit()
    conn.close()

db_kur()

def admin_mi(user_id):
    if user_id == KURUCU_ID:
        return True
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM adminler WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# --- KOMANDALAR WE FATURALAR ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_mi(user_id):
        await update.message.reply_text("⛔ **Geçiş gadagan!**")
        return

    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("🔗 VPN Link Paýlaş", callback_data="menu_vpn_paylas")],
        [InlineKeyboardButton("➕ Kanal Goş", callback_data="menu_kanal_gos"), 
         InlineKeyboardButton("➖ Kanal Poz", callback_data="menu_kanal_poz")],
        [InlineKeyboardButton("📊 Statistika", callback_data="menu_statistika")]
    ]
    if user_id == KURUCU_ID:
        keyboard.append([InlineKeyboardButton("👤 Admin Goş", callback_data="menu_admin_gos"),
                         InlineKeyboardButton("🗑️ Admin Poz", callback_data="menu_admin_poz")])

    await update.message.reply_text("🔮 **VPN Dolandyryş Paneli**", reply_markup=InlineKeyboardMarkup(keyboard))

async def sms_gelende(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_mi(user_id): return

    isleg = context.user_data.get('isleg')
    text = update.message.text.strip()

    if isleg == "AYAK_KANAL_GOS" or ("|" in text and ("-100" in text or text.split('|')[0].strip().replace('-', '').isdigit())):
        if "|" not in text:
            await update.message.reply_text("❌ Format: `-10012345 | https://t.me/link`")
            return
        try:
            k_id, k_link = [x.strip() for x in text.split('|')]
            try:
                test_msg = await context.bot.send_message(chat_id=k_id, text="⚙️ Barlag...")
                await context.bot.delete_message(chat_id=k_id, message_id=test_msg.message_id)
            except TelegramError:
                await update.message.reply_text("⚠️ Bot bu kanalda admin däl!")
                return

            conn = sqlite3.connect('vpn_bot.db')
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kanallar (kanal_id, kanal_link) VALUES (?, ?)", (k_id, k_link))
            conn.commit()
            conn.close()
            await update.message.reply_text("✅ Kanal goşuldy! /start")
            context.user_data.clear()
        except Exception:
            await update.message.reply_text("❌ Hata ýüze çykdy.")
        return

    if isleg == "AYAK_ADMIN_GOS" and user_id == KURUCU_ID:
        if not text.isdigit(): return
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO adminler (user_id) VALUES (?)", (int(text),))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Admin goşuldy! /start")
        context.user_data.clear()
        return

    elif isleg == "AYAK_VPN_LINK_AL":
        context.user_data['vpn_link'] = text
        context.user_data['isleg'] = "AYAK_VPN_DESC_AL"
        await update.message.reply_text("📝 Description ýazyň:")
        return

    elif isleg == "AYAK_VPN_DESC_AL":
        context.user_data['vpn_desc'] = text
        context.user_data['secili_kanallar'] = []
        context.user_data['isleg'] = None
        await vpn_paneli_goster(update.message.reply_text, context)
        return

async def vpn_paneli_goster(gorkez_func, context: ContextTypes.DEFAULT_TYPE, edit=False):
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT kanal_id, kanal_link FROM kanallar")
    kanallar = cursor.fetchall()
    conn.close()
    
    secili = context.user_data.get('secili_kanallar', [])
    hepsi_secili = len(secili) == len(kanallar) and len(kanallar) > 0

    keyboard = [[
        InlineKeyboardButton("✅ Ählisini Saýla" if not hepsi_secili else "🟩 Ählisi Saýlandy", callback_data="v_HEPSI"),
        InlineKeyboardButton("🚀 PAÝLAŞ", callback_data="v_PAYLAS_ET")
    ]]
    for k_id, k_link in kanallar:
        isaret = "🟢" if k_id in secili else "🔴"
        keyboard.append([InlineKeyboardButton(f"{isaret} {k_link}", callback_data=f"v_sec_{k_id}")])
        
    vpn_link = context.user_data.get('vpn_link', '')
    vpn_desc = context.user_data.get('vpn_desc', '')
    post_gornus = f"`{vpn_link}`\n{vpn_desc}\n\nKanallary saýlaň:"
    
    if edit:
        try: await gorkez_func(text=post_gornus, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception: pass
    else:
        await gorkez_func(text=post_gornus, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def duwmeler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if not admin_mi(user_id): return

    if data == "menu_kanal_gos":
        context.user_data['isleg'] = "AYAK_KANAL_GOS"
        await query.message.reply_text("👉 Formatda iberiň:\n\n`-100123456789 | https://t.me/link`")
    elif data == "menu_admin_gos" and user_id == KURUCU_ID:
        context.user_data['isleg'] = "AYAK_ADMIN_GOS"
        await query.message.reply_text("👤 Telegram ID ýazyň:")
    elif data == "menu_vpn_paylas":
        context.user_data['isleg'] = "AYAK_VPN_LINK_AL"
        await query.message.reply_text("🔗 VPN Linkiňizi ýazyň:")
    elif data == "menu_kanal_poz" and user_id == KURUCU_ID:
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT kanal_id, kanal_link FROM kanallar")
        kanallar = cursor.fetchall()
        conn.close()
        if not kanallar: return
        keyboard = [[InlineKeyboardButton(f"❌ {k[1]}", callback_data=f"goni_kpoz_{k[0]}")] for k in kanallar]
        await query.message.reply_text("🗑️ Kanal saýlaň:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("goni_kpoz_") and user_id == KURUCU_ID:
        k_id = data.replace("goni_kpoz_", "")
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM kanallar WHERE kanal_id = ?", (k_id,))
        conn.commit()
        conn.close()
        await query.message.edit_text("✅ Pozuldy! /start")
    elif data == "menu_statistika":
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM kanallar")
        jemi = cursor.fetchone()[0]
        conn.close()
        await query.message.reply_text(f"📊 Jemi kanal: {jemi}\n/start")

    elif data == "v_HEPSI" or data.startswith("v_sec_") or data == "v_PAYLAS_ET":
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT kanal_id FROM kanallar")
        tum_idler = [x[0] for x in cursor.fetchall()]
        conn.close()
        secili = context.user_data.get('secili_kanallar', [])

        if data == "v_HEPSI":
            context.user_data['secili_kanallar'] = [] if len(secili) == len(tum_idler) else tum_idler.copy()
            await vpn_paneli_goster(query.message.edit_text, context, edit=True)
        elif data.startswith("v_sec_"):
            k_id = data.replace("v_sec_", "")
            secili.remove(k_id) if k_id in secili else secili.append(k_id)
            context.user_data['secili_kanallar'] = secili
            await vpn_paneli_goster(query.message.edit_text, context, edit=True)
        elif data == "v_PAYLAS_ET":
            vpn_link = context.user_data.get('vpn_link')
            vpn_desc = context.user_data.get('vpn_desc', '')
            hedef = context.user_data.get('secili_kanallar', [])
            if not hedef: return
            sonky_sms = f"`{vpn_link}`\n{vpn_desc}"
            for cid in hedef:
                try: await context.bot.send_message(chat_id=cid, text=sonky_sms, parse_mode="Markdown")
                except Exception: pass
            await query.message.edit_text("🚀 Paýlaşyldy! /start")
            context.user_data.clear()

# --- INPUT FIXER FOR RENDER ---
async def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(duwmeler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sms_gelende))
    application.add_handler(CommandHandler("start", start))
    
    # Boty asynk usulda el bilen başlatmak (Render-i doňdurmazlygy üçin)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Render Web serverini we Pingeri parallel potokda (Thread) yzda saklaýarys
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    print("Bot arka planda üstünlikli diňlenilýär...")
    
    # Botuň öçmezligi üçin asynk garaşma döwresi
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    # Esasy uly asyncio loop-y işledýäris
    asyncio.run(run_bot())
        
