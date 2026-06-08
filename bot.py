# # All-in-One Safe Decryptor & Telegram VIP Management Bot (With Reseller Edit & Expiry Date)
# Py By @AHLFLK2025 (Fully Fixed Reseller Bypass Leak - Token & Date Dual Protection)
# Updated: Integrated flawlessly with Single-Sheet Google Apps Script System

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

# Google Apps Script Web App URL
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
    return "Decrypt & VPN APK Sheet-Linked Bot is Active!"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

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
# 3. DATABASE & GOOGLE SHEETS SYNC SYSTEM
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

def parse_sheet_date(date_str):
    """ Sheet ထဲက ရက်စွဲ Format မျိုးစုံကို စစ်ထုတ်ဖတ်ယူခြင်း """
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except:
            continue
    return datetime.now().strftime("%Y-%m-%d")

def pull_data_from_google_sheet():
    """ Google Sheet တစ်ခုတည်းကနေ VIP တွေနဲ့ Reseller တွေကို စနစ်တကျ ခွဲထုတ်ဖတ်ယူခြင်း """
    if not SCRIPT_URL: return
    try:
        response = requests.get(SCRIPT_URL, timeout=12)
        if response.status_code == 200:
            data_list = response.json()
            if not isinstance(data_list, list): return
            
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            
            # Local DB ကို ရှင်းပြီး အသစ်ပြန်ထည့်မယ် (Admin ကလွဲရင်)
            cursor.execute("DELETE FROM auth_keys")
            cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
            
            for row in data_list:
                t_id = row.get("Users")
                k_str = row.get("Name") or ""
                key_apk = row.get("Key") or ""
                start_date = row.get("Start") or ""
                month_val = row.get("Month") or "0"
                exp_date_raw = row.get("Expiration") or ""
                
                # Sheet ထဲက Row အပို အလွတ် Error တွေကို ကျော်မယ်
                if not t_id or str(t_id).strip() == "" or "1899" in str(exp_date_raw) or "-4618" in str(row.get("Valid")):
                    continue
                
                t_id_str = str(t_id).strip()
                k_str = k_str.strip()
                
                # ပုံစံတူ ရက်စွဲဖြစ်အောင် ပြောင်းမယ်
                parsed_start = parse_sheet_date(start_date)
                parsed_exp = parse_sheet_date(exp_date_raw)
                
                # Name ထဲမှာ _Reseller ပါရင် Reseller Table ထဲထည့်မယ်
                if "_Reseller" in k_str:
                    try:
                        tg_id_val = int(t_id_str)
                        # Month ထဲက တန်ဖိုးကို Token အဖြစ်ယူဆပြီး ရက်စွဲကို သက်တမ်းကုန်ရက်အဖြစ် သတ်မှတ်မယ်
                        cursor.execute("""
                            INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date)
                            VALUES (?, ?, 'reseller', ?, ?)
                        """, (tg_id_val, k_str, int(month_val) if month_val.isdigit() else DEFAULT_CREDITS, parsed_exp))
                    except:
                        continue
                else:
                    # သာမန် VIP User ဖြစ်ရင် auth_keys ထဲထည့်မယ်
                    cursor.execute("""
                        INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at)
                        VALUES (?, ?, ?, 'm', ?, ?)
                    """, (t_id_str, k_str, month_val, ADMIN_ID, parsed_start))
                    
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"[-] Pull Data Sheet Error: {str(e)}")

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
        # ၁။ Reseller ဟုတ်မဟုတ် အရင်စစ်မယ်
        cursor.execute("SELECT role, token_balance, expire_date FROM users WHERE tg_id = ?", (user_id,))
        user_row = cursor.fetchone()
        
        if user_row and user_row[0] == 'reseller':
            exp_date_str = user_row[2]
            try:
                expire_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
                if datetime.now().date() > expire_date:
                    return False, "Expired (Reseller Out)"
                return True, f"Reseller Staff ({exp_date_str})"
            except:
                return False, "Date Error"

        # ၂။ သာမန် VIP ဟုတ်မဟုတ် ဆက်စစ်မယ်
        cursor.execute("SELECT unit_val, duration_type, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        row = cursor.fetchone()
        
        if not row: return False, "Not VIP"
        
        unit_val, duration_type, created_at_str = row
        try:
            created_date = datetime.strptime(created_at_str, "%Y-%m-%d").date()
            days_to_add = calculate_days(unit_val, duration_type)
            expire_date = created_date + timedelta(days=days_to_add)
            
            if datetime.now().date() <= expire_date:
                return True, expire_date.strftime("%Y-%m-%d")
            else:
                return False, "Expired"
        except: return False, "Error Check"
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
        bot_name = "Safe Decryptor VIP Bot"
    
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
# 6. RESELLER & ADMIN INTERACTION (POST TO SHEET)
# ==========================================
def send_post_request(payload):
    if not SCRIPT_URL: return False
    try:
        response = requests.post(SCRIPT_URL, data=payload, timeout=12)
        if response.status_code == 200:
            return "success" in response.text.lower()
    except Exception as e:
        print(f"[-] POST Request Error: {str(e)}")
    return False

def cmd_add_vip(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_google_sheet()
    
    current_tokens = get_reseller_tokens(user_id)
    user_states[user_id] = 'w_vip'
    
    msg_text = (
        f"✍️ <b>VIP အသစ်ဆောက်ရန် ပုံစံစာသားပေးပို့ပါ-</b>\n"
        f"🪙 လက်ကျန်: <code>{current_tokens}</code> Tokens\n\n"
        f"✍️ Format အတိုင်း အောက်ပါစာသားကို ကူးယူပြင်ဆင်ပြီး ပို့နိုင်ပါသည်-\n"
        f"<code>TelegramID | VIP_Name | Key/APK_ID | Month</code>\n\n"
        f"👇 <b>နမူနာ ကို နှိပ်ပြီး Copy ယူနိုင်သည်-</b>\n"
        f"<code>123456789 | Bbb | 53269990e11f5008 | 5</code>"
    )
    bot.reply_to(message, msg_text, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_vip')
def process_vip_add(message):
    user_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4 or not parts[0].isdigit() or not parts[3].isdigit():
        return bot.reply_to(message, "❌ ပုံစံမှားနေပါသည်။ TelegramID | VIP_Name | Key | Month အတိုင်း သေချာပြန်ပို့ပေးပါ။")
    
    target_vip_id, name, key_val, month_val = parts[0], parts[1], parts[2], parts[3]
    pull_data_from_google_sheet()
    
    # API ပုံစံအတိုင်း POST Payload တည်ဆောက်ခြင်း
    payload = {
        "action": "insert",
        "user": target_vip_id,
        "name": name,
        "key": key_val,
        "start": datetime.now().strftime("%d/%m/%Y"),
        "month": month_val
    }
    
    status_msg = bot.reply_to(message, "⏳ Google Sheet သို့ သိမ်းဆည်းနေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text(f"✅ <b>VIP User [ {name} ] အား Google Sheet သို့ အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ!</b>", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
    else:
        bot.edit_message_text("❌ Google Sheet သို့ ဒေတာပို့ရန် မအောင်မြင်ပါ။ Script Web App အား စစ်ဆေးပါ။", chat_id=message.chat.id, message_id=status_msg.message_id)
    user_states[user_id] = None

def cmd_my_vips(message):
    if not is_reseller(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val FROM auth_keys")
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 VIP အကောင့်မရှိသေးပါ။")
    res = "👥 <b>...VIP အသုံးပြုသူများစာရင်း...</b>\n\n"
    for r in rows: res += f"• ID: <code>{r[0]}</code> -> နာမည်: <b>{r[1]}</b> ({r[2]} လပိုင်း)\n"
    bot.reply_to(message, res, parse_mode="HTML")

def cmd_my_balance(message):
    user_id = message.from_user.id
    pull_data_from_google_sheet()
    is_vip, exp_status = check_vip_status(user_id)
    
    response_text = f"📊 <b>သင့်အကောင့်အခြေအနေ (Account Info):</b>\n\n" \
                    f"👤 အမည်: <b>{message.from_user.first_name}</b>\n" \
                    f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                    f"⏳ သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>\n"
                    
    if is_reseller(user_id) and user_id != ADMIN_ID:
        tokens = get_reseller_tokens(user_id)
        response_text += f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n"

    bot.reply_to(message, response_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

def admin_reseller_edit_vip_menu(message):
    bot.reply_to(message, "💡 VIP အကောင့်သက်တမ်း တိုးမြှင့်လိုပါက <b>➕ Add VIP User</b> ကိုနှိပ်ပြီး ID တူ၊ Name တူဖြင့် လိုချင်သော လ အရေအတွက်ကို ထပ်မံဖြည့်စွက်ပေးပို့လိုက်ရုံဖြင့် Google Sheet မှ အလိုအလျောက် သက်တမ်းတိုးပေးသွားမည် ဖြစ်သည်။")

def admin_reseller_delete_vip_menu(message):
    user_id = message.from_user.id
    if not is_reseller(user_id): return
    pull_data_from_google_sheet()
    
    user_states[user_id] = 'w_del_vip'
    bot.reply_to(message, "🗑 <b>ဖျက်ထုတ်လိုသော VIP ၏ 'Key (သို့မဟုတ်) APK ID' ကို ရိုက်ပို့ပေးပါ-</b>", parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_del_vip')
def process_delete_vip_by_id(message):
    user_id = message.from_user.id
    key_to_del = message.text.strip()
    
    payload = {"action": "delete", "key": key_to_del}
    status_msg = bot.reply_to(message, "⏳ Google Sheet မှ ဖျက်ထုတ်နေပါသည်...")
    
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ Google Sheet မှ အောင်မြင်စွာ ဖျက်ထုတ်ပြီးပါပြီ။", chat_id=message.chat.id, message_id=status_msg.message_id)
    else:
        bot.edit_message_text("❌ ဖျက်ထုတ်ရန် မအောင်မြင်ပါ။ Key မှန်ကန်မှု ရှိမရှိ ပြန်စစ်ပါ။", chat_id=message.chat.id, message_id=status_msg.message_id)
    user_states[user_id] = None

# ==========================================
# 7. MAIN ADMIN PANEL: MANAGE RESELLERS
# ==========================================
def admin_create_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'w_reseller'
    
    r_msg = (
        f"👤 <b>Reseller အသစ်ဖန်တီးရန် စာသားပေးပို့ပါ-</b>\n\n"
        f"✍️ Format လမ်းညွှန်-\n"
        f"<code>TelegramID | ResellerName_Reseller | Tokens | Month(သက်တမ်းလ)</code>\n\n"
        f"👇 <b>နမူနာ- (နာမည်အနောက်တွင် _Reseller မဖြစ်မနေ ထည့်ပေးပါ)</b>\n"
        f"<code>6655182165 | ABC_Reseller | RESELLER_ACCOUNT | 1</code>"
    )
    bot.reply_to(message, r_msg, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'w_reseller')
def process_admin_reseller(message):
    admin_id = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 4:
        return bot.reply_to(message, "❌ ပုံစံမှားယွင်းနေပါသည်။ စာသားပြန်လည်စစ်ဆေးပါ။")
        
    payload = {
        "action": "insert",
        "user": parts[0],
        "name": parts[1],
        "key": parts[2],
        "start": datetime.now().strftime("%d/%m/%Y"),
        "month": parts[3]
    }
    
    status_msg = bot.reply_to(message, "⏳ Reseller အား Sheet သို့ သိမ်းဆည်းနေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ Reseller အကောင့်ကို အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။", chat_id=message.chat.id, message_id=status_msg.message_id)
    else:
        bot.edit_message_text("❌ အကောင့်ဆောက်ရန် မအောင်မြင်ပါ။", chat_id=message.chat.id, message_id=status_msg.message_id)
    user_states[admin_id] = None

def admin_view_resellers(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role='reseller'")
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 <b>Reseller စာရင်း လုံးဝမရှိသေးပါ။</b>", parse_mode="HTML")
    res = "👥 <b>Reseller စာရင်းများနှင့် သက်တမ်းများ:</b>\n\n"
    for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 <b>{r[1]}</b>\n🪙 {r[2]} Tokens | ⏳ Exp: <code>{r[3]}</code>\n\n"
    bot.reply_to(message, res, parse_mode="HTML")

def admin_edit_reseller_menu(message):
    bot.reply_to(message, "💡 Reseller ၏ တိုကင် သို့မဟုတ် သက်တမ်းပြင်ဆင်ရန် <b>👤 Create Reseller</b> ကိုနှိပ်၍ သက်ဆိုင်ရာ ID ၊ နာမည် တူညီစွာဖြင့် လအသစ် ပြောင်းလဲပို့ပေးလိုက်ရုံဖြင့် အလိုအလျောက် အပ်ဒိတ်ဖြစ်သွားမည် ဖြစ်သည်။")

def admin_delete_reseller_menu(message):
    admin_reseller_delete_vip_menu(message)

def admin_view_all_keys(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val FROM auth_keys")
        rows = cursor.fetchall()
    finally:
        conn.close()
    if not rows: return bot.reply_to(message, "📭 <b>VIP အကောင့် မရှိသေးပါ။</b>", parse_mode="HTML")
    res = f"🌐 <b>VIP အသုံးပြုသူ အားလုံးစာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | {r[2]} လပိုင်းသက်တမ်း\n"
    bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# 8. BOT POLLING & WEBHOOK EXECUTION
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()  # Start Sync
    if PUBLIC_URL:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")
        except Exception as e: print(f"[-] Webhook Error: {str(e)}")
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        bot.remove_webhook()
        bot.infinity_polling()
