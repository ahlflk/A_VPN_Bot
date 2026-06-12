# # All-in-One (VPN_APK) Telegram VIP Management Bot
# Py By @AHLFLK2025

# ==========================================
# 1. CONFIGURATION & CORE BOT SETUP
# ==========================================
import os
import re
import sqlite3
import requests
from threading import Thread
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TGC_ID")) if os.environ.get("TGC_ID") else None
SCRIPT_URL = os.environ.get("SCRIPT_URL")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
vip_temp_data = {} 

ADMIN_BUTTONS = [
    "➕ Add VPN APK VIP", "✏️ Edit VPN APK", "🗑 Delete VPN APK", "🌐 View All VIPs",
    "👤 Create Reseller", "📊 Reseller List", "✏️ Edit Reseller", "🗑 Delete Reseller",
    "💰 My Balance"
]

RESELLER_BUTTONS = [
    "➕ Add VPN APK VIP", "✏️ Edit VPN APK", "🗑 Delete VPN APK", "🔑 My VIP Users", "💰 My Balance"
]

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return "Bot is running", 200

# ==========================================
# 2. DATABASE INITIALIZATION & SHEET SYNC
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_keys (
                target_id TEXT,
                key_string TEXT,
                vpn_key TEXT PRIMARY KEY,
                unit_val INTEGER,
                created_at TEXT,
                added_by TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resellers (
                reseller_id TEXT PRIMARY KEY,
                username TEXT,
                credits INTEGER,
                created_by TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

def pull_data_from_google_sheet():
    if not SCRIPT_URL: return
    try:
        res = requests.get(SCRIPT_URL, timeout=15)
        if res.status_code == 200:
            data_list = res.json()
            if isinstance(data_list, dict) and "error" in data_list: return
            
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            
            existing_vip_owners = {}
            cursor.execute("SELECT vpn_key, added_by FROM auth_keys WHERE added_by IS NOT NULL")
            for r in cursor.fetchall():
                existing_vip_owners[r[0]] = r[1]
                
            cursor.execute("DELETE FROM auth_keys")
            cursor.execute("DELETE FROM resellers")
            
            for row in data_list:
                t_id = row.get("Users")
                k_str = row.get("Name") or ""
                key_apk = row.get("Key") or ""
                c_at = row.get("Start") or ""
                m_val = row.get("Month") or 0
                
                if not t_id or t_id.strip() == "":
                    if "_Reseller" in str(k_str): t_id = "0" 
                    else: continue
                
                t_id = str(t_id).strip()

                if "_Reseller" in str(k_str):
                    try:
                        clean_name = str(k_str).replace("_Reseller", "").strip()
                        token_val = int(float(key_apk)) if '.' in str(key_apk) else int(key_apk)
                        cursor.execute("INSERT OR REPLACE INTO resellers VALUES (?, ?, ?, ?)", 
                                       (t_id, clean_name, token_val, str(ADMIN_ID)))
                    except Exception as e: pass
                
                elif key_apk and key_apk != "RESELLER_ACCOUNT":
                    try:
                        clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 1
                        owner_id = existing_vip_owners.get(str(key_apk).strip(), str(ADMIN_ID))
                        cursor.execute(
                            "INSERT OR REPLACE INTO auth_keys (target_id, key_string, vpn_key, unit_val, created_at, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                            (t_id, str(k_str).strip(), str(key_apk).strip(), clean_months, str(c_at).strip(), str(owner_id))
                        )
                    except Exception as e: pass
                        
            conn.commit()
            conn.close()
    except Exception as e: pass

def push_to_google_sheet(action, users, name, key, start, month, is_reseller_mode=False):
    if not SCRIPT_URL: return False
    payload = {
        "action": "sync_reseller" if is_reseller_mode else action,
        "users": str(users),
        "name": str(name),
        "key": str(key),
        "start": str(start),
        "month": int(month)
    }
    try:
        res = requests.post(SCRIPT_URL, json=payload, timeout=15)
        return res.status_code == 200
    except:
        return False

# ==========================================
# 3. HELPER FUNCTIONS & AUTHENTICATION
# ==========================================
def is_admin(user_id):
    return int(user_id) == ADMIN_ID

def is_reseller(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT reseller_id FROM resellers WHERE reseller_id = ?", (str(user_id),))
        return cursor.fetchone() is not None
    except: return False
    finally: conn.close()

def get_reseller_tokens(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT credits FROM resellers WHERE reseller_id = ?", (str(user_id),))
        row = cursor.fetchone()
        return row[0] if row else 0
    except: return 0
    finally: conn.close()

def is_vpn_key_exists(vpn_key):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT vpn_key FROM auth_keys WHERE vpn_key = ?", (str(vpn_key).strip(),))
        return cursor.fetchone() is not None
    except: return False
    finally: conn.close()

def check_vip_status_by_tg(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key_string, vpn_key, unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        rows = cursor.fetchall()
        if rows:
            last_row = rows[-1]
            exp = get_expired_date_string(last_row[3], last_row[2])
            
            is_expired = False
            if exp != "သက်တမ်းမရှိပါ":
                try:
                    exp_date = datetime.strptime(exp, "%d/%m/%Y")
                    if datetime.now() > exp_date:
                        is_expired = True
                except: pass
                
            return True, exp, last_row[1], is_expired
        return False, "No VPN Account Locked", "မရှိပါ", True
    except: return False, "စစ်ဆေး၍မရပါ", "မရှိပါ", True
    finally: conn.close()

def get_expired_date_string(created_str, months_val):
    try:
        if not created_str or created_str.strip() == "":
            created_str = datetime.now().strftime("%d/%m/%Y")
        if "-" in created_str:
            dt = datetime.strptime(created_str.strip(), "%d/%m/%Y")
        elif "/" in created_str:
            dt = datetime.strptime(created_str.strip(), "%d/%m/%Y")
        else:
            dt = datetime.now()
        exp = dt + timedelta(days=int(months_val) * 30)
        return exp.strftime("%d/%m/%Y")
    except Exception:
        return "သက်တမ်းမရှိပါ"

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_admin(user_id):
        markup.add(*[types.KeyboardButton(b) for b in ADMIN_BUTTONS])
    elif is_reseller(user_id):
        markup.add(*[types.KeyboardButton(b) for b in RESELLER_BUTTONS])
    else:
        markup.add(types.KeyboardButton("💰 My Balance"))
    return markup

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

# ==========================================
# 4. TELEGRAM BOT HANDLERS & COMMANDS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    pull_data_from_google_sheet()
    
    try:
        bot_info = bot.get_me()
        bot_name = bot_info.first_name
    except:
        bot_name = "VPN_VIP_Bot"
        
    is_vip, exp_status, vpn_key, is_expired = check_vip_status_by_tg(user_id)
    first_name = message.from_user.first_name
    account_status = "Normal User 🙂"
    tokens_line = ""
    
    if is_admin(user_id): 
        account_status = "Main Admin 👑"
        if not is_vip: exp_status = "Main Admin Account (No VPN)"
    elif is_reseller(user_id):
        account_status = "Reseller Staff 💼"
        tokens = get_reseller_tokens(user_id)
        tokens_line = f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n"
        if not is_vip: exp_status = "Reseller Account (No VPN)"

    welcome_text = f"👋 <b>{bot_name} မှ ကြိုဆိုပါတယ်ဗျာ!</b>\n\n" \
                   f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                   f"👑 အဆင့်အတန်း: <b>{account_status}</b>\n" \
                   f"👤 အမည်: <b>{first_name}</b>\n" \
                   f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                   f"{tokens_line}" \
                   f"🔑 Last VPN Key: <code>{vpn_key}</code>\n" \
                   f"⏳ VPN သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>\n\n" \
                   f"အောက်ပါ Panel Keyboard ကို အသုံးပြုပြီး ထိန်းချုပ်နိုင်ပါသည်။"
                   
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text in ADMIN_BUTTONS or msg.text in RESELLER_BUTTONS or msg.text == "💰 My Balance")
def handle_menu_clicks(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "💰 My Balance":
        pull_data_from_google_sheet()
        is_vip, exp_status, vpn_key, is_expired = check_vip_status_by_tg(user_id)
        first_name = message.from_user.first_name
        
        if is_admin(user_id):
            admin_text = f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                         f"👑 အဆင့်အတန်း: <b>Admin 👑</b>\n" \
                         f"👤 အမည်: <b>{first_name}</b>\n" \
                         f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                         f"🔑 Last VPN Key: <code>{vpn_key}</code>\n" \
                         f"⏳ VPN သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>"
            bot.reply_to(message, admin_text, parse_mode="HTML")
            
        elif is_reseller(user_id):
            tokens = get_reseller_tokens(user_id)
            reseller_text = f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                            f"👑 အဆင့်အတန်း: <b>Reseller Staff 💼</b>\n" \
                            f"👤 အမည်: <b>{first_name}</b>\n" \
                            f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                            f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n" \
                            f"🔑 Last VPN Key: <code>{vpn_key}</code>\n" \
                            f"⏳ VPN သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>"
            
            if tokens <= 0:
                reseller_text += "\n\n🚫 <b>သင့်ရဲ့ Reseller Token ကုန်ဆုံးသွားပါပြီဗျာ။</b>\n\nလုပ်ဆောင်ချက်များကို ဆက်လက်အသုံးပြုနိုင်ရန်အတွက် ကျေးဇူးပြု၍ Admin ထံသို့ ဆက်သွယ်ပြီး Token ဖြည့်တင်းပေးပါရန်।"
                bot.reply_to(message, reseller_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            else:
                bot.reply_to(message, reseller_text, parse_mode="HTML")
                
        else:
            user_text = f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                        f"👑 အဆင့်အတန်း: <b>Normal User 🙂</b>\n" \
                        f"👤 အမည်: <b>{first_name}</b>\n" \
                        f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                        f"🔑 Last VPN Key: <code>{vpn_key}</code>\n" \
                        f"⏳ VPN သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>"
            
            if is_expired or not is_vip:
                user_text += "\n\n⚠️ <b>သင့်ရဲ့ VPN VIP အကောင့် သက်တမ်းကုန်ဆုံးသွားပါပြီ။</b>\n\nသက်တမ်း ဆက်တိုးလိုပါက သို့မဟုတ် အကောင့်အသစ်ဝယ်ယူလိုပါက အောက်ပါ Admin ထံသို့ တိုက်ရိုက်ဆက်သွယ်နိုင်ပါသည်ဗျာ।"
                bot.reply_to(message, user_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
            else:
                bot.reply_to(message, user_text, parse_mode="HTML")
        return

    if not (is_admin(user_id) or is_reseller(user_id)): return

    if is_reseller(user_id):
        tokens = get_reseller_tokens(user_id)
        if tokens <= 0:
            contact_text = f"🚫 <b>လုပ်ဆောင်ချက်ကို ငြင်းပယ်လိုက်သည်။</b>\n\nသင့်တွင် လက်ရှိ Token ကုန်နေသဖြင့် မည်သည့် VIP Feature ကိုမျှ သုံးခွင့်မရှိသေးပါ။\nကျေးဇူးပြု၍ Admin ထံ ဆက်သွယ်ပါဗျာ။"
            return bot.reply_to(message, contact_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")

    if text == "➕ Add VPN APK VIP":
        bot.reply_to(message, "⚙️ <b>[အဆင့် ၁]</b> VIP ပေးမည့်သူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_VIP_ID"
        vip_temp_data[user_id] = {}
        
    elif text == "🌐 View All VIPs":
        if is_admin(user_id): admin_view_all_keys(message)
        
    elif text == "🔑 My VIP Users":
        if is_reseller(user_id): reseller_view_my_vips(message)
        
    elif text == "✏️ Edit VPN APK":
        bot.reply_to(message, "✏️ ပြင်ဆင်လိုသည့် အသုံးပြုသူ၏ <b>VPN APK ID (Key)</b> ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_EDIT_VPN_KEY"
        vip_temp_data[user_id] = {}
        
    elif text == "🗑 Delete VPN APK":
        bot.reply_to(message, "🗑 ဖျက်ထုတ်လိုသည့် <b>VPN APK ID (Key)</b> ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_DEL_VIP_KEY"

    elif is_admin(user_id):
        if text == "👤 Create Reseller":
            bot.reply_to(message, "💼 ဖန်တီးမည့် Reseller ၏ <b>Telegram ID</b> ကို ပို့ပေးပါ:", parse_mode="HTML")
            user_states[user_id] = "AWAIT_RS_ID"
        elif text == "📊 Reseller List": view_all_resellers(message)
        elif text == "✏️ Edit Reseller":
            bot.reply_to(message, "✏️ ပြင်ဆင်မည့် Reseller ၏ <b>Telegram ID</b> ကို ပို့ပေးပါ:", parse_mode="HTML")
            user_states[user_id] = "AWAIT_EDIT_RS_ID"
        elif text == "🗑 Delete Reseller":
            bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် Reseller ၏ <b>Telegram ID</b> ကို ပို့ပေးပါ:", parse_mode="HTML")
            user_states[user_id] = "AWAIT_DEL_RS_ID"

# ==========================================
# 5. CONVERSATION STATE MACHINE (FLUID INPUTS)
# ==========================================
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) is not None)
def handle_fluid_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text.strip()

    if state == "AWAIT_VIP_ID":
        vip_temp_data[user_id]["telegram_id"] = text
        bot.reply_to(message, "👤 <b>[အဆင့် ၂]</b> အသုံးပြုမည့်သူ၏ <b>အမည် (Name)</b> ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_VIP_NAME"
        
    elif state == "AWAIT_VIP_NAME":
        vip_temp_data[user_id]["name"] = text
        bot.reply_to(message, "🔑 <b>[အဆင့် ၃]</b> ၎င်း၏ <b>VPN APK ID (Key)</b> ကို ထည့်သွင်းပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_VIP_KEY"

    elif state == "AWAIT_VIP_KEY":
        if is_vpn_key_exists(text):
            user_states[user_id] = None
            return bot.reply_to(message, f"❌ ဤ VPN APK ID: <code>{text}</code> သည် ရှိပြီးသားဖြစ်နေပါသည်။\n\nသက်တမ်းတိုးရန် <b>✏️ Edit VPN APK</b> စနစ်ကို အသုံးပြုပေးပါ။", parse_mode="HTML")
            
        vip_temp_data[user_id]["key"] = text
        bot.reply_to(message, "📅 <b>[အဆင့် ၄]</b> အသုံးပြုမည့် <b>လအရေအတွက်</b> အား ဂဏန်းရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_VIP_MONTH"

    elif state == "AWAIT_VIP_MONTH":
        if not text.isdigit(): return bot.reply_to(message, "❌ ဂဏန်းသီးသန့်သာ ရိုက်ထည့်ပေးပါ:", parse_mode="HTML")
        
        target_id = vip_temp_data[user_id]["telegram_id"]
        name = vip_temp_data[user_id]["name"]
        key = vip_temp_data[user_id]["key"]
        month = int(text)
        start_date = datetime.now().strftime("%d/%m/%Y")

        if is_reseller(user_id):
            current_tokens = get_reseller_tokens(user_id)
            if current_tokens < month:
                user_states[user_id] = None
                insufficient_text = f"🚫 သင့်တွင် <b>Tokens</b> မလုံလောက်တော့ပါ။\n" \
                                    f"🪙 သင့်တွင် <b>({current_tokens} Tokens)</b> ပဲ ရှိပါသည်။\n\n" \
                                    f"လုပ်ဆောင်ချက် ဆက်လက်ပြုလုပ်ရန် (သို့မဟုတ်) တိုကင်ထည့်သွင်းရန် Admin ကို ဆက်သွယ်ပေးပါရန်।"
                return bot.reply_to(message, insufficient_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")

        bot.reply_to(message, "⏳ Google Sheet သို့ VIP ဒေတာများ ချိတ်ဆက်သိမ်းဆည်းနေပါသည်...", parse_mode="HTML")
        
        payload = {
            "action": "sync",
            "users": str(target_id),
            "name": str(name),
            "key": str(key),
            "start": str(start_date),
            "month": int(month),
            "added_by": str(user_id)
        }
        
        try:
            res = requests.post(SCRIPT_URL, json=payload, timeout=15)
            sheet_success = (res.status_code == 200)
        except:
            sheet_success = False

        if sheet_success:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO auth_keys (target_id, key_string, vpn_key, unit_val, created_at, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                           (target_id, name, key, month, start_date, str(user_id)))
            
            if is_reseller(user_id):
                cursor.execute("UPDATE resellers SET credits = credits - ? WHERE reseller_id = ? AND credits >= ?", (month, str(user_id), month))
                
            conn.commit()
            conn.close()
            
            pull_data_from_google_sheet()

            success_text = f"✅ <b>VPN APK VIP အား အောင်မြင်စွာ စာရင်းသွင်းပြီးပါပြီ။</b>\n\n" \
                           f"🔑 APK Key: <code>{key}</code>\n"
            
            if is_reseller(user_id):
                updated_tokens = get_reseller_tokens(user_id)
                success_text += f"📊 Sheets နှင့် Token Balance ထဲမှ <b>({month} Tokens)</b> နှုတ်ယူပြီးပါပြီ။\n" \
                                f"🪙 သင့်လက်ရှိ Token <b>({updated_tokens} Tokens)</b> ဖြစ်ပါသည်။"
            else:
                success_text += f"📊 Sheets ထဲသို့ VIP ဒေတာများ ထည့်သွင်းပြီးပါပြီ။"
            
            bot.send_message(user_id, success_text, parse_mode="HTML")
            
        else:
            bot.send_message(user_id, "❌ Sheet သို့ ဒေတာပေးပို့ခြင်း မအောင်မြင်ပါ။", parse_mode="HTML")
        user_states[user_id] = None

    elif state == "AWAIT_EDIT_VPN_KEY":
        vip_temp_data[user_id]["key"] = text
        bot.reply_to(message, "✏️ <b>[ပြင်ဆင်ခြင်း]</b> ပြောင်းလဲတွဲဖက်မည့် အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_EDIT_VIP_TG"
        
    elif state == "AWAIT_EDIT_VIP_TG":
        vip_temp_data[user_id]["telegram_id"] = text
        bot.reply_to(message, "✏️ <b>[ပြင်ဆင်ခြင်း]</b> အမည်သစ်ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_EDIT_VIP_NAME"

    elif state == "AWAIT_EDIT_VIP_NAME":
        vip_temp_data[user_id]["name"] = text
        bot.reply_to(message, "✏️ <b>[ပြင်ဆင်ခြင်း]</b> ထပ်မံတိုးမြှင့် ပေါင်းထည့်မည့် <b>လအရေအတွက်</b> ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
        user_states[user_id] = "AWAIT_EDIT_VIP_MONTH"

    elif state == "AWAIT_EDIT_VIP_MONTH":
        if not text.isdigit(): return bot.reply_to(message, "❌ ဂဏန်းသီးသန့်သာ ရိုက်ထည့်ပါ:", parse_mode="HTML")
        
        target_id = vip_temp_data[user_id]["telegram_id"]
        name = vip_temp_data[user_id]["name"]
        key = vip_temp_data[user_id]["key"]
        month = int(text)
        start_date = datetime.now().strftime("%d/%m/%Y")

        bot.reply_to(message, "⏳ Google Sheet တွင် ရှာဖွေပေါင်းထည့်နေပါသည်...", parse_mode="HTML")
        if push_to_google_sheet("sync", target_id, name, key, start_date, month):
            pull_data_from_google_sheet()
            bot.send_message(user_id, "✅ VPN APK VIP သက်တမ်းလများ ထပ်ပေါင်းပြင်ဆင်မှု အောင်မြင်ပါသည်။", parse_mode="HTML")
        else:
            bot.send_message(user_id, "❌ ပြင်ဆင်မှု မအောင်မြင်ပါ။", parse_mode="HTML")
        user_states[user_id] = None

    elif state == "AWAIT_DEL_VIP_KEY":
        if push_to_google_sheet("delete", "", "", text, "", 0):
            pull_data_from_google_sheet()
            bot.send_message(user_id, f"✅ VPN APK Key: <code>{text}</code> အား ရှင်းထုတ်ပြီးပါပြီ။", parse_mode="HTML")
        else: bot.send_message(user_id, "❌ ဖျက်ထုတ်မှု မအောင်မြင်ပါ။", parse_mode="HTML")
        user_states[user_id] = None

    elif is_admin(user_id):
        if state == "AWAIT_RS_ID":
            reseller_temp_data[user_id] = {"id": text}
            bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller ၏ <b>အမည် (Name)</b> ကို ထည့်ပေးပါ:", parse_mode="HTML")
            user_states[user_id] = "AWAIT_RS_UNAME"
            
        elif state == "AWAIT_RS_UNAME":
            reseller_temp_data[user_id]["uname"] = f"{text}_Reseller"
            bot.reply_to(message, "🪙 သတ်မှတ်ပေးမည့် သို့မဟုတ် ထပ်ပေါင်းထည့်မည့် <b>Token Credit</b> အရေအတွက်:", parse_mode="HTML")
            user_states[user_id] = "AWAIT_RS_CREDITS"
            
        elif state == "AWAIT_RS_CREDITS":
            if not text.isdigit(): return
            r_id = reseller_temp_data[user_id]["id"]
            uname = reseller_temp_data[user_id]["uname"]
            creds = int(text)
            
            if push_to_google_sheet("sync_reseller", r_id, uname, "RESELLER_ACCOUNT", "", creds, is_reseller_mode=True):
                pull_data_from_google_sheet()
                bot.reply_to(message, f"✅ <b>Reseller အား အောင်မြင်စွာ စာရင်းသွင်း/တိုကင်ပေါင်းထည့်ပြီးပါပြီ။</b>", parse_mode="HTML")
            user_states[user_id] = None

        elif state == "AWAIT_EDIT_RS_ID":
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT username, credits FROM resellers WHERE reseller_id = ?", (text,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                user_states[user_id] = None
                return bot.reply_to(message, "❌ ဤ Reseller ID ကို စာရင်းထဲမှာ ရှာမတွေ့ပါ။", parse_mode="HTML")
                
            reseller_temp_data[user_id] = {"id": text}
            bot.reply_to(message, f"✏️ Reseller (<code>{text}</code>) အတွက် <b>အမည်သစ်</b> ထည့်ပေးပါ (ယခင်: {row[0]}):", parse_mode="HTML")
            user_states[user_id] = "AWAIT_EDIT_RS_UNAME"

        elif state == "AWAIT_EDIT_RS_UNAME":
            reseller_temp_data[user_id]["uname"] = f"{text}_Reseller"
            bot.reply_to(message, "🪙 ၎င်း Reseller အတွက် ပြောင်းလဲသတ်မှတ်မည့် <b>တိုကင်အသစ် (Token Total)</b> ကို ရိုက်ထည့်ပါ:", parse_mode="HTML")
            user_states[user_id] = "AWAIT_EDIT_RS_CREDITS"

        elif state == "AWAIT_EDIT_RS_CREDITS":
            if not text.isdigit(): return bot.reply_to(message, "❌ ဂဏန်းသာ ရိုက်ထည့်ပါ:", parse_mode="HTML")
            r_id = reseller_temp_data[user_id]["id"]
            uname = reseller_temp_data[user_id]["uname"]
            creds = int(text)
            
            if push_to_google_sheet("sync_reseller", r_id, uname, "RESELLER_ACCOUNT", "", creds, is_reseller_mode=True):
                pull_data_from_google_sheet()
                bot.reply_to(message, f"✅ Reseller ID: <code>{r_id}</code> အား ဒေတာပြင်ဆင်ပြီး (Sync)လုပ်ပြီးပါပြီ။", parse_mode="HTML")
            else:
                bot.reply_to(message, "❌ Sheet ပြင်ဆင်မှု မအောင်မြင်ပါ။", parse_mode="HTML")
            user_states[user_id] = None

        elif state == "AWAIT_DEL_RS_ID":
            if push_to_google_sheet("delete", text, "", "RESELLER_ACCOUNT", "", 0):
                pull_data_from_google_sheet()
                bot.reply_to(message, f"✅ Reseller ID: <code>{text}</code> အား စာရင်းမှ ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML")
            else:
                bot.reply_to(message, "❌ ဖျက်ထုတ်မှု မအောင်မြင်ပါ။", parse_mode="HTML")
            user_states[user_id] = None

# ==========================================
# 6. DATA VISUALIZATION & REPORTS
# ==========================================
def view_all_resellers(message):
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT reseller_id, username, credits FROM resellers")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "💼 Reseller မရှိသေးပါ။", parse_mode="HTML")
    res = "💼 <b>Resellers စာရင်းချုပ်:</b>\n\n"
    for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 {r[1]} | 🪙 <b>{r[2]} Tokens</b>\n"
    bot.reply_to(message, res, parse_mode="HTML")

def admin_view_all_keys(message):
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, vpn_key, unit_val, created_at FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 VIP အကောင့် မရှိသေးပါ။", parse_mode="HTML")
    res = f"🌐 <b>VPN APK VIP စာရင်းချုပ် ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        exp_str = get_expired_date_string(r[4], r[3])
        res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | 🔑 <code>{r[2]}</code> | 📅 <code>{exp_str}</code>\n"
    bot.reply_to(message, res, parse_mode="HTML")

def reseller_view_my_vips(message):
    user_id = str(message.from_user.id)
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, vpn_key, unit_val, created_at FROM auth_keys WHERE added_by = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 သင်ကိုယ်တိုင် ထည့်သွင်းထားသော VIP အသုံးပြုသူ မရှိသေးပါ။", parse_mode="HTML")
    res = f"🔑 <b>သင့်ရဲ့ VIP အသုံးပြုသူ စာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        exp_str = get_expired_date_string(r[4], r[3])
        res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | 🔑 <code>{r[2]}</code> | 📅 <code>{exp_str}</code>\n"
    bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# 7. WEBHOOK WEB SERVER & WEB POLLING
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()
    if PUBLIC_URL and BOT_TOKEN:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=PUBLIC_URL)
        except: pass
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    else:
        bot.infinity_polling()
