import logging
import os
import time
import threading
import requests
from flask import Flask  # Render üçin gerek
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from pymongo import MongoClient  # MongoDB üçin goşuldy

# --- FLASK WE ANTI-SLEEP (RENDER UKLAMAZLYK GURLUŞY) ---
flask_app = Flask(__name__)
# Render sahypaňyzyň durnukly linki
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
        time.sleep(300) # Her 5 minutdan özi özüne jaň edip uykudan açýar

# Loglama Sazlamalary
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ESASY SAZLAMALAR ---
BOT_TOKEN = "7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y"
KURUCU_ID = 7523674506  

# --- MONGODB BAGLANYŞYGY (TÄZELENDI) ---
MONGO_URI = "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/vpn_telegram_bot?retryWrites=true&w=majority&appName=Cluster1" 

mongo_client = MongoClient(MONGO_URI)
db = mongo_client['vpn_telegram_bot'] # Maglumat binasynyň ady
db_adminler = db['adminler']         # Adminler tablisasy
db_kanallar = db['kanallar']         # Kanallar tablisasy

# --- ÝARDÝMCY FUNKSIÝALAR ---
def admin_mi(user_id):
    if user_id == KURUCU_ID:
        return True
    res = db_adminler.find_one({"user_id": int(user_id)})
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
            
            # Botuň kanaldaky rugsady barlanylýar
            try:
                test_msg = await context.bot.send_message(chat_id=k_id, text="⚙️ Barlag sms...")
                await context.bot.delete_message(chat_id=k_id, message_id=test_msg.message_id)
            except TelegramError:
                await update.message.reply_text(f"⚠️ **Duýduryş!** Bot `{k_id}` kanalynda admin däl ýa-da **Habarlara Erşmek Rugsady ÝOK!** Ilki admin ediň.")
                return

            # MongoDB-ä goşmak
            db_kanallar.update_one(
                {"kanal_id": k_id},
                {"$set": {"kanal_link": k_link}},
                upsert=True
            )
            
            await update.message.reply_text("✅ **Kanal üstünlikli goşuldy!**\n\nBaş Menu: /start")
            context.user_data.clear()
            return
        except Exception:
            await update.message.reply_text("❌ Nädogry format! Nusga: `-1001234567 | https://t.me/link` \n\nÝatyrmak üçin: /start")
            return

    # 2. ADMİN GOŞMAK
    if isleg == "AYAK_ADMIN_GOS" and user_id == KURUCU_ID:
        if not text.isdigit():
            await update.message.reply_text("❌ ID diňe sanlardan ybarat bolmalydyr!")
            return
        
        db_adminler.update_one(
            {"user_id": int(text)},
            {"$setOnInsert": {"paylasim_sayisi": 0}},
            upsert=True
        )
        await update.message.reply_text(f"✅ `{text}` ID-li ulanyjy Admin edildi!\n\nBaş Menu: /start")
        context.user_data.clear()
        return

    # 3. VPN LİNKINI ALMAK WE DESCRIPTION SORAMAK
    elif isleg == "AYAK_VPN_LINK_AL":
        context.user_data['vpn_link'] = text
        context.user_data['isleg'] = "AYAK_VPN_DESC_AL"
        await update.message.reply_text("📝 Indi bolsa şol VPN linkiniň yzyndan goşuljak **Düşündiriş tekstini (Description)** ýazyň:")
        return

    # 4. DESCRIPTION ALMAK WE PANEL GÖRKEZMEK
    elif isleg == "AYAK_VPN_DESC_AL":
        context.user_data['vpn_desc'] = text
        context.user_data['secili_kanallar'] = []
        context.user_data['isleg'] = None
        await vpn_paneli_goster(update.message.reply_text, context)
        return

