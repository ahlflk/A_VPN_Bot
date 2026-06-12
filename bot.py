# # All-in-One Safe Decryptor & Telegram VIP Management Bot (Fixed UX & Sheet Format)
# Py By @AHLFLK2025

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

SCRIPT_URL = os.environ.get("SCRIPT_URL")
PUBLIC_URL = os.environ.get("PUBLIC_URL")
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
vip_temp_data = {}

# Menu ขလုတ်များကို Role အလိုက် သီးသန့်ခွဲခြားသတ်မှတ်ခြင်း
ADMIN_BUTTONS = [
    ["🌐 VPN Decrypt List"],
    ["➕ Add VIP User", "🔑 My VIP Users"],
    ["✏️ Edit VIP", "🗑 Delete VIP"],
    ["👤 Create Reseller", "📊 Reseller List"],
    ["✏️ Edit Reseller", "🗑 Delete Reseller"],
    ["🌐 View All VIPs", "💰 My Balance"]
]

RESELLER_BUTTONS = [
    ["🌐 VPN Decrypt List"],
    ["➕ Add VIP User", "🔑 My VIP Users"],
    ["✏️ Edit VIP", "🗑 Delete VIP"],
    ["💰 My Balance"]
]

def get_menu_markup(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id == ADMIN_ID:
        for row in ADMIN_BUTTONS:
            markup.add(*[types.KeyboardButton(b) for b in row])
    else:
        for row in RESELLER_BUTTONS:
            markup.add(*[types.KeyboardButton(b) for b in row])
    return markup

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

@app.route('/')
def home():
    return "VIP Bot with Dynamic Keyboards and Persistent VPN Grid is Active!"

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
# CRYPTOGRAPHY & DECRYPTION ENGINE (XXTEA) - မပြောင်းလဲပါ
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
    headers = {'User-Agent': 'Mozilla/5.0'}
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
        return []

# ==========================================
# GOOGLE SHEET & LOCAL SQLITE DATABASE SYNC
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

def pull_data_from_github():
    if not SCRIPT_URL: return
    try:
        res = requests.get(SCRIPT_URL, timeout=15)
        if res.status_code == 200:
            data_list = res.json()
            if isinstance(data_list, dict) and "error" in data_list: return
            
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM auth_keys")
                cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
                
                for row in data_list:
                    t_id = row.get("Users")
                    k_str = row.get("Name") or ""
                    key_apk = row.get("Key") or ""
                    c_at = row.get("Start") or datetime.now().strftime("%d/%m/%Y")
                    m_val = row.get("Month") or 0
                    
                    # ကွက်လပ်ဖြစ်နေသော တန်းများကို လုံးဝ စစ်ထုတ်ဖယ်ရှားရန်
                    if not t_id or str(t_id).strip() == "" or str(k_str).strip() == "":
                        continue
                        
                    t_id = str(t_id).strip()
                    
                    if "_Reseller" in str(k_str):
                        try:
                            clean_name = str(k_str).replace("_Reseller", "").strip()
                            token_val = int(float(key_apk)) if '.' in str(key_apk) else int(key_apk)
                            exp_d = (datetime.now() + timedelta(days=int(float(m_val))*30)).strftime("%d/%m/%Y")
                            cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date) VALUES (?, ?, ?, ?, ?)", 
                                           (int(t_id), clean_name, 'reseller', token_val, exp_d))
                        except: pass
                    else:
                        try:
                            clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 1
                            cursor.execute("INSERT OR IGNORE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)", 
                                           (t_id, str(k_str).strip(), str(clean_months), "m", ADMIN_ID, str(c_at).strip()))
                        except: pass
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        print(f"[-] Pull Error: {str(e)}")

