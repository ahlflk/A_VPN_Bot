# # All-in-One Safe Decryptor & Telegram VIP Management Bot (Google Sheets Engine)
# Py By @AHLFLK2025 (Google App Script Integration)

# ==========================================
# 1. CONFIGURATION & CORE BOT SETUP
# ==========================================
import os
import re
import json
import struct
import base64
import sqlite3
import requests
import urllib.request
from threading import Thread
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TGC_ID")) if os.environ.get("TGC_ID") else None
DEFAULT_CREDITS = 100  

# Google App Script API URL via Environment Variable
SCRIPT_URL = os.environ.get("SCRIPT_URL")
PUBLIC_URL = os.environ.get("PUBLIC_URL")
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
MENU_BUTTONS = ["🌐 VPN Decrypt List", "➕ Add VIP User", "🔑 My VIP Users", "✏️ Edit VIP", "🗑 Delete VIP", "👤 Create Reseller", "📊 Reseller List", "✏️ Edit Reseller", "🗑 Delete Reseller", "🌐 View All VIPs", "💰 My Balance"]

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

@app.route('/')
def home():
    return "VIP & Reseller Google-Sheet-Locked Bot is Active!"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

# ==========================================
# 2. CRYPTOGRAPHY & DECRYPTION ENGINE (XXTEA)
# ==========================================
def u32(x): return x & 0xFFFFFFFF

def _longs_to_bytes(n, include_length):
    length = len(n)
    res = struct.pack('<%dI' % length, *n)
    if include_length:
        expected_length = n[-1]
        max_len = len(res) - 4
        min_len = len(res) - 7
        if expected_length < min_len or expected_length > max_len:
            return res[:-4].rstrip(b'\x00')
        res = res[:expected_length]
    return res

