import logging
import sqlite3
import os
import time
import threading
import asyncio
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError

# --- FLASK WE ANTI-SLEEP (RENDER ÜÇIN) ---
flask_app = Flask(__name__)
RENDER_URL = "https://vpn-bot-z9rj.onrender.com"  

@flask_app.route("/")
def home():
    return "Bot is Alive!", 200

def self_ping():
    time.sleep(20)
    print("Anti-Sleep ulgamy işjeňleşdirildi...")
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
            print("Ping iberildi: Bot oýanyk!")
        except Exception as e:
            print(f"Ping hatasy: {e}")
        time.sleep(300)

# Loglama Sazlamalary
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ESASY SAZLAMALAR ---
BOT_TOKEN = "7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y"
KURUCU_ID = 7523674506  

# --- MAGLUMAT BINASY (DATABASE) ---
def db_kur():
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS adminler (user_id INTEGER PRIMARY KEY, paylasim_sayisi INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kanallar (kanal_id TEXT PRIMARY KEY, kanal_link TEXT)''')
    conn.commit()
    conn.close()

db_kur()

# --- ÝARDÝMCY FUNKSIÝALAR ---
def admin_mi(user_id):
    if user_id == KURUCU_ID:
        return True
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM adminler WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# --- BAŞ MENU (/start) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_mi(user_id):
        await update.message.reply_text("⛔ **Geçiş gadagan!** Bu boty diňe Esasy Gurujy we Adminler ulanyp biler.")
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

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔮 **VPN Dolandyryş Paneline Hoş Geldiňiz!**\nEtmek isleýän işiňizi saýlaň:", reply_markup=reply_markup)

# --- TEKST GIRDILERINI DOLANDYRYŞ ---
async def sms_gelende(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_mi(user_id): return

    isleg = context.user_data.get('isleg')
    text = update.message.text.strip()

    # ⭐ AKYLLY KANAL GOŞMAK
    if "|" in text and ("-100" in text or text.split('|')[0].strip().replace('-', '').isdigit()):
        try:
            k_id, k_link = [x.strip() for x in text.split('|')]
            
            try:
                test_msg = await context.bot.send_message(chat_id=k_id, text="⚙️ Barlag...")
                await context.bot.delete_message(chat_id=k_id, message_id=test_msg.message_id)
            except TelegramError:
                await update.message.reply_text(f"⚠️ **Duýduryş!** Bot `{k_id}` kanalynda admin däl ýa-da sms rugsady ýok!")
                return

            conn = sqlite3.connect('vpn_bot.db')
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kanallar (kanal_id, kanal_link) VALUES (?, ?)", (k_id, k_link))
            conn.commit()
            conn.close()
            
            await update.message.reply_text("✅ **Kanal üstünlikli goşuldy!**\n\nBaş Menu: /start")
            context.user_data.clear()
            return
        except Exception:
            await update.message.reply_text("❌ Format nädogry. Nusga: `-1001234567 | https://t.me/link`")
            return

    # ADMIN GOŞMAK
    if isleg == "AYAK_ADMIN_GOS" and user_id == KURUCU_ID:
        if not text.isdigit():
            await update.message.reply_text("❌ ID diňe san bolmalydyr!")
            return
        
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO adminler (user_id) VALUES (?)", (int(text),))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ `{text}` ID-li ulanyjy Admin edildi!\n\nBaş Menu: /start")
        context.user_data.clear()
        return

    # VPN LİNKINI ALMAK
    elif isleg == "AYAK_VPN_LINK_AL":
        context.user_data['vpn_link'] = text
        context.user_data['isleg'] = "AYAK_VPN_DESC_AL"
        await update.message.reply_text("📝 Indi bolsa VPN düşündiriş tekstini (Description) ýazyň:")
        return

    # DESCRIPTION ALMAK
    elif isleg == "AYAK_VPN_DESC_AL":
        context.user_data['vpn_desc'] = text
        context.user_data['secili_kanallar'] = []
        context.user_data['isleg'] = None
        await vpn_paneli_goster(update.message.reply_text, context)
        return

# --- VPN PAÝLAŞYŞ PANELY ---
async def vpn_paneli_goster(gorkez_func, context: ContextTypes.DEFAULT_TYPE, edit=False):
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT kanal_id, kanal_link FROM kanallar")
    kanallar = cursor.fetchall()
    conn.close()
    
    secili = context.user_data.get('secili_kanallar', [])
    hepsi_secili = len(secili) == len(kanallar) and len(kanallar) > 0

    ust_satir = [
        InlineKeyboardButton("✅ Ählisini Saýla" if not hepsi_secili else "🟩 Ählisi Saýlandy", callback_data="v_HEPSI"),
        InlineKeyboardButton("🚀 PAÝLAŞ", callback_data="v_PAYLAS_ET")
    ]
    keyboard = [ust_satir]
    
    for k_id, k_link in kanallar:
        isaret = "🟢" if k_id in secili else "🔴"
        keyboard.append([InlineKeyboardButton(f"{isaret} {k_link}", callback_data=f"v_sec_{k_id}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    vpn_link = context.user_data.get('vpn_link', '')
    vpn_desc = context.user_data.get('vpn_desc', '')
    
    post_gornus = "👁️ **Postuň kanaldaky görnüşi:**\n\n" + f"`{vpn_link}`\n" + f"{vpn_desc}\n\n" + "Paýlaşyljak kanallary aşakdan saýlaň:"
    
    if edit:
        try: await gorkez_func(text=post_gornus, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception: pass
    else:
        await gorkez_func(text=post_gornus, reply_markup=reply_markup, parse_mode="Markdown")

# --- DÜWMELERIŇ IŞLEÝIŞI ---
async def duwmeler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if not admin_mi(user_id): return

    if data == "menu_kanal_gos":
        context.user_data['isleg'] = "AYAK_KANAL_GOS"
        await query.message.reply_text("👉 Goşmak isleýän kanalyňyzyň **ID-sini** we **Linkini** şu formatda iberiň:\n\n`-100123456789 | https://t.me/kanal_linki`")

    elif data == "menu_admin_gos" and user_id == KURUCU_ID:
        context.user_data['isleg'] = "AYAK_ADMIN_GOS"
        await query.message.reply_text("👤 Goşmak isleýän täze adminiňiziň **Telegram ID**-sini ýazyň:")

    elif data == "menu_vpn_paylas":
        context.user_data['isleg'] = "AYAK_VPN_LINK_AL"
        await query.message.reply_text("🔗 Lütfen, kanallara ugratmak isleýän **VPN Linkiňizi** ýazyň:")

    elif data == "menu_kanal_poz" and user_id == KURUCU_ID:
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT kanal_id, kanal_link FROM kanallar")
        kanallar = cursor.fetchall()
        conn.close()
        if not kanallar:
            await query.message.reply_text("📭 Hasaba alnan kanal tapylmady.")
            return
        keyboard = [[InlineKeyboardButton(f"❌ {k[1]}", callback_data=f"goni_kpoz_{k[0]}")] for k in kanallar]
        await query.message.reply_text("🗑️ Silmek islan kanalyňyzy saýlaň:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("goni_kpoz_") and user_id == KURUCU_ID:
        k_id = data.replace("goni_kpoz_", "")
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM kanallar WHERE kanal_id = ?", (k_id,))
        conn.commit()
        conn.close()
        await query.message.edit_text("✅ Kanal maglumat binasyndan pozuldy! /start")

    elif data == "menu_admin_poz" and user_id == KURUCU_ID:
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM adminler")
        adminler = cursor.fetchall()
        conn.close()
        if not adminler:
            await query.message.reply_text("👥 Admin tapylmady.")
            return
        keyboard = [[InlineKeyboardButton(f"🗑️ Admin: {a[0]}", callback_data=f"goni_apoz_{a[0]}")] for a in adminler]
        await query.message.reply_text("Silmek isleýän adminiňizi saýlaň:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("goni_apoz_") and user_id == KURUCU_ID:
        a_id = data.replace("goni_apoz_", "")
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM adminler WHERE user_id = ?", (int(a_id),))
        conn.commit()
        conn.close()
        await query.message.edit_text(f"✅ {a_id} ID-li admin pozuldy! /start")

    elif data == "menu_statistika":
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM kanallar")
        jemi_kanal = cursor.fetchone()[0]
        cursor.execute("SELECT user_id, paylasim_sayisi FROM adminler")
        admin_list = cursor.fetchall()
        conn.close()
        
        txt = f"📊 **BOT STATİSTİKASY**\n\n📢 Jemi kanallar: **{jemi_kanal}**\n\n👥 **Adminleriň paýlaşyk sany:**\n"
        for adm in admin_list:
            txt += f"├─ Admin ID (`{adm[0]}`): {adm[1]} gezek paýlaşdy.\n"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif data == "v_HEPSI" or data.startswith("v_sec_") or data == "v_PAYLAS_ET":
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT kanal_id FROM kanallar")
        tum_kanal_idleri = [x[0] for x in cursor.fetchall()]
        conn.close()
        
        secili = context.user_data.get('secili_kanallar', [])
        
        if data == "v_HEPSI":
            if len(secili) == len(tum_kanal_idleri):
                context.user_data['secili_kanallar'] = []
            else:
                context.user_data['secili_kanallar'] = tum_kanal_idleri.copy()
            await vpn_paneli_goster(query.message.edit_text, context, edit=True)

        elif data.startswith("v_sec_"):
            k_id = data.replace("v_sec_", "")
            if k_id in secili: secili.remove(k_id)
            else: secili.append(k_id)
            context.user_data['secili_kanallar'] = secili
            await vpn_paneli_goster(query.message.edit_text, context, edit=True)
            
        elif data == "v_PAYLAS_ET":
            vpn_link = context.user_data.get('vpn_link')
            vpn_desc = context.user_data.get('vpn_desc', '')
            hedef_kanallar = context.user_data.get('secili_kanallar', [])
            
            if not hedef_kanallar:
                await query.message.reply_text("❌ Lütfen, ilki aşakdan paýlaşyljak kanallary saýlaň!")
                return
                
            sonky_sms = f"`{vpn_link}`\n{vpn_desc}"
            sowly = 0
            hata = 0
            
            for cid in hedef_kanallar:
                try:
                    await context.bot.send_message(chat_id=cid, text=sonky_sms, parse_mode="Markdown")
                    sowly += 1
                except Exception:
                    hata += 1
                    
            conn = sqlite3.connect('vpn_bot.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE adminler SET paylasim_sayisi = paylasim_sayisi
        