def push_to_google_sheet(action, users, name, key, start, month):
    if not SCRIPT_URL: return False
    payload = {
        "action": action,
        "users": str(users),
        "name": str(name),
        "key": str(key),
        "start": str(start), # 12/06/2026 Format ဝင်လာမည်
        "month": int(month)
    }
    try:
        res = requests.post(SCRIPT_URL, json=payload, timeout=15)
        return res.status_code == 200
    except:
        return False

# ==========================================
# AUTHENTICATION & TOKEN LOGIC
# ==========================================
def calculate_days(unit, duration_type):
    return int(unit) * 30

def is_admin(user_id): 
    return user_id == ADMIN_ID

def is_reseller(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
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
                # Format နှစ်မျိုးလုံးကို အဆင်ပြေအောင် Check ခြင်း
                fmt = "%d/%m/%Y" if '/' in exp_date_str else "%Y-%m-%d"
                expire_date = datetime.strptime(exp_date_str, fmt).date()
                if datetime.now().date() > expire_date: return False, "Expired"
                return True, f"Reseller Staff ({exp_date_str})"
            except: return False, "Date Error"

        cursor.execute("SELECT unit_val, duration_type, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        row = cursor.fetchone()
        if not row: return False, "Not VIP"
        unit_val, duration_type, created_at_str = row
        try:
            fmt = "%d/%m/%Y" if '/' in created_at_str else "%Y-%m-%d"
            created_date = datetime.strptime(created_at_str, fmt).date()
            days_to_add = calculate_days(unit_val, duration_type)
            expire_date = created_date + timedelta(days=days_to_add)
            if datetime.now().date() <= expire_date:
                return True, expire_date.strftime("%d/%m/%Y")
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
                fmt = "%d/%m/%Y" if '/' in exp_date_str else "%Y-%m-%d"
                expire_date = datetime.strptime(exp_date_str, fmt).date()
                if datetime.now().date() > expire_date: return False
            except: return False
            
            if tokens >= required_tokens:
                cursor.execute("UPDATE users SET token_balance = token_balance - ? WHERE tg_id = ?", (required_tokens, user_id))
                conn.commit()
                return True
        return False
    finally:
        conn.close()

def make_vpn_grid_markup():
    """ VPN List ကို ဘေးချင်းကပ် ၂ ခုစီ စီစဉ်ပြီး Layout တည်ဆောက်သည် """
    configs = get_vpn_configs()
    markup = types.InlineKeyboardMarkup()
    if not configs:
        return markup
    
    # ခလုတ် ၂ ခုစီ တွဲ၍ Grid ပြုလုပ်ခြင်း
    row_buttons = []
    for i, cfg in enumerate(configs):
        btn = types.InlineKeyboardButton(text=f"🌐 {cfg['name']}", callback_data=f"dec_{i}")
        row_buttons.append(btn)
        if len(row_buttons) == 2:
            markup.row(*row_buttons)
            row_buttons = []
    if row_buttons:
        markup.row(*row_buttons)
    return markup

# ==========================================
# TELEGRAM INTERFACE & NAVIGATION HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None
    pull_data_from_github()
    
    is_vip, exp_status = check_vip_status(user_id)
    first_name = message.from_user.first_name
    account_status = "Normal User 🙂"
    tokens_line = ""
    
    if is_admin(user_id): 
        account_status = "Main Admin 👑"
    elif is_reseller(user_id):
        account_status = "Reseller Staff 💼"
        tokens = get_reseller_tokens(user_id)
        tokens_line = f"🪙 Credit Balance: <code>{tokens}</code> Tokens\n"

    welcome_text = f"👋 <b>VIP Management Bot မှ ကြိုဆိုပါတယ်ဗျာ!</b>\n\n" \
                   f"📊 <b>အကောင့်အခြေအနေ (Account Info):</b>\n" \
                   f"👑 အဆင့်အတန်း: <b>{account_status}</b>\n" \
                   f"👤 အမည်: <b>{first_name}</b>\n" \
                   f"🆔 Telegram ID: <code>{user_id}</code>\n" \
                   f"{tokens_line}" \
                   f"⏳ VIP သက်တမ်းကုန်မည့်ရက်: <code>{exp_status}</code>\n\n" \
                   f"အောက်ပါ Panel Keyboard ကို အသုံးပြုပြီး ထိန်းချုပ်နိုင်ပါသည်။"

    bot.reply_to(message, welcome_text, reply_markup=get_menu_markup(user_id), parse_mode="HTML")

@bot.message_handler(func=lambda msg: any(msg.text in row for row in ADMIN_BUTTONS))
def handle_menu_clicks(message):
    user_id = message.from_user.id
    text = message.text
    pull_data_from_github()
    
    if text == "💰 My Balance":
        is_vip, exp_status = check_vip_status(user_id)
        tokens = get_reseller_tokens(user_id)
        res = f"💰 <b>သင့်ရဲ့ Balance အခြေအနေ:</b>\n\n" \
              f"🆔 TG ID: <code>{user_id}</code>\n" \
              f"🪙 လက်ကျန် Token: <code>{tokens}</code> Tokens\n" \
              f"📅 သက်တမ်းကုန်ဆုံးရက်: <code>{exp_status}</code>"
        bot.reply_to(message, res, parse_mode="HTML")
        
    elif text == "🌐 VPN Decrypt List":
        configs = get_vpn_configs()
        if not configs:
            return bot.reply_to(message, "📭 Decrypt ရန် VPN Config များ မရှိသေးပါ။")
        bot.reply_to(message, "⬇️ Decrypt ပြုလုပ်လိုသော VPN App ကို ရွေးချယ်ပေးပါ-", reply_markup=make_vpn_grid_markup())

    elif text == "➕ Add VIP User":
        if not is_reseller(user_id): return
        user_states[user_id] = "ADD_VIP_ID"
        bot.reply_to(message, "👤 ထည့်သွင်းမည့် အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🔑 My VIP Users":
        if not is_reseller(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        if is_admin(user_id):
            cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys WHERE target_id != ''")
        else:
            cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys WHERE added_by = ? AND target_id != ''", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 သင်ကိုယ်တိုင် ထည့်သွင်းထားသော VIP အသုံးပြုသူ မရှိသေးပါ။")
        res = f"🔑 <b>သင့်ရဲ့ VIP အသုံးပြုသူ စာရင်း ({len(rows)} ဦး):</b>\n\n"
        for r in rows:
            days = calculate_days(r[2], "m")
            try:
                fmt = "%d/%m/%Y" if '/' in r[3] else "%Y-%m-%d"
                exp = (datetime.strptime(r[3], fmt) + timedelta(days=days)).strftime("%d/%m/%Y")
            except: exp = "Error"
            res += f"🆔 TG ID: <code>{r[0]}</code>\n👤 အမည်: <code>{r[1]}</code>\n📅 Expired: <code>{exp}</code>\n\n"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "✏️ Edit VIP":
        if not is_reseller(user_id): return
        user_states[user_id] = "EDIT_VIP_ID"
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် VIP အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🗑 Delete VIP":
        if not is_reseller(user_id): return
        user_states[user_id] = "DEL_VIP_ID"
        bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် VIP အသုံးပြုသူ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "👤 Create Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "ADD_RES_ID"
        bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller ၏ <b>Telegram ID (သီးသန့် Token ID)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "📊 Reseller List":
        if not is_admin(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role = 'reseller' AND tg_id != ''")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 Reseller စာရင်း မရှိသေးပါ။")
        res = f"📊 <b>Reseller စာရင်းအားလုံး ({len(rows)} ဦး):</b>\n\n"
        for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 {r[1]} | 🪙 {r[2]} Tk | 📅 {r[3]}\n"
        bot.reply_to(message, res, parse_mode="HTML")

    elif text == "✏️ Edit Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "EDIT_RES_ID"
        bot.reply_to(message, "✏️ ပြင်ဆင်မည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🗑 Delete Reseller":
        if not is_admin(user_id): return
        user_states[user_id] = "DEL_RES_ID"
        bot.reply_to(message, "🗑 ဖျက်ထုတ်မည့် Reseller ၏ <b>Telegram ID</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")

    elif text == "🌐 View All VIPs":
        if not is_admin(user_id): return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, duration_type FROM auth_keys WHERE target_id != '' AND key_string != ''")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 VIP အကောင့် မရှိသေးပါ။")
        res = f"🌐 <b>VIP အသုံးပြုသူ အားလုံးစာရင်း ({len(rows)} ဦး):</b>\n\n"
        for r in rows: res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | {r[2]} {r[3]}\n"
        bot.reply_to(message, res, parse_mode="HTML")

# ==========================================
# CONVERSATION STATE FLOW (INPUTS SECTIONS)
# ==========================================
@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) is not None)
def handle_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text.strip()
    
    # ------------------ ADD VIP PROCESS ------------------
    if state == "ADD_VIP_ID":
        vip_temp_data[user_id] = {"target_id": text}
        user_states[user_id] = "ADD_VIP_NAME"
        bot.reply_to(message, "👤 အသုံးပြုသူ၏ <b>အမည် (Name)</b> ကို ရိုက်ထည့်ပေးပါ-", parse_mode="HTML")
        
    elif state == "ADD_VIP_NAME":
        vip_temp_data[user_id]["name"] = text
        user_states[user_id] = "ADD_VIP_MONTH"
        bot.reply_to(message, "⏳ သက်တမ်းသတ်မှတ်ရန် <b>လအရေအတွက် (ဥပမာ- 1 သို့မဟုတ် 3)</b> ကို ထည့်ပေးပါ-", parse_mode="HTML")
        
    elif state == "ADD_VIP_MONTH":
        if not text.isdigit():
            return bot.reply_to(message, "⚠️ ဂဏန်းသီးသန့် (ဥပမာ- 1) ပဲ ထည့်သွင်းပေးပါ-")
        months = int(text)
        required_tokens = months
        
        if not deduct_reseller_tokens_by_days(user_id, required_tokens):
            user_states[user_id] = None
            return bot.reply_to(message, "❌ သင့်မှာ လုံလောက်တဲ့ Token မရှိပါ သို့မဟုတ် သက်တမ်းကုန်နေပါသည်။")
            
        target_id = vip_temp_data[user_id]["target_id"]
        name = vip_temp_data[user_id]["name"]
        
        # Format ကို 12/06/2026 သို့ ပြောင်းလဲသတ်မှတ်ခြင်း
        start_date = datetime.now().strftime("%d/%m/%Y")
        
        success = push_to_google_sheet("sync", target_id, name, target_id, start_date, months)
        if success:
            pull_data_from_github()
            bot.reply_to(message, f"✅ VIP အကောင့် အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။\n🆔 TG ID: <code>{target_id}</code>\n👤 အမည်: <code>{name}</code>\n⏳ သက်တမ်း: <code>{months}</code> လ", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Google Sheet သို့ Data ပို့ဆောင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # ------------------ EDIT VIP PROCESS ------------------
    elif state == "EDIT_VIP_ID":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string FROM auth_keys WHERE target_id = ?", (text,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            user_states[user_id] = None
            return bot.reply_to(message, "❌ အဆိုပါ VIP ID အား ရှာမတွေ့ပါ။")
        vip_temp_data[user_id] = {"target_id": text}
        user_states[user_id] = "EDIT_VIP_MONTH"
        bot.reply_to(message, "✏️ တိုးမြှင့်မည့် <b>လအရေအတွက် (ဥပမာ- 2)</b> ကို ရိုက်ထည့်ပါ-", parse_mode="HTML")

    elif state == "EDIT_VIP_MONTH":
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းပဲ ရိုက်ထည့်ပေးပါ-")
        months = int(text)
        if not deduct_reseller_tokens_by_days(user_id, months):
            user_states[user_id] = None
            return bot.reply_to(message, "❌ Token မလုံလောက်ပါ။")
            
        target_id = vip_temp_data[user_id]["target_id"]
        start_date = datetime.now().strftime("%d/%m/%Y")
        success = push_to_google_sheet("sync", target_id, "Edit_VIP", target_id, start_date, months)
        if success:
            pull_data_from_github()
            bot.reply_to(message, "✅ VIP အကောင့် သက်တမ်း တိုးမြှင့်ပြီးပါပြီ။")
        else:
            bot.reply_to(message, "❌ ပြင်ဆင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # ------------------ DELETE VIP PROCESS ------------------
    elif state == "DEL_VIP_ID":
        target_id = text
        success = push_to_google_sheet("delete", target_id, "Delete", target_id, "", 0)
        if success:
            pull_data_from_github()
            bot.reply_to(message, f"✅ VIP ID: <code>{target_id}</code> အား ဖျက်သိမ်းပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ ဖျက်သိမ်းမှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # ------------------ CREATE RESELLER PROCESS (ADMINONLY) ------------------
    elif state == "ADD_RES_ID":
        if not is_admin(user_id): return
        reseller_temp_data[user_id] = {"tg_id": text}
        user_states[user_id] = "ADD_RES_NAME"
        bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller အမည် ကို ရိုက်ထည့်ပေးပါ-")

    elif state == "ADD_RES_NAME":
        if not is_admin(user_id): return
        reseller_temp_data[user_id]["username"] = text
        user_states[user_id] = "ADD_RES_MONTH"
        bot.reply_to(message, "⏳ Reseller သက်တမ်းသတ်မှတ်ရန် <b>လအရေအတွက် (ဥပမာ- 12)</b> ထည့်ပေးပါ-", parse_mode="HTML")

    elif state == "ADD_RES_MONTH":
        if not is_admin(user_id): return
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းထည့်ပါ-")
        reseller_temp_data[user_id]["month"] = int(text)
        user_states[user_id] = "ADD_RES_TOKENS"
        bot.reply_to(message, "🪙 ထည့်သွင်းပေးမည့် <b>Token ပမာဏ (Credits)</b> ကို ရိုက်ထည့်ပါ-", parse_mode="HTML")

    elif state == "ADD_RES_TOKENS":
        if not is_admin(user_id): return
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းထည့်ပါ-")
        tokens = int(text)
        r_id = reseller_temp_data[user_id]["tg_id"]
        r_name = reseller_temp_data[user_id]["username"] + "_Reseller"
        months = reseller_temp_data[user_id]["month"]
        start_date = datetime.now().strftime("%d/%m/%Y")
        
        success = push_to_google_sheet("sync_reseller", r_id, r_name, str(tokens), start_date, months)
        if success:
            pull_data_from_github()
            bot.reply_to(message, f"✅ Reseller အကောင့် ဖန်တီးပြီးပါပြီ။\n🆔 ID: <code>{r_id}</code>\n🪙 တိုကင်: {tokens} Tk\n⏳ သက်တမ်း: {months} လ", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Google Sheet ချိတ်ဆက်မှု လွဲချော်နေပါသည်။")
        user_states[user_id] = None

    # ------------------ EDIT RESELLER PROCESS ------------------
    elif state == "EDIT_RES_ID":
        if not is_admin(user_id): return
        reseller_temp_data[user_id] = {"tg_id": text}
        user_states[user_id] = "EDIT_RES_TOKENS"
        bot.reply_to(message, "🪙 တိုးမြှင့်ထည့်သွင်းမည့် <b>Token အရေအတွက်</b> ကို ရိုက်ထည့်ပါ-", parse_mode="HTML")

    elif state == "EDIT_RES_TOKENS":
        if not is_admin(user_id): return
        if not text.isdigit(): return bot.reply_to(message, "⚠️ ဂဏန်းထည့်ပါ-")
        tokens = int(text)
        r_id = reseller_temp_data[user_id]["tg_id"]
        start_date = datetime.now().strftime("%d/%m/%Y")
        success = push_to_google_sheet("sync_reseller", r_id, "Edit_Reseller", str(tokens), start_date, 1)
        if success:
            pull_data_from_github()
            bot.reply_to(message, "✅ Reseller တိုကင် ဖြည့်သွင်းမှု အောင်မြင်ပါသည်။")
        else:
            bot.reply_to(message, "❌ ပြင်ဆင်မှု မအောင်မြင်ပါ။")
        user_states[user_id] = None

    # ------------------ DELETE RESELLER PROCESS ------------------
    elif state == "DEL_RES_ID":
        if not is_admin(user_id): return
        r_id = text
        success = push_to_google_sheet("delete_reseller", r_id, "RESELLER_ACCOUNT", "RESELLER_ACCOUNT", "", 0)
        if success:
            pull_data_from_github()
            bot.reply_to(message, f"✅ Reseller ID: <code>{r_id}</code> အား ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ ဖျက်သိမ်းမှု လွဲချော်ခဲ့သည်။")
        user_states[user_id] = None

# ==========================================
# INLINE CALLBACK FOR DECRYPTION ENGINE
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("dec_"))
def callback_decrypt(call):
    user_id = call.from_user.id
    is_vip, exp_status = check_vip_status(user_id)
    if not is_vip:
        return bot.answer_callback_query(call.id, f"❌ သင်သည် VIP မဟုတ်ပါသဖြင့် အသုံးပြုနိုင်ခြင်းမရှိပါ။ ({exp_status})", show_alert=True)
        
    try:
        idx = int(call.data.split("_")[1])
        configs = get_vpn_configs()
        cfg = configs[idx]
        
        bot.answer_callback_query(call.id, "⏳ Decrypting Configuration...")
        
        # စာသားများ မပြောင်းလဲစေဘဲ နဂိုအတိုင်း Decrypt လုပ်ဆောင်ခြင်း
        decrypted_data = perform_decryption(cfg['url'], cfg['outer_key'], cfg['outer_delta'], cfg['method'])
        json_str = json.dumps(decrypted_data, indent=2, ensure_ascii=False)
        
        file_name = f"{cfg['id']}_decrypted.json"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(json_str)
            
        with open(file_name, "rb") as f:
            bot.send_document(
                call.message.chat.id, 
                f, 
                caption=f"✅ <b>{cfg['name']} Decrypted Successfully!</b>\n⚙️ Method: <code>{cfg['method']}</code>\n👤 Request By: <code>{user_id}</code>", 
                parse_mode="HTML"
            )
        os.remove(file_name)
        
        # 🌟 စာရင်းပြန်မပျောက်စေရန် ဤနေရာတွင် Inline Grid Markup ကို ပြန်ထုတ်ပေးထားပါသည်
        bot.send_message(call.message.chat.id, "⬇️ ထပ်မံလုပ်ဆောင်လိုသော VPN App ကို ရွေးချယ်နိုင်ပါသေးသည်-", reply_markup=make_vpn_grid_markup())
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Decrypt လုပ်ဆောင်မှု လွဲချော်သွားပါသည်-\n<code>{str(e)}</code>", parse_mode="HTML", reply_markup=get_admin_contact_markup())

# ==========================================
# BOT POLLING & WEBHOOK EXECUTION
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_github()
    
    if PUBLIC_URL and BOT_TOKEN:
        bot.remove_webhook()
        bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")
        run_server()
    else:
        bot.remove_webhook()
        Thread(target=run_server).start()
        bot.infinity_polling(skip_pending=True)