def _bytes_to_longs(s):
    padding = (4 - len(s) % 4) % 4
    s += b'\x00' * padding
    return list(struct.unpack('<%dI' % (len(s) // 4), s))

def _fix_key(key_bytes):
    if len(key_bytes) == 16: return key_bytes
    return key_bytes[:16] if len(key_bytes) > 16 else key_bytes + b'\x00' * (16 - len(key_bytes))

def decrypt_xxtea(data, key, delta):
    if len(data) == 0: return b''
    v = _bytes_to_longs(data)
    k = _bytes_to_longs(_fix_key(key))
    n = len(v)
    if n < 2: return data 

    q = 52 // n + 6
    sum_val = u32(q * delta)

    while sum_val != 0:
        e = u32(sum_val >> 2) & 3
        y = v[0]
        for p in range(n - 1, 0, -1):
            z = v[p - 1]
            mx = u32(((z >> 5) ^ u32(y << 2)) + ((y >> 3) ^ u32(z << 4))) ^ u32((sum_val ^ y) + (k[(p & 3) ^ e] ^ z))
            y = u32(v[p] - mx)
            v[p] = y
        z = v[n - 1]
        mx = u32(((z >> 5) ^ u32(y << 2)) + ((y >> 3) ^ u32(z << 4))) ^ u32((sum_val ^ y) + (k[(0 & 3) ^ e] ^ z))
        y = u32(v[0] - mx)
        v[0] = y
        sum_val = u32(sum_val - delta)
    return _longs_to_bytes(v, True)

def parse_delta(delta_val):
    if isinstance(delta_val, int): return delta_val
    try:
        if isinstance(delta_val, str) and delta_val.strip().startswith('-'):
            clean_hex = delta_val.replace('-', '').strip()
            return -int(clean_hex, 16)
        else: return int(delta_val, 16)
    except: return 0x2e0ba747

def decrypt_inner_base64_recursive(encrypted_str):
    if not isinstance(encrypted_str, str) or len(encrypted_str) < 4: return encrypted_str
    try:
        clean_str = encrypted_str.replace('\n', '').replace('\r', '').strip()
        if not re.match(r'^[A-Za-z0-9+/=]+$', clean_str): return encrypted_str
        missing_padding = len(clean_str) % 4
        if missing_padding: clean_str += '=' * (4 - missing_padding)
        decoded_bytes = base64.b64decode(clean_str)
        decoded_str = decoded_bytes.decode('utf-8')
        if len(decoded_str) > 4 and re.match(r'^[A-Za-z0-9+/=]+$', decoded_str.replace('\n','').strip()):
            if any(x in decoded_str for x in ["HTTP/", "vless://", "vmess://", "trojan://", "ss://"]): return decoded_str
            return decrypt_inner_base64_recursive(decoded_str)
        return decoded_str
    except: return encrypted_str

def decrypt_inner_bamar(encrypted_str):
    if not encrypted_str or len(encrypted_str) < 10: return encrypted_str
    try:
        data = base64.b64decode(encrypted_str)
        decrypted_bytes = decrypt_xxtea(data, b"9488362782103982762188", 0x2e0ba747)
        return decrypted_bytes.decode('utf-8', errors='ignore') if decrypted_bytes else encrypted_str
    except: return encrypted_str

def decrypt_inner_pnt(encrypted_str):
    if not encrypted_str or len(encrypted_str) < 15: return encrypted_str
    try:
        data = base64.b64decode(encrypted_str, validate=True)
        decrypted_bytes = decrypt_xxtea(data, b"7361", 0x2e0ba747)
        if not decrypted_bytes: return encrypted_str
        intermediate_str = decrypted_bytes.decode('utf-8')
        key_int = 7361
        final_str = []
        for char in intermediate_str:
            val = (ord(char) - key_int - key_int) & 0xFFFF
            final_str.append(chr(val))
        return "".join(final_str)
    except: return encrypted_str

def process_json_structure(data, method):
    if isinstance(data, dict): return {k: process_json_structure(v, method) for k, v in data.items()}
    elif isinstance(data, list): return [process_json_structure(i, method) for i in data]
    elif isinstance(data, str):
        if method == "bamar": return decrypt_inner_bamar(data)
        elif method == "pnt_special": return decrypt_inner_pnt(data)
        elif method == "base64_recursive": return decrypt_inner_base64_recursive(data)
        return data
    return data

def perform_decryption(config_url, outer_key, outer_delta_raw, method):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(config_url, headers=headers)
    with urllib.request.urlopen(req) as response:
        enc_base64 = response.read().decode('utf-8').replace('\n', '').replace('\r', '').strip()
        
    outer_delta = parse_delta(outer_delta_raw)
    enc_data = base64.b64decode(enc_base64)
    dec_bytes = decrypt_xxtea(enc_data, outer_key.encode('utf-8'), outer_delta)
    raw_json_str = dec_bytes.decode('utf-8', errors='ignore').replace('\\/', '/')
    json_obj = json.loads(raw_json_str)
    return {"AHLFLK": "Decrypted By @AHLFLK2025", **process_json_structure(json_obj, method)}

def get_vpn_configs():
    try: 
        return json.loads(VPN_CONFIGS) if VPN_CONFIGS else []
    except Exception as e: 
        print(f"[-] VPN Configs Parse Error: {str(e)}")
        return []

# ==========================================
# 3. DATABASE & GOOGLE SHEET SYNC SYSTEM
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS auth_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            target_id TEXT UNIQUE,
            key_string TEXT, 
            unit_val TEXT, 
            duration_type TEXT, 
            added_by INTEGER,
            created_at TEXT
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, 
            username TEXT, 
            role TEXT,
            token_balance INTEGER DEFAULT 0,
            expire_date TEXT DEFAULT '2099-12-31'
        )''')
        cursor.execute("INSERT OR IGNORE INTO users (tg_id, username, role, token_balance, expire_date) VALUES (?, ?, ?, ?, ?)", (ADMIN_ID, 'Main_Admin', 'admin', 9999999, '2099-12-31'))
        conn.commit()
    finally:
        conn.close()

def pull_data_from_google_sheet():
    """ Google Sheet မှ ဒေတာများကို ဖတ်ပြီး local SQLite ထဲသို့ ထည့်သွင်းခြင်း """
    try:
        res = requests.get(SCRIPT_URL, timeout=15)
        if res.status_code == 200:
            sheet_data = res.json()
            if isinstance(sheet_data, list):
                conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM auth_keys")
                    for row in sheet_data:
                        # Column အမည်များ: Users, Name, Key, Start, Month, Valid, Expiration
                        target_id = row.get("Users", "").strip()
                        name = row.get("Name", "").strip()
                        key_val = row.get("Key", "").strip()
                        start_date = row.get("Start", "").strip()
                        month_val = row.get("Month", "").strip()
                        
                        if target_id and target_id.isdigit():
                            # Local database compatibility mapping
                            cursor.execute(
                                "INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (target_id, name, month_val, 'm', ADMIN_ID, start_date)
                            )
                    conn.commit()
                finally:
                    conn.close()
    except Exception as e:
        print(f"[-] Pull Sheet Data Error: {str(e)}")

def push_vip_to_google_sheet(target_id, name, key, start, month, valid, expiration):
    """ Sheet ထဲသို့ VIP ဒေတာ အသစ်ထည့်ခြင်း သို့မဟုတ် ပြင်ဆင်ခြင်း """
    payload = {
        "action": "add_or_update",
        "users": str(target_id),
        "name": str(name),
        "key": str(key),
        "start": str(start),
        "month": str(month),
        "valid": str(valid),
        "expiration": str(expiration)
    }
    try:
        requests.post(SCRIPT_URL, json=payload, timeout=15)
    except Exception as e:
        print(f"[-] Push Sheet Error: {str(e)}")

def delete_vip_from_google_sheet(target_id):
    """ Sheet ထဲမှ VIP ကို ဖျက်ထုတ်ခြင်း """
    payload = {
        "action": "delete",
        "users": str(target_id)
    }
    try:
        requests.post(SCRIPT_URL, json=payload, timeout=15)
    except Exception as e:
        print(f"[-] Delete Sheet Error: {str(e)}")

# ==========================================
# 4. AUTHENTICATION & TOKEN LOGIC
# ==========================================
def calculate_days(unit, duration_type):
    if duration_type.lower() == 'm':
        return int(unit) * 30
    return int(unit)

def is_admin(user_id): 
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'admin'", (user_id,))
        res = cursor.fetchone()
    finally:
        conn.close()
    return res is not None

def is_reseller(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE tg_id = ? AND (role = 'reseller' OR role = 'admin')", (user_id,))
        res = cursor.fetchone()
    finally:
        conn.close()
    return res is not None

def check_vip_status(user_id):
    if user_id == ADMIN_ID: return True, "Unlimited (Admin)"
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role, token_balance, expire_date FROM users WHERE tg_id = ?", (user_id,))
        user_row = cursor.fetchone()
        
        if user_row and user_row[0] == 'reseller':
            exp_date_str = user_row[2]
            try:
                expire_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
                if datetime.now().date() > expire_date:
                    return False, "Expired (Date Out)"
                return True, f"Reseller Staff ({exp_date_str})"
            except:
                return False, "Date Error"

        # Check in local synchronized keys
        cursor.execute("SELECT key_string, unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        row = cursor.fetchone()
        
        if not row: return False, "Not VIP"
        
        key_string, unit_val, created_at_str = row
        try:
            # Google sheet Date formatting parsing (DD/MM/YYYY သို့မဟုတ် YYYY-MM-DD ဖြစ်နိုင်ခြေအတွက်)
            if "/" in created_at_str:
                created_date = datetime.strptime(created_at_str, "%d/%m/%m").date() if len(created_at_str.split('/')[2])==2 else datetime.strptime(created_at_str, "%d/%m/%Y").date()
            else:
                created_date = datetime.strptime(created_at_str, "%Y-%m-%d").date()
                
            months_to_add = int(unit_val)
            # အကြမ်းဖျင်း ရက်ပေါင်းတွက်ချက်ခြင်း
            expire_date = created_date + timedelta(days=months_to_add * 30)
            
            if datetime.now().date() <= expire_date:
                return True, expire_date.strftime("%d/%m/%Y")
            else:
                return False, "Expired"
        except: 
            return False, "Error Check"
    finally:
        conn.close()

def get_reseller_tokens(user_id):
    if user_id == ADMIN_ID: return 9999999
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT token_balance FROM users WHERE tg_id = ?", (user_id,))
        res = cursor.fetchone()
    finally:
        conn.close()
    return res[0] if res else 0

def deduct_reseller_tokens_by_days(user_id, required_tokens):
    if user_id == ADMIN_ID: return True
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT token_balance, expire_date FROM users WHERE tg_id = ?", (user_id,))
        res = cursor.fetchone()
        if res:
            tokens, exp_date_str = res
            try:
                expire_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
                if datetime.now().date() > expire_date:
                    return False 
            except: 
                return False
                
            if tokens >= required_tokens:
                cursor.execute("UPDATE users SET token_balance = token_balance - ? WHERE tg_id = ?", (required_tokens, user_id))
                conn.commit()
                return True
        return False
    finally:
        conn.close()

# ==========================================
# 5. TELEGRAM INTERFACE & NAVIGATION MAIN
# ==========================================
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    is_vip, _ = check_vip_status(user_id)
    
    if is_vip or is_admin(user_id):
        markup.row(types.KeyboardButton("🌐 VPN Decrypt List"))
        
    if is_vip and not is_reseller(user_id):
        markup.row(types.KeyboardButton("💰 My Balance"))
    
    if is_reseller(user_id) and (is_vip or user_id == ADMIN_ID):
        markup.row(types.KeyboardButton("➕ Add VIP User"), types.KeyboardButton("🔑 My VIP Users"))
        markup.row(types.KeyboardButton("✏️ Edit VIP"), types.KeyboardButton("🗑 Delete VIP"))
        
        if is_admin(user_id):
            markup.row(types.KeyboardButton("💰 My Balance"), types.KeyboardButton("🌐 View All VIPs"))
        else:
            markup.row(types.KeyboardButton("💰 My Balance"))
            
    elif is_reseller(user_id):
        markup.row(types.KeyboardButton("💰 My Balance"))
        
    if is_admin(user_id):
        markup.row(types.KeyboardButton("👤 Create Reseller"), types.KeyboardButton("📊 Reseller List"))
        markup.row(types.KeyboardButton("✏️ Edit Reseller"), types.KeyboardButton("🗑 Delete Reseller"))
        
    return markup

@bot.message_handler(func=lambda msg: msg.text in MENU_BUTTONS)
def handle_menu_buttons(message):
    user_id = message.from_user.id
    user_states[user_id] = None  
    if user_id in reseller_temp_data: del reseller_temp_data[user_id] 
    
    is_vip, _ = check_vip_status(user_id)
    if message.text != "💰 My Balance" and not is_vip and not is_admin(user_id):
        return bot.reply_to(message, "🚫 <b>သင့်အကောင့်သည် သက်တမ်းကုန်ဆုံးသွားပြီဖြစ်၍ ဤခလုတ်အား အသုံးပြုနိုင်ခြင်းမရှိပါ။</b>\n\nAdmin ထံ ဆက်သွယ်ရန် ခလုတ်ကို နှိပ်ပါ။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

    if message.text == "🌐 VPN Decrypt List":
        display_decrypt_list(message, user_id, message.chat.id)
    elif message.text == "➕ Add VIP User":
        cmd_add_vip(message)
    elif message.text == "🔑 My VIP Users":
        cmd_my_vips(message)
    elif message.text == "💰 My Balance":
        cmd_my_balance(message)
    elif message.text == "✏️ Edit VIP":
        admin_reseller_edit_vip_menu(message)
    elif message.text == "🗑 Delete VIP":
        admin_reseller_delete_vip_menu(message)
    elif message.text == "👤 Create Reseller":
        admin_create_reseller(message)
    elif message.text == "📊 Reseller List":
        admin_view_resellers(message)
    elif message.text == "✏️ Edit Reseller":
        admin_edit_reseller_menu(message)
    elif message.text == "🗑 Delete Reseller":
        admin_delete_reseller_menu(message)
    elif message.text == "🌐 View All VIPs":
        admin_view_all_keys(message)

def display_decrypt_list(message_or_call, user_id, chat_id):
    pull_data_from_google_sheet()
    is_vip, exp_status = check_vip_status(user_id)

    try:
        bot_info = bot.get_me()
        bot_name = bot_info.first_name
    except:
        bot_name = "Safe Decryptor & VIP Center"
    
    if isinstance(message_or_call, types.Message):
        first_name = message_or_call.from_user.first_name
    else:
        first_name = message_or_call.from_user.first_name if hasattr(message_or_call, 'from_user') else "User"

    if not is_vip:
        no_vip_text = f"🚫 <b>သင်သည် VIP စနစ်အသုံးပြုခွင့် မရှိသေးပါ (သို့မဟုတ်) သက်တမ်းကုန်သွားပါပြီ!</b>\n\n" \
                      f"👤 အမည်: <b>{first_name}</b>\n" \
                      f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                      f"📊 အခြေအနေ: <b>{exp_status}</b>\n\n" \
                      f"Admin ထံဆက်သွယ်၍ သက်တမ်းတိုးမြှင့်/ဝယ်ယူနိုင်ပါသည်။"
        
        if isinstance(message_or_call, types.Message):
            bot.reply_to(message_or_call, no_vip_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
        else:
            bot.send_message(chat_id, no_vip_text, reply_markup=get_admin_contact_markup(), parse_mode="HTML")
        return

    account_status = "VIP User VIP ✨"
    tokens_line = ""
    
    if is_admin(user_id):
        account_status = "Main Admin 👑"
    elif is_reseller(user_id):
        account_status = "Reseller Staff 💼"
        tokens = get_reseller_tokens(user_id)
        tokens_line = f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n"

    configs = get_vpn_configs()
    
    welcome_text = f"👋 <b>{bot_name} မှ\nနွေးထွေးစွာ ကြိုဆိုပါတယ်!</b>\n\n" \
                   f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                   f"👑 အဆင့်အတန်း: <b>{account_status}</b>\n" \
                   f"👤 အမည်: <b>{first_name}</b>\n" \
                   f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                   f"{tokens_line}" \
                   f"⏳ သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>\n\n" \
                   f"--- <b>Decrypt Configurations List</b> ---\n" \
                   f"🛠️ Decrypt လုပ်ချင်တဲ့ VPN Config အမျိုးအစားကို အောက်မှာ ရွေးချယ်ပါ-"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for index, vpn in enumerate(configs, start=1):
        btn = types.InlineKeyboardButton(f"[{index}] {vpn['name']}", callback_data=f"dec_{vpn['id']}")
        buttons.append(btn)
    
    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])
        
    if isinstance(message_or_call, types.Message):
        bot.reply_to(message_or_call, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")
    else:
        bot.send_message(chat_id, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")
        
    if configs: 
        bot.send_message(chat_id, "👇 Decrypt Configurations List:", reply_markup=markup)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None 
    display_decrypt_list(message, user_id, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def handle_decrypt_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    is_vip, _ = check_vip_status(user_id)
    if not is_vip:
        bot.answer_callback_query(call.id, "🚫 သင်သည် VIP သက်တမ်း ကုန်ဆုံးသွားပြီ ဖြစ်သည်။")
        bot.send_message(chat_id, "🚫 သင်သည် VIP သက်တမ်း ကုန်ဆုံးသွားပြီ ဖြစ်သဖြင့် အသုံးပြု၍မရပါ။ Admin ထံ ဆက်သွယ်ပါ။", reply_markup=get_admin_contact_markup())
        return

    vpn_id = call.data.split('_')[1]
    configs = get_vpn_configs()
    selected_vpn = next((item for item in configs if item["id"] == vpn_id), None)
    if not selected_vpn: return

    status_msg = bot.send_message(chat_id, f"⏳ <b>{selected_vpn['name']} VPN Config ကို Decrypt လုပ်နေပါတယ်...</b>", parse_mode="HTML")
    try:
        result_json = perform_decryption(selected_vpn["url"], selected_vpn["outer_key"], selected_vpn["outer_delta"], selected_vpn["method"])
        temp_file_path = f"{vpn_id}_decrypted.json"
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, indent=4, ensure_ascii=False)
            
        bot.delete_message(chat_id, status_msg.message_id)
        with open(temp_file_path, 'rb') as doc:
            bot.send_document(chat_id, doc, caption=f"✅ <b>{selected_vpn['name']} Decrypted Successfully!</b>", parse_mode="HTML")
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
    except Exception as e:
        bot.send_message(chat_id, f"❌ <b>Error:</b> <code>{str(e)}</code>\nပြဿနာတစ်စုံတစ်ရာရှိပါက Admin သို့ မေးမြန်းနိုင်ပါသည်။", reply_markup=get_admin_contact_markup(), parse_mode="HTML")

# ==========================================
# 6. RESELLER PANEL: MANAGE VIP CUSTOMERS
# ==========================================
def cmd_add_vip(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_google_sheet()
    
    current_tokens = get_reseller_tokens(user_id)
    user_states[user_id] = 'w_vip'
    
    msg_text = (
        f"✍️ <b>VIP အသစ်ဆောက်ရန် ပုံစံစာသားပေးပို့ပါ-</b>\n"
        f"🪙 နှုန်းထား: <code>1 Month = 30 Tokens</code> (လက်ကျန်: <code>{current_tokens}</code> Tokens)\n\n"
        f"✍️ Format အတိုင်း အောက်ပါစာသားကို ကူးယူပြင်ဆင်ပြီး ပို့နိုင်ပါသည်-\n"
        f"<code>TelegramID | VIP_Name | Key_Hex | Month_Count</code>\n\n"
        f"👇 <b>နမူနာ ကို နှိပ်ပြီး Copy ယူနိုင်သည် (ဥပမာ ၁ လစာ)-</b>\n"
        f"<code>1234567890 | AHLFLK2025 | 8e8a34bd8e494abc | 1</code>"
    )
    bot.reply_to(message, msg_text, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_vip')
def process_vip_add(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4 or not parts[0].isdigit() or not parts[3].isdigit():
        return bot.reply_to(message, "❌ ပုံစံမှားနေပါသည်။ TelegramID | VIP_Name | Key_Hex | Month_Count အတိုင်း သေချာပြန်ပို့ပေးပါ။")
    
    target_vip_id = int(parts[0])
    pull_data_from_google_sheet()
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key_string FROM auth_keys WHERE target_id = ?", (str(target_vip_id),))
        existing_vip = cursor.fetchone()
        
        cursor.execute("SELECT username FROM users WHERE tg_id = ?", (target_vip_id,))
        existing_reseller = cursor.fetchone()
    finally:
        conn.close()
    
    if existing_vip:
        user_states[user_id] = None
        return bot.reply_to(message, f"❌ <b>ထည့်သွင်း၍မရပါ!</b>\n\nဒီ ID (<code>{target_vip_id}</code>) သည် VIP စနစ်ထဲတွင် ရှိနှင့်ပြီးသား ဖြစ်နေပါသည်။")

    if existing_reseller:
        user_states[user_id] = None
        return bot.reply_to(message, f"❌ <b>ထည့်သွင်း၍မရပါ!</b>\n\nဒီ ID သည် Reseller စာရင်းထဲတွင် ရှိနေသောကြောင့် VIP ထည့်၍မရပါ။")

    months = int(parts[3])
    required_tokens = months * 30  # 1 Month = 30 tokens deduction
    current_tokens = get_reseller_tokens(user_id)
    
    if not is_admin(user_id) and current_tokens < required_tokens:
        return bot.reply_to(message, f"❌ Token မလုံလောက်ပါ။ {required_tokens} Tokens လိုအပ်သည်။ အကူအညီရရန် Admin သို့ ဆက်သွယ်ပါ။", reply_markup=get_admin_contact_markup())

    if deduct_reseller_tokens_by_days(user_id, required_tokens):
        try:
            start_date_str = datetime.now().strftime("%d/%m/%Y")
            exp_date_str = (datetime.now() + timedelta(days=months * 30)).strftime("%d/%m/%Y")
            
            # Google Sheet သို့ လှမ်းသိမ်းခြင်း (Columns: Users, Name, Key, Start, Month, Valid, Expiration)
            push_vip_to_google_sheet(
                target_id=target_vip_id,
                name=parts[1],
                key=parts[2],
                start=start_date_str,
                month=months,
                valid="-34", # Default fixed value context in your sheet image
                expiration=exp_date_str
            )
            
            # Local Database မှာလည်း မှတ်ထားမယ်
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)", (str(target_vip_id), parts[1], str(months), 'm', user_id, start_date_str))
                conn.commit()
            finally:
                conn.close()
            
            new_balance = get_reseller_tokens(user_id)
            bot.reply_to(message, f"✅ <b>VIP အကောင့်ကို Google Sheet ထဲသို့ အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ။</b>\n👤 နာမည်: <b>{parts[1]}</b>\n💰 လက်ကျန်တိုကင်: <code>{new_balance}</code> Tokens", parse_mode="HTML")
        except Exception as e: 
            bot.reply_to(message, f"❌ Error: {str(e)}")
    else:
        bot.reply_to(message, "❌ တိုကင်နှုတ်ယူခြင်း မအောင်မြင်ပါ (သို့မဟုတ်) သင့်သက်တမ်း ကုန်ဆုံးနေပါသည်။", reply_markup=get_admin_contact_markup())
        
    user_states[user_id] = None

def cmd_my_vips(message):
    if not is_reseller(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys WHERE added_by = ?", (message.from_user.id,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 သင်ထည့်သွင်းထားသော VIP အကောင့်မရှိသေးပါ။")
    res = "👥 <b>...သင်ထည့်ထားသော VIP အသုံးပြုသူများ...</b>\n\n"
    for r in rows: res += f"• ID: <code>{r[0]}</code> -> နာမည်: <b>{r[1]}</b> ({r[2]} လစာ)\n"
    bot.reply_to(message, res, parse_mode="HTML")

def cmd_my_balance(message):
    user_id = message.from_user.id
    pull_data_from_google_sheet()
    
    is_vip, exp_status = check_vip_status(user_id)
    tokens = 0
    exp_date_str = exp_status
    is_expired = not is_vip
    
    if is_reseller(user_id):
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT token_balance, expire_date FROM users WHERE tg_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                tokens = row[0]
                exp_date_str = row[1]
                try:
                    expire_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                    if datetime.now() > expire_date:
                        is_expired = True
                except:
                    is_expired = True
        except Exception as e:
            print(f"[-] Balance Check Error: {str(e)}")
            is_expired = True
        finally:
            conn.close()

    needs_contact_admin = is_expired and (user_id != ADMIN_ID)

    response_text = f"💰 <b>သင့်အကောင့်အခြေအနေ (Account Info):</b>\n\n" \
                    f"👤 အမည်: {message.from_user.first_name}\n" \
                    f"🆔 Telegram ID: <code>{user_id}</code>\n"
    
    if is_reseller(user_id) and user_id != ADMIN_ID:
        response_text += f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n"
        response_text += f"⏳ သင့် Reseller သက်တမ်းကုန်မည့်ရက်: <code>{exp_date_str}</code>"
    else:
        response_text += f"⏳ သင့် VIP သက်တမ်းကုန်မည့်ရက်: <code>{exp_date_str}</code>"
    
    if needs_contact_admin:
        response_text += "\n\n⚠️ <b>သင့်အကောင့်သည် သက်တမ်းကုန်ဆုံးနေခြင်း (သို့မဟုတ်) အသုံးပြုခွင့်မရှိခြင်း ဖြစ်ပေါ်နေပါသည်။</b>"
        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
        bot.reply_to(message, response_text, reply_markup=admin_markup, parse_mode="HTML")
    else:
        bot.reply_to(message, response_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

def admin_reseller_edit_vip_menu(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        if is_admin(user_id):
            cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
        else:
            cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys WHERE added_by = ?", (user_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    
    if not rows: return bot.reply_to(message, "📭 ပြင်ဆင်ရန် VIP အသုံးပြုသူ လုံးဝမရှိသေးပါ။")
    
    res_list = "📝 <b>...လက်ရှိ VIP အသုံးပြုသူ စာရင်းများ...</b>\n\n"
    for r in rows: res_list += f"🆔 <code>{r[0]}</code> | 👤 <b>{r[1]}</b> ({r[2]} လစာ)\n"
    res_list += "\n✍️ <b>သက်တမ်းပြင်ဆင်/တိုးမြှင့်လိုသော VIP ၏ Telegram ID ကို ရိုက်ပို့ပေးပါ-</b>"
    
    user_states[user_id] = 'w_edit_vip_id'
    bot.send_message(message.chat.id, res_list, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_edit_vip_id')
def process_edit_vip_id(message):
    user_id = message.from_user.id
    target_id_str = message.text.strip()
    if not target_id_str.isdigit(): return bot.reply_to(message, "❌ Telegram ID အမှန်ကို ရိုက်ပို့ပေးပါ။")
        
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        if is_admin(user_id):
            cursor.execute("SELECT key_string, unit_val, duration_type FROM auth_keys WHERE target_id = ?", (str(target_id_str),))
        else:
            cursor.execute("SELECT key_string, unit_val, duration_type FROM auth_keys WHERE target_id = ? AND added_by = ?", (str(target_id_str), user_id))
        row = cursor.fetchone()
    finally:
        conn.close()
    
    if not row: return bot.reply_to(message, "❌ ဤ ID ဖြင့် VIP အား ရှာမတွေ့ပါ သို့မဟုတ် ပြင်ဆင်ခွင့်မရှိပါ။")
        
    reseller_temp_data[user_id] = {'target_id': str(target_id_str), 'name': row[0]}
    user_states[user_id] = 'w_edit_vip_duration'
    
    edit_msg = f"👤 အကောင့်: <b>{row[0]}</b>\n\n✍️ တိုးမြှင့်လိုသော <b>လ အရေအတွက် (Month)</b> ကို ရိုက်ပို့ပေးပါ-\nဥပမာ- <code>1</code> (၁ လစာအတွက် 30 Tokens ထပ်မံနှုတ်ယူပါမည်)"
    bot.reply_to(message, edit_msg, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_edit_vip_duration')
def process_edit_vip_duration(message):
    user_id = message.from_user.id
    temp = reseller_temp_data.get(user_id)
    if not temp: return
        
    input_month = message.text.strip()
    if not input_month.isdigit():
        return bot.reply_to(message, "❌ လ အရေအတွက် ဂဏန်းသီးသန့်သာ ထည့်သွင်းပေးပါ။")
        
    months = int(input_month)
    new_days = months * 30
    current_tokens = get_reseller_tokens(user_id)
    
    if not is_admin(user_id) and current_tokens < new_days:
        return bot.reply_to(message, f"❌ သက်တမ်းတိုးရန် Token မလုံလောက်ပါ။ Admin ထံ ဆက်သွယ်ပါ။", reply_markup=get_admin_contact_markup())
        
    pull_data_from_google_sheet()
    
    if deduct_reseller_tokens_by_days(user_id, new_days):
        start_date_str = datetime.now().strftime("%d/%m/%Y")
        exp_date_str = (datetime.now() + timedelta(days=months * 30)).strftime("%d/%m/%Y")
        
        # Google Sheet ထဲမှာပါ သွားရောက် Update လုပ်ပေးခြင်း
        push_vip_to_google_sheet(
            target_id=temp['target_id'],
            name=temp['name'],
            key="8e8a34bd8e494abc", # Fallback or keep static context
            start=start_date_str,
            month=months,
            valid="-34",
            expiration=exp_date_str
        )
        
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE auth_keys SET unit_val = ?, created_at = ? WHERE target_id = ?", (months, start_date_str, str(temp['target_id'])))
            conn.commit()
        finally:
            conn.close()
        
        new_balance = get_reseller_tokens(user_id)
        bot.reply_to(message, f"✅ VIP User: <b>{temp['name']}</b> ကို Google Sheet တွင် သက်တမ်းတိုးမြှင့်ပြီးပါပြီ။\n💰 လက်ကျန်တိုကင်: <code>{new_balance}</code> Tokens", parse_mode="HTML")
    else:
        bot.reply_to(message, "❌ Token နှုတ်ယူခြင်း မအောင်မြင်ပါ။ သက်တမ်းကုန်နေခြင်း ဖြစ်နိုင်ပါသည်။", reply_markup=get_admin_contact_markup())
    
    user_states[user_id] = None
    if user_id in reseller_temp_data: del reseller_temp_data[user_id]

def admin_reseller_delete_vip_menu(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        if is_admin(user_id):
            cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
        else:
            cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys WHERE added_by = ?", (user_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 ဖျက်ရန် VIP မရှိပါ။")
    
    res_list = "🗑 <b>လက်ရှိ VIP အသုံးပြုသူ စာရင်းများ</b>\n\n"
    for r in rows: res_list += f"🆔 <code>{r[0]}</code> | 👤 <b>{r[1]}</b> ({r[2]} လစာ)\n"
    res_list += "\n✍️ <b>ဖျက်ထုတ်လိုသော VIP ၏ Telegram ID ကို ရိုက်ပို့ပေးပါ-</b>"
    user_states[user_id] = 'w_del_vip'
    bot.send_message(message.chat.id, res_list, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_del_vip')
def process_delete_vip_by_id(message):
    user_id = message.from_user.id
    id_to_del = message.text.strip()
    if not id_to_del.isdigit(): return bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။")
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        if is_admin(user_id):
            cursor.execute("SELECT key_string FROM auth_keys WHERE target_id = ?", (str(id_to_del),))
        else:
            cursor.execute("SELECT key_string FROM auth_keys WHERE target_id = ? AND added_by = ?", (str(id_to_del), user_id))
        row = cursor.fetchone()
        if not row:
            return bot.reply_to(message, "❌ ရှာမတွေ့ပါ သို့မဟုတ် ဖျက်ခွင့်မရှိပါ။")
            
        # Google Sheet ထဲမှပါ လှမ်းဖျက်ခြင်း
        delete_vip_from_google_sheet(id_to_del)
        
        cursor.execute("DELETE FROM auth_keys WHERE target_id = ?", (str(id_to_del),))
        conn.commit()
    finally:
        conn.close()
    
    bot.reply_to(message, f"✅ VIP User: <b>{row[0]}</b> ကို Sheet နှင့် System ထဲမှ ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML")
    user_states[user_id] = None

# ==========================================
# 7. MAIN ADMIN PANEL: MANAGE RESELLERS
# ==========================================
def admin_create_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'w_one_line_reseller'
    
    r_msg = (
        f"👤 <b>Reseller အသစ်ဖန်တီးရန် စာသားပေးပို့ပါ-</b>\n\n"
        f"✍️ Format လမ်းညွှန်-\n"
        f"<code>TelegramID | Reseller_Name | Tokens | ExpireDate(YYYY-MM-DD)</code>\n\n"
        f"👇 <b>နမူနာ ကို နှိပ်ပြီး Copy ယူနိုင်သည်-</b>\n"
        f"<code>1234567890 | MgMg_Reseller | 100 | 2026-07-02</code>"
    )
    bot.reply_to(message, r_msg, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_one_line_reseller')
def process_one_line_reseller(message):
    admin_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    
    if len(parts) != 4 or not parts[0].isdigit() or not parts[2].isdigit():
        return bot.reply_to(message, "❌ ပုံစံမှားယွင်းနေပါသည်။ TelegramID | Reseller_Name | Tokens | YYYY-MM-DD အတိုင်း ပို့ပေးပါ။")
        
    r_id = int(parts[0])
    r_name = parts[1]
    r_tokens = int(parts[2])
    r_date = parts[3]
    
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', r_date):
        return bot.reply_to(message, "❌ ရက်စွဲပုံစံ မှားနေပါသည်။ YYYY-MM-DD (ဥပမာ- 2026-07-02) အတိုင်း ရေးပေးပါ။")
    
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE tg_id = ?", (r_id,))
        existing_reseller = cursor.fetchone()
        
        cursor.execute("SELECT key_string FROM auth_keys WHERE target_id = ?", (str(r_id),))
        existing_vip = cursor.fetchone()
    finally:
        conn.close()
    
    if existing_reseller:
        user_states[admin_id] = None
        return bot.reply_to(message, f"❌ ဤ ID သည် Reseller အဖြစ် ရှိနှင့်ပြီးသား ဖြစ်နေပါသည်။")

    if existing_vip:
        user_states[admin_id] = None
        return bot.reply_to(message, f"❌ ဤ ID သည် VIP စာရင်းထဲတွင် ရှိနေသောကြောင့် Reseller ခန့်၍မရပါ။")

    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (tg_id, username, role, token_balance, expire_date) VALUES (?, ?, 'reseller', ?, ?)", (r_id, r_name, r_tokens, r_date))
            conn.commit()
        finally:
            conn.close()
        
        success_msg = (
            f"✅ <b>Reseller အကောင့်ကို အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ!</b>\n\n"
            f"🆔 ID: {r_id}\n"
            f"👤 နာမည်: <b>{r_name}</b>\n"
            f"🪙 Tokens: {r_tokens} Tokens\n"
            f"⏳ သက်တမ်းကုန်မည့်ရက်: {r_date}"
        )
        bot.reply_to(message, success_msg, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
        
    user_states[admin_id] = None

def admin_view_resellers(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role='reseller' AND tg_id != ?", (ADMIN_ID,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း လုံးဝမရှိသေးပါ။")
    res = "👥 <b>Reseller စာရင်းများနှင့် သက်တမ်းများ:</b>\n\n"
    for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 <b>{r[1]}</b>\n🪙 {r[2]} Tokens | ⏳ Exp: <code>{r[3]}</code>\n\n"
    bot.reply_to(message, res, parse_mode="HTML")

def admin_edit_reseller_menu(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role = 'reseller' AND tg_id != ?", (ADMIN_ID,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    
    if not rows: return bot.reply_to(message, "📭 ပြင်ဆင်ရန် Reseller လုံးဝမရှိသေးပါ။")
    
    res_list = "📝 <b>...လက်ရှိ Reseller စာရင်းများ...</b>\n\n"
    for r in rows: res_list += f"🆔 <code>{r[0]}</code> | 👤 <b>{r[1]}</b> (🪙 {r[2]} | ⏳ {r[3]})\n"
    res_list += "\n✍️ <b>ပြင်ဆင်လိုသော Reseller ၏ Telegram ID ကို ရိုက်ပို့ပေးပါ-</b>"
    
    user_states[message.from_user.id] = 'w_edit_reseller_id'
    bot.send_message(message.chat.id, res_list, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_edit_reseller_id')
def process_edit_reseller_id(message):
    admin_id = message.from_user.id
    target_id_str = message.text.strip()
    if not target_id_str.isdigit(): return bot.reply_to(message, "❌ Telegram ID အမှန်ကို ရိုက်ပို့ပေးပါ။")
        
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username, token_balance, expire_date FROM users WHERE tg_id = ? AND role = 'reseller'", (int(target_id_str),))
        row = cursor.fetchone()
    finally:
        conn.close()
    
    if not row: return bot.reply_to(message, "❌ ဤ ID ဖြင့် Reseller အား ရှာမတွေ့ပါ။")
        
    reseller_temp_data[admin_id] = {'target_reseller_id': int(target_id_str), 'old_name': row[0]}
    user_states[admin_id] = 'w_edit_reseller_data'
    
    edit_msg = (
        f"👤 ပြင်ဆင်မည့်သူ: <b>{row[0]}</b>\n\n"
        f"✍️ <b>အချက်အလက်အသစ်များကို အောက်ပါ Format အတိုင်း ပြင်ဆင်ပို့ပေးပါ-</b>\n"
        f"<code>Reseller_Name | New_Tokens | ExpireDate(YYYY-MM-DD)</code>\n\n"
        f"👇 <b>နမူနာ ကို နှိပ်ပြီး Copy ယူနိုင်သည်-</b>\n"
        f"<code>{row[0]} | {row[1]} | {row[2]}</code>"
    )
    bot.reply_to(message, edit_msg, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_edit_reseller_data')
def process_edit_reseller_data(message):
    admin_id = message.from_user.id
    temp = reseller_temp_data.get(admin_id)
    if not temp: return
        
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 3 or not parts[1].isdigit():
        return bot.reply_to(message, "❌ Format မှားယွင်းနေပါသည်။ Name | Tokens | YYYY-MM-DD ဟု ပို့ပေးပါ။")
        
    new_name = parts[0]
    new_tokens = int(parts[1])
    new_date = parts[2]
    
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', new_date):
        return bot.reply_to(message, "❌ ရက်စွဲပုံစံ မှားနေပါသည်။ YYYY-MM-DD (ဥပမာ- 2026-07-02) အတိုင်း ရေးပေးပါ။")
        
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET username = ?, token_balance = ?, expire_date = ? WHERE tg_id = ?", (new_name, new_tokens, new_date, temp['target_reseller_id']))
            conn.commit()
        finally:
            conn.close()
        
        bot.reply_to(message, f"✅ Reseller: <b>{temp['old_name']}</b> ၏ အချက်အလက်များအား အောင်မြင်စွာ အပ်ဒိတ်လုပ်ပြီးပါပြီ။", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
    
    user_states[admin_id] = None
    if admin_id in reseller_temp_data: del reseller_temp_data[admin_id]

def admin_delete_reseller_menu(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role = 'reseller' AND tg_id != ?", (ADMIN_ID,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 ဖျက်ရန် Reseller မရှိပါ။")
    
    res_list = "👥 <b>လက်ရှိ Reseller စာရင်းများ:</b>\n\n"
    for r in rows: 
        res_list += f"🆔 <code>{r[0]}</code> | 👤 <b>{r[1]}</b> (🪙 {r[2]} | ⏳ {r[3]})\n"
        
    res_list += "\n✍️ <b>ဖျက်ထုတ်လိုသော Reseller ၏ Telegram ID ကို ရိုက်ပို့ပေးပါ-</b>"
    user_states[message.from_user.id] = 'w_del_reseller'
    bot.send_message(message.chat.id, res_list, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_del_reseller')
def process_delete_reseller_by_id(message):
    user_id = message.from_user.id
    id_to_del = message.text.strip()
    if not id_to_del.isdigit(): return bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။")
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE tg_id = ? AND role = 'reseller'", (int(id_to_del),))
        row = cursor.fetchone()
        if not row:
            return bot.reply_to(message, "❌ ရှာမတွေ့ပါ။")
        cursor.execute("DELETE FROM users WHERE tg_id = ?", (int(id_to_del),))
        conn.commit()
    finally:
        conn.close()
    
    bot.reply_to(message, f"✅ Reseller: <b>{row[0]}</b> ကို ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML")
    user_states[user_id] = None

def admin_view_all_keys(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys")
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 VIP အကောင့် မရှိသေးပါ။")
    res = f"🌐 <b>VIP အသုံးပြုသူ အားလုံးစာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | {r[2]} လစာ\n"
    bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# 8. BOT POLLING & WEBHOOK EXECUTION
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
