import logging
import sqlite3
import os
import time
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from pymongo import MongoClient
from datetime import datetime

# --- FLASK WE ANTI-SLEEP (RENDER FLASH) ---
flask_app = Flask(__name__)
RENDER_URL = "https://vpn-paylayan-bot-zonex.onrender.com"

@flask_app.route("/")
def home():
    return "✅ Bot Çalışıyor!", 200

@flask_app.route("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}, 200

def self_ping():
    time.sleep(20)
    print("🔄 Anti-Sleep başlatıldı...")
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
            print("✅ Ping gönderildi: Bot canlı!")
        except Exception as e:
            print(f"❌ Ping hatası: {e}")
        time.sleep(300)  # Her 5 dakika

# --- LOGLAMA ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- AYARLAR ---
BOT_TOKEN = "7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y"
KURUCU_ID = 7523674506

# --- MONGODB BAGLANTISI ---
MONGODB_URI = "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1"
try:
    mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    mongo_db = mongo_client["vpn_bot"]
    kanallar_col = mongo_db["kanallar"]
    adminler_col = mongo_db["adminler"]
    paylas_col = mongo_db["paylas"]
    logger.info("✅ MongoDB bağlantı başarılı")
except Exception as e:
    logger.error(f"❌ MongoDB hatası: {e}")
    mongo_db = None

# --- SQLITE FALLBACK ---
def db_kur():
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS adminler (user_id INTEGER PRIMARY KEY, paylasim_sayisi INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kanallar (kanal_id TEXT PRIMARY KEY, kanal_link TEXT)''')
    conn.commit()
    conn.close()

db_kur()

# --- ADMIN KONTROLU ---
def admin_mi(user_id):
    if user_id == KURUCU_ID:
        return True
    
    # MongoDB'de ara
    if mongo_db:
        try:
            if adminler_col.find_one({"user_id": user_id}):
                return True
        except:
            pass
    
    # SQLite'de ara
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM adminler WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# --- KANAL EKLE/SIL (MONGODB + SQLITE) ---
def kanal_ekle(k_id, k_link):
    if mongo_db:
        try:
            kanallar_col.insert_one({"kanal_id": k_id, "kanal_link": k_link, "created_at": datetime.utcnow()})
        except:
            pass
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO kanallar (kanal_id, kanal_link) VALUES (?, ?)", (k_id, k_link))
    conn.commit()
    conn.close()

def kanal_sil(k_id):
    if mongo_db:
        try:
            kanallar_col.delete_one({"kanal_id": k_id})
        except:
            pass
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kanallar WHERE kanal_id = ?", (k_id,))
    conn.commit()
    conn.close()

def kanallar_al():
    kanallar = []
    
    if mongo_db:
        try:
            kanallar = [(k["kanal_id"], k["kanal_link"]) for k in kanallar_col.find()]
            if kanallar:
                return kanallar
        except:
            pass
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT kanal_id, kanal_link FROM kanallar")
    kanallar = cursor.fetchall()
    conn.close()
    return kanallar

# --- ADMIN EKLE/SIL (MONGODB + SQLITE) ---
def admin_ekle(admin_id):
    if mongo_db:
        try:
            adminler_col.insert_one({"user_id": admin_id, "paylasim_sayisi": 0, "created_at": datetime.utcnow()})
        except:
            pass
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO adminler (user_id) VALUES (?)", (int(admin_id),))
    conn.commit()
    conn.close()

def admin_sil(admin_id):
    if mongo_db:
        try:
            adminler_col.delete_one({"user_id": admin_id})
        except:
            pass
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM adminler WHERE user_id = ?", (int(admin_id),))
    conn.commit()
    conn.close()

def adminler_al():
    if mongo_db:
        try:
            adminler = [(a["user_id"],) for a in adminler_col.find()]
            if adminler:
                return adminler
        except:
            pass
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, paylasim_sayisi FROM adminler")
    adminler = cursor.fetchall()
    conn.close()
    return adminler

# --- START KOMUTU ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_mi(user_id):
        await update.message.reply_text("⛔ **Siz admin däl!** Bu boty dineje admin ulanyp biler.")
        return

    context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("🔗 VPN Paylaş", callback_data="menu_vpn_paylas")],
        [InlineKeyboardButton("📄 File Paylaş", callback_data="menu_dosya_paylas"),
         InlineKeyboardButton("📰 Habar Paylaş", callback_data="menu_haber_paylas")],
        [InlineKeyboardButton("➕ Kanal Goş", callback_data="menu_kanal_gos"), 
         InlineKeyboardButton("➖ Kanal Poz", callback_data="menu_kanal_poz")],
        [InlineKeyboardButton("📊 İstatistika", callback_data="menu_statistika")]
    ]
    
    if user_id == KURUCU_ID:
        keyboard.append([InlineKeyboardButton("👤 Admin Goş", callback_data="menu_admin_gos"),
                         InlineKeyboardButton("🗑️ Admin Poz", callback_data="menu_admin_poz")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎯 **VPN Bot Paneline Hoş Geldiniz!**\nHemme zady su yerden edip bilersiňiz:", reply_markup=reply_markup)

# --- MESAJ HANDLER ---
async def sms_gelende(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_mi(user_id): 
        return

    isleg = context.user_data.get('isleg')
    text = update.message.text.strip() if update.message.text else ""

    # KANAL EKLEME (akıllı)
    if "|" in text and ("-100" in text or text.split('|')[0].strip().replace('-', '').isdigit()):
        try:
            k_id, k_link = [x.strip() for x in text.split('|')]
            
            # Bot admin kontrolü
            try:
                test_msg = await context.bot.send_message(chat_id=k_id, text="⚙️ Test mesajı...")
                await context.bot.delete_message(chat_id=k_id, message_id=test_msg.message_id)
            except TelegramError:
                await update.message.reply_text(f"⚠️ **Nä sazlyk!** Bot `{k_id}` bod kanala admin däl **kanala post ugratma rugsady berilenok!** Başda admin ediň.")
                return

            kanal_ekle(k_id, k_link)
            await update.message.reply_text("✅ **Kanal Goşuldy!**\n\nMenü: /start")
            context.user_data.clear()
            return
        except Exception:
            await update.message.reply_text("❌ Ýalňyş! Örnek: `-1001234567 | https://t.me/kanal_linki` \n\nÇıkmak üçin: /start")
            return

    # ADMIN EKLEME
    if isleg == "AYAK_ADMIN_GOS" and user_id == KURUCU_ID:
        if not text.isdigit():
            await update.message.reply_text("❌ Diňeje ID oklaň!")
            return
        
        admin_ekle(int(text))
        await update.message.reply_text(f"✅ `{text}` Admin goşuldy!\n\nMenü: /start")
        context.user_data.clear()
        return

    # VPN LINKI ALMA
    elif isleg == "AYAK_VPN_LINK_AL":
        context.user_data['vpn_link'] = text
        context.user_data['isleg'] = "AYAK_VPN_DESC_AL"
        await update.message.reply_text("📝 Ugratmak isleýän vpniňizi ugradyň(Description):")
        return

    # VPN DESCRIPTION ALMA
    elif isleg == "AYAK_VPN_DESC_AL":
        context.user_data['vpn_desc'] = text
        context.user_data['secili_kanallar'] = []
        context.user_data['isleg'] = None
        context.user_data['paylas_tipi'] = 'vpn'
        await vpn_paneli_goster(update.message.reply_text, context)
        return

    # DOSYA PAYLAŞIMI
    elif isleg == "AYAK_DOSYA_AL":
        context.user_data['dosya_link'] = text
        context.user_data['isleg'] = "AYAK_DOSYA_DESC_AL"
        await update.message.reply_text("📝 File описание:")
        return

    elif isleg == "AYAK_DOSYA_DESC_AL":
        context.user_data['dosya_desc'] = text
        context.user_data['secili_kanallar'] = []
        context.user_data['isleg'] = None
        context.user_data['paylas_tipi'] = 'dosya'
        await vpn_paneli_goster(update.message.reply_text, context)
        return

    # HABER PAYLAŞIMI
    elif isleg == "AYAK_HABER_AL":
        context.user_data['haber_text'] = text
        context.user_data['secili_kanallar'] = []
        context.user_data['isleg'] = None
        context.user_data['paylas_tipi'] = 'haber'
        await vpn_paneli_goster(update.message.reply_text, context)
        return

# --- VPN PANELI (GENEL PAYLAŞ PANELI) ---
async def vpn_paneli_goster(gorkez_func, context: ContextTypes.DEFAULT_TYPE, edit=False):
    kanallar = kanallar_al()
    
    secili = context.user_data.get('secili_kanallar', [])
    hepsi_secili = len(secili) == len(kanallar) and len(kanallar) > 0
    paylas_tipi = context.user_data.get('paylas_tipi', 'vpn')

    ust_satir = [
        InlineKeyboardButton("✅ Hepsini saýla" if not hepsi_secili else "🟩 Hemmesi saýlandy", callback_data="v_HEMMESI"),
        InlineKeyboardButton("🚀 PAYLAŞ", callback_data="v_PAYLAS_ET")
    ]
    keyboard = [ust_satir]
    
    for k_id, k_link in kanallar:
        isaret = "🟢" if k_id in secili else "🔴"
        keyboard.append([InlineKeyboardButton(f"{isaret} {k_link}", callback_data=f"v_sec_{k_id}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Paylaşım içeriğini göster
    if paylas_tipi == 'vpn':
        vpn_link = context.user_data.get('vpn_link', '')
        vpn_desc = context.user_data.get('vpn_desc', '')
        post_gornus = f"👁️ **Post İçeriği:**\n\n`{vpn_link}`\n{vpn_desc}\n\n**Paýlaşmak isleyän kanalyňy saýla:**"
    elif paylas_tipi == 'dosya':
        dosya_link = context.user_data.get('dosya_link', '')
        dosya_desc = context.user_data.get('dosya_desc', '')
        post_gornus = f"📄 **File paýlaş:**\n\n`{dosya_link}`\n{dosya_desc}\n\n**Paýlaşmak isleyän kanalyňy saýla:**"
    else:  # haber
        haber_text = context.user_data.get('haber_text', '')
        post_gornus = f"📰 **Habar paýlaş:**\n\n{haber_text}\n\n**Paýlaşmak isleyän kanalyňy saýla:**"
    
    if edit:
        try: 
            await gorkez_func(text=post_gornus, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception: 
            pass
    else:
        await gorkez_func(text=post_gornus, reply_markup=reply_markup, parse_mode="Markdown")

# --- BUTONLAR (CALLBACK) ---
async def duwmeler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if not admin_mi(user_id): 
        return

    if data == "menu_kanal_gos":
        context.user_data['isleg'] = "AYAK_KANAL_GOS"
        await query.message.reply_text("👉 Goşmak isleýän kanlyň**ID'sini** ve **Linkini** şu formatta ýazyň:\n\n`-100123456789 | https://t.me/kanal_linki`")

    elif data == "menu_admin_gos" and user_id == KURUCU_ID:
        context.user_data['isleg'] = "AYAK_ADMIN_GOS"
        await query.message.reply_text("👤 Goşmak iselýän adamyň **Telegram ID'sini** yazın:")

    elif data == "menu_vpn_paylas":
        context.user_data['isleg'] = "AYAK_VPN_LINK_AL"
        await query.message.reply_text("🔗 Kanallara paýlaşmak isleýän **VPN Linkini** yazın:")

    elif data == "menu_dosya_paylas":
        context.user_data['isleg'] = "AYAK_DOSYA_AL"
        await query.message.reply_text("📄 Fileyň **indirme linkini** yazın:")

    elif data == "menu_haber_paylas":
        context.user_data['isleg'] = "AYAK_HABER_AL"
        await query.message.reply_text("📰 **Ibermek isleýän habery** yazyň:")

    elif data == "menu_kanal_poz" and user_id == KURUCU_ID:
        kanallar = kanallar_al()
        if not kanallar:
            await query.message.reply_text("📭 Kanal tapylmady.")
            return
        keyboard = [[InlineKeyboardButton(f"❌ {k[1]}", callback_data=f"goni_kpoz_{k[0]}")] for k in kanallar]
        await query.message.reply_text("🗑️ Pozmak isleýan kanaly saýlaň:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("goni_kpoz_") and user_id == KURUCU_ID:
        k_id = data.replace("goni_kpoz_", "")
        kanal_sil(k_id)
        await query.message.edit_text("✅ Kanal pozuldy! /start")

    elif data == "menu_admin_poz" and user_id == KURUCU_ID:
        adminler = adminler_al()
        if not adminler:
            await query.message.reply_text("👥 admin tapylmady.")
            return
        keyboard = [[InlineKeyboardButton(f"🗑️ Admin: {a[0]}", callback_data=f"goni_apoz_{a[0]}")] for a in adminler]
        await query.message.reply_text("Silmek istediğiniz admini seçin:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("goni_apoz_") and user_id == KURUCU_ID:
        a_id = data.replace("goni_apoz_", "")
        admin_sil(int(a_id))
        await query.message.edit_text(f"✅ Admin {a_id} silindi! /start")

    elif data == "menu_statistika":
        kanallar = kanallar_al()
        adminler = adminler_al()
        
        txt = f"📊 **BOT İSTATİSTİKASI**\n\n📢 Hemme kanal: **{len(kanallar)}**\n\n👥 **Adminler:**\n"
        for adm in adminler:
            txt += f"├─ Admin ID (`{adm[0]}`)\n"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif data == "v_HEMMESI" or data.startswith("v_sec_") or data == "v_PAYLAS_ET":
        kanallar = kanallar_al()
        tum_kanal_idleri = [x[0] for x in kanallar]
        
        secili = context.user_data.get('secili_kanallar', [])
        
        if data == "v_HEMMESI":
            if len(secili) == len(tum_kanal_idleri):
                context.user_data['secili_kanallar'] = []
            else:
                context.user_data['secili_kanallar'] = tum_kanal_idleri.copy()
            await vpn_paneli_goster(query.message.edit_text, context, edit=True)

        elif data.startswith("v_sec_"):
            k_id = data.replace("v_sec_", "")
            if k_id in secili: 
                secili.remove(k_id)
            else: 
                secili.append(k_id)
            context.user_data['secili_kanallar'] = secili
            await vpn_paneli_goster(query.message.edit_text, context, edit=True)
            
        elif data == "v_PAYLAS_ET":
            paylas_tipi = context.user_data.get('paylas_tipi', 'vpn')
            hedef_kanallar = context.user_data.get('secili_kanallar', [])
            
            if not hedef_kanallar:
                await query.message.reply_text("❌ Birinji kanllary saýlaň!")
                return
            
            sowly = 0
            hata = 0
            
            if paylas_tipi == 'vpn':
                vpn_link = context.user_data.get('vpn_link')
                vpn_desc = context.user_data.get('vpn_desc', '')
                sonky_sms = f"`{vpn_link}`\n{vpn_desc}"
            elif paylas_tipi == 'dosya':
                dosya_link = context.user_data.get('dosya_link')
                dosya_desc = context.user_data.get('dosya_desc', '')
                sonky_sms = f"`{dosya_link}`\n{dosya_desc}"
            else:  # haber
                sonky_sms = context.user_data.get('haber_text')
            
            for cid in hedef_kanallar:
                try:
                    await context.bot.send_message(chat_id=cid, text=sonky_sms, parse_mode="Markdown")
                    sowly += 1
                except Exception:
                    hata += 1
            
            # MongoDB'ye kaydet
            if mongo_db:
                try:
                    paylas_col.insert_one({
                        "user_id": user_id,
                        "type": paylas_tipi,
                        "kanal_sayisi": sowly,
                        "created_at": datetime.utcnow()
                    })
                except:
                    pass
            
            await query.message.edit_text(f"🚀 **Paylaşım Tamamlandy!**\n\n✅ Tamamlandy: {sowly} kanal.\n❌ Na sazlyk: {hata} kanal.")
            context.user_data.clear()

# --- BOT ÇALIŞTIR ---
def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(duwmeler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sms_gelende))
    application.add_handler(CommandHandler("start", start))
    application.run_polling(close_loop=False)

if __name__ == '__main__':
    # Flask Keep-Alive thread'i
    threading.Thread(target=self_ping, daemon=True).start()
    
    # Flask server (Render port'u)
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port, use_reloader=False), daemon=True).start()
    
    print("✅ Flask Server ve Bot Render için hazır!")
    run_telegram_bot()
    