# --- VPN PAÝLAŞYŞ PANELY ---
async def vpn_paneli_goster(gorkez_func, context: ContextTypes.DEFAULT_TYPE, edit=False):
    kanallar = list(db_kanallar.find({}, {"_id": 0, "kanal_id": 1, "kanal_link": 1}))
    
    secili = context.user_data.get('secili_kanallar', [])
    hepsi_secili = len(secili) == len(kanallar) and len(kanallar) > 0

    ust_satir = [
        InlineKeyboardButton("✅ Ählisini Saýla" if not hepsi_secili else "🟩 Ählisi Saýlandy", callback_data="v_HEPSI"),
        InlineKeyboardButton("🚀 PAÝLAŞ", callback_data="v_PAYLAS_ET")
    ]
    keyboard = [ust_satir]
    
    for k in kanallar:
        k_id = k['kanal_id']
        k_link = k['kanal_link']
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

# --- DÜWMELERIŇ IŞLEÝIŞI (CALLBACK QUERIES) ---
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
        kanallar = list(db_kanallar.find({}, {"_id": 0, "kanal_id": 1, "kanal_link": 1}))
        if not kanallar:
            await query.message.reply_text("📭 Hasaba alnan kanal tapylmady.")
            return
        keyboard = [[InlineKeyboardButton(f"❌ {k['kanal_link']}", callback_data=f"goni_kpoz_{k['kanal_id']}")] for k in kanallar]
        await query.message.reply_text("🗑️ Silmek islan kanalyňyzy saýlaň (Diňe Gurujy):", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("goni_kpoz_") and user_id == KURUCU_ID:
        k_id = data.replace("goni_kpoz_", "")
        db_kanallar.delete_one({"kanal_id": k_id})
        await query.message.edit_text("✅ Kanal maglumat binasyndan pozuldy! /start")

    elif data == "menu_admin_poz" and user_id == KURUCU_ID:
        adminler = list(db_adminler.find({}, {"_id": 0, "user_id": 1}))
        if not adminler:
            await query.message.reply_text("👥 Admin tapylmady.")
            return
        keyboard = [[InlineKeyboardButton(f"🗑️ Admin: {a['user_id']}", callback_data=f"goni_apoz_{a['user_id']}")] for a in adminler]
        await query.message.reply_text("Silmek isleýän adminiňizi saýlaň:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("goni_apoz_") and user_id == KURUCU_ID:
        a_id = data.replace("goni_apoz_", "")
        db_adminler.delete_one({"user_id": int(a_id)})
        await query.message.edit_text(f"✅ {a_id} ID-li admin pozuldy! /start")

    elif data == "menu_statistika":
        jemi_kanal = db_kanallar.count_documents({})
        admin_list = list(db_adminler.find({}, {"_id": 0, "user_id": 1, "paylasim_sayisi": 1}))
        
        txt = f"📊 **BOT STATİSTİKASY**\n\n📢 Botuň admin bolan jemi kanallary: **{jemi_kanal}**\n\n👥 **Adminleriň paýlaşyk sany:**\n"
        for adm in admin_list:
            txt += f"├─ Admin ID (`{adm['user_id']}`): {adm.get('paylasim_sayisi', 0)} gezek paýlaşdy.\n"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif data == "v_HEPSI" or data.startswith("v_sec_") or data == "v_PAYLAS_ET":
        tum_kanal_idleri = [x['kanal_id'] for x in db_kanallar.find({}, {"kanal_id": 1})]
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
                    
            db_adminler.update_one(
                {"user_id": user_id},
                {"$inc": {"paylasim_sayisi": 1}},
                upsert=True
            )
            
            await query.message.edit_text(f"🚀 **Paýlaşyk tamamlandy!**\n\n✅ Şowly ugradylan: {sowly} kanal.\n❌ Şowsuz (Rugsatsyz): {hata} kanal.")
            context.user_data.clear()

# --- MAIN RUNNER FUNCTION ---
def run_telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(duwmeler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sms_gelende))
    application.add_handler(CommandHandler("start", start))
    application.run_polling(close_loop=False)

if __name__ == '__main__':
    # Flask-yň arka planda uykudan açyjy gurluşy
    threading.Thread(target=self_ping, daemon=True).start()
    
    # Flask web serverini parallel potokda işe girizýäris (Render Porty üçin)
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port, use_reloader=False), daemon=True).start()
    
    print("Web Server we Bot Render we MongoDB üçin doly taýýar edildi...")
    run_telegram_bot()
    
