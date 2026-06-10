# # All-in-One Safe Decryptor & Telegram VIP Management Bot (Google Sheet Sync Mode)
# Py By @AHLFLK2025 (Dual Protection - Connected with Google Apps Script API)

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
SCRIPT_URL = os.environ.get("SCRIPT_URL")  # Web App URL from Google Apps Script
PUBLIC_URL = os.environ.get("PUBLIC_URL")
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}
vip_temp_data = {}

MENU_BUTTONS = ["🌐 VPN Decrypt List", "➕ Add VIP User", "🔑 My VIP Users", "✏️ Edit VIP", "🗑 Delete VIP", "👤 Create Reseller", "📊 Reseller List", "✏️ Edit Reseller", "🗑 Delete Reseller", "🌐 View All VIPs", "💰 My Balance"]

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

@app.route('/')
def home():
    return "VIP & Reseller Google Sheet-Locked Bot is Active!"

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
            unit_val INTEGER, 
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
    if not SCRIPT_URL: return
    try:
        res = requests.get(SCRIPT_URL, timeout=15)
        if res.status_code == 200:
            data_list = res.json()
            if isinstance(data_list, dict) and "error" in data_list: return
            
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            
            existing_vip_owners = {}
            cursor.execute("SELECT target_id, added_by FROM auth_keys WHERE added_by IS NOT NULL")
            for r in cursor.fetchall():
                existing_vip_owners[str(r[0])] = r[1]
                
            cursor.execute("DELETE FROM auth_keys")
            cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
            
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
                        clean_months = int(float(m_val)) if '.' in str(m_val) else int(m_val)
                        # Google Sheet ရဲ့ Month သက်တမ်းကို ယနေ့မှစတွက်ပြီး Expire Target သတ်မှတ်မည်
                        exp_d = (datetime.now() + timedelta(days=clean_months * 30)).strftime("%Y-%m-%d")
                        cursor.execute("INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date) VALUES (?, ?, ?, ?, ?)", 
                                       (int(t_id), clean_name, 'reseller', clean_months, exp_d))
                    except: pass
                
                elif key_apk and key_apk != "RESELLER_ACCOUNT":
                    try:
                        clean_months = int(float(m_val)) if str(m_val).replace('.','',1).isdigit() else 1
                        owner_id = existing_vip_owners.get(t_id, ADMIN_ID)
                        cursor.execute(
                            "INSERT OR REPLACE INTO auth_keys (target_id, key_string, unit_val, duration_type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (t_id, str(k_str).strip(), clean_months, "m", int(owner_id), str(c_at).strip())
                        )
                    except: pass
                        
            conn.commit()
            conn.close()
    except: pass

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
# 4. AUTHENTICATION & TOKEN LOGIC
# ==========================================
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

        cursor.execute("SELECT unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
        row = cursor.fetchone()
        
        if not row: return False, "Not VIP"
        
        unit_val, created_at_str = row
        try:
            if "-" in created_at_str:
                created_date = datetime.strptime(created_at_str.strip(), "%Y-%m-%d").date()
            elif "/" in created_at_str:
                created_date = datetime.strptime(created_at_str.strip(), "%d/%m/%Y").date()
            else:
                created_date = datetime.now().date()
                
            days_to_add = int(unit_val) * 30  # Sheet Formula အတိုင်း လအလိုက်တွက်ချက်ခြင်း
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

def deduct_reseller_tokens(user_id, required_tokens):
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
            except: return False
            
            if tokens >= required_tokens:
                # Local DB update
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
    
    if is_reseller(user_id):
        markup.row(types.KeyboardButton("➕ Add VIP User"), types.KeyboardButton("🔑 My VIP Users"))
        markup.row(types.KeyboardButton("✏️ Edit VIP"), types.KeyboardButton("🗑 Delete VIP"))
        
    if is_admin(user_id):
        markup.row(types.KeyboardButton("💰 My Balance"), types.KeyboardButton("🌐 View All VIPs"))
        markup.row(types.KeyboardButton("👤 Create Reseller"), types.KeyboardButton("📊 Reseller List"))
        markup.row(types.KeyboardButton("✏️ Edit Reseller"), types.KeyboardButton("🗑 Delete Reseller"))
    else:
        markup.row(types.KeyboardButton("💰 My Balance"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[user_id] = None
    pull_data_from_google_sheet()
    
    is_vip, status_msg = check_vip_status(user_id)
    first_name = message.from_user.first_name
    
    welcome_text = f"👋 **မင်္ဂလာပါ {first_name}!**\n\n"
    if is_admin(user_id):
        welcome_text += "👑 **Role:** `Main Admin` [Full Access]\n"
    elif is_reseller(user_id):
        tokens = get_reseller_tokens(user_id)
        welcome_text += f"💼 **Role:** `Reseller Staff` \n🪙 **Credits:** `{tokens}` Months Token\n"
    else:
        welcome_text += "👤 **Role:** `Normal Member` \n"
        
    welcome_text += f"⏳ **VIP Expiry:** `{status_msg}`\n\n"
    welcome_text += "အောက်ပါ Panel ခလုတ်များကို အသုံးပြုနိုင်ပါသည်။"
    
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in MENU_BUTTONS)
def handle_menu_buttons(message):
    user_id = message.from_user.id
    user_states[user_id] = None
    if user_id in reseller_temp_data: del reseller_temp_data[user_id]
    if user_id in vip_temp_data: del vip_temp_data[user_id]
    
    is_vip, _ = check_vip_status(user_id)
    if message.text != "💰 My Balance" and not is_vip and not is_admin(user_id):
        return bot.reply_to(message, "❌ သင်သည် VIP User မဟုတ်သဖြင့် အသုံးပြုခွင့်မရှိပါ။", reply_markup=get_admin_contact_markup())

    if message.text == "🌐 VPN Decrypt List":
        configs = get_vpn_configs()
        if not configs: return bot.reply_to(message, "📭 လတ်တလော Decrypt ပြုလုပ်ရန် Config မရှိသေးပါ။")
        markup = types.InlineKeyboardMarkup()
        for idx, item in enumerate(configs):
            markup.add(types.InlineKeyboardButton(text=item.get("name", f"Config {idx+1}"), callback_with_data=f"dec_{idx}"))
        bot.reply_to(message, "👇 **Decrypt ပြုလုပ်လိုသော Config ကို ရွေးချယ်ပါ:**", reply_markup=markup, parse_mode="Markdown")

    elif message.text == "💰 My Balance":
        pull_data_from_google_sheet()
        is_vip, status_msg = check_vip_status(user_id)
        if is_admin(user_id):
            bot.reply_to(message, f"👑 **Account:** `Main Admin` \n⏳ **Status:** `Life_Time`", parse_mode="Markdown")
        elif is_reseller(user_id):
            tokens = get_reseller_tokens(user_id)
            bot.reply_to(message, f"💼 **Account:** `Reseller` \n🪙 **Balance:** `{tokens}` Month Tokens\n⏳ **Expire:** `{status_msg}`", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"👤 **Account:** `VIP Member` \n⏳ **Expire Date:** `{status_msg}`", parse_mode="Markdown")

    elif message.text == "➕ Add VIP User":
        if not is_reseller(user_id): return
        bot.reply_to(message, "👉 ထည့်သွင်းမည့် VIP ရဲ့ **Telegram ID** ကို ပို့ပေးပါ:")
        user_states[user_id] = "ADD_VIP_ID"

    elif message.text == "🔑 My VIP Users":
        pull_data_from_google_sheet()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys WHERE added_by = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 သင်ကိုယ်တိုင် ထည့်သွင်းထားသော VIP မရှိသေးပါ။")
        res = f"🔑 **သင့်ရဲ့ VIP အသုံးပြုသူစာရင်း ({len(rows)} ဦး):**\n\n"
        for r in rows:
            res += f"🆔 ID: `{r[0]}` | 👤 အမည်: `{r[1]}` | ⏳ `{r[2]}` လပိုင်း\n"
        bot.reply_to(message, res, parse_mode="Markdown")

    elif message.text == "🌐 View All VIPs":
        if not is_admin(user_id): return
        pull_data_from_google_sheet()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, key_string, unit_val FROM auth_keys")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 စနစ်ထဲတွင် VIP မရှိသေးပါ။")
        res = f"🌐 **VIP စုစုပေါင်းစာရင်း ({len(rows)} ဦး):**\n\n"
        for r in rows: res += f"🆔 ` {r[0]} ` | 👤 ` {r[1]} ` | `{r[2]}` Months\n"
        bot.reply_to(message, res, parse_mode="Markdown")

    elif message.text == "🗑 Delete VIP":
        if not is_reseller(user_id): return
        bot.reply_to(message, "👉 ဖြုတ်ထုတ်လိုသော VIP ရဲ့ **Telegram ID** ကို ပို့ပေးပါ:")
        user_states[user_id] = "DEL_VIP_ID"

    elif message.text == "👤 Create Reseller":
        if not is_admin(user_id): return
        bot.reply_to(message, "👉 Reseller ရဲ့ **Telegram ID** ကို ပို့ပေးပါ:")
        user_states[user_id] = "ADD_RES_ID"

    elif message.text == "📊 Reseller List":
        if not is_admin(user_id): return
        pull_data_from_google_sheet()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role='reseller'")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return bot.reply_to(message, "📭 Reseller မရှိသေးပါ။")
        res = f"📊 **Reseller စုစုပေါင်းစာရင်း ({len(rows)} ဦး):**\n\n"
        for r in rows: res += f"🆔 `{r[0]}` | 👤 `{r[1]}` | 🪙 `{r[2]}` လပိုင်း\n"
        bot.reply_to(message, res, parse_mode="Markdown")

    elif message.text == "🗑 Delete Reseller":
        if not is_admin(user_id): return
        bot.reply_to(message, "👉 ဖျက်ထုတ်မည့် Reseller ရဲ့ **Telegram ID** ကို ပို့ပေးပါ:")
        user_states[user_id] = "DEL_RES_ID"

# ==========================================
# 6. STATE HANDLING ENGINE (INPUT PROCESS)
# ==========================================
@bot.message_handler(func=lambda msg: True)
def process_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state: return

    # --- ADD VIP USER PROCESS ---
    if state == "ADD_VIP_ID":
        target = message.text.strip()
        if not target.isdigit(): return bot.reply_to(message, "❌ ID သည် ဂဏန်းသီးသန့် ဖြစ်ရပါမည်။ တစ်ခေါက်ပြန်ပို့ပေးပါ:")
        vip_temp_data[user_id] = {"target_id": target}
        bot.reply_to(message, "👉 ထည့်သွင်းမည့်သူ၏ အမည် သို့မဟုတ် ဖုန်းနံပါတ်ကို ပို့ပေးပါ:")
        user_states[user_id] = "ADD_VIP_NAME"

    elif state == "ADD_VIP_NAME":
        vip_temp_data[user_id]["name"] = message.text.strip()
        bot.reply_to(message, "👉 အသုံးပြုခွင့်ပေးမည့် **သက်တမ်းလအရေအတွက် (ဥပမာ- 1 သို့မဟုတ် 3)** ကို ဂဏန်းသီးသန့် ပို့ပေးပါ:")
        user_states[user_id] = "ADD_VIP_MONTH"

    elif state == "ADD_VIP_MONTH":
        months = message.text.strip()
        if not months.isdigit(): return bot.reply_to(message, "❌ လအရေအတွက်ကို ဂဏန်းသီးသန့် ပို့ပေးပါ:")
        
        req_token = int(months)
        current_tokens = get_reseller_tokens(user_id)
        if not is_admin(user_id) and current_tokens < req_token:
            return bot.reply_to(message, f"❌ သင့်မှာ လက်ကျန် Credit မလုံလောက်ပါ။\nလက်ရှိလက်ကျန်: `{current_tokens}` Tokens", parse_mode="Markdown")
        
        target_id = vip_temp_data[user_id]["target_id"]
        target_name = vip_temp_data[user_id]["name"]
        start_date = datetime.now().strftime("%Y-%m-%d")
        
        # Google Sheet ဘက်သို့ လှမ်းပို့ပြီး အတည်ပြုခြင်း
        success = push_to_google_sheet("sync", target_id, target_name, "DECRYPT_VIP_ACCESS", start_date, req_token)
        if success:
            deduct_reseller_tokens(user_id, req_token)
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ VIP အကောင့် အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ။\n👤 အမည်: `{target_name}`\n⏳ သက်တမ်း: `{req_token}` လ", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Google Sheet Engine ချိတ်ဆက်မှု အဆင်မပြေပါ။ နောက်မှ တစ်ခေါက် ပြန်လည် ကြိုးစားပါ။")
        user_states[user_id] = None

    # --- DELETE VIP PROCESS ---
    elif state == "DEL_VIP_ID":
        target = message.text.strip()
        success = push_to_google_sheet("delete", 0, "", "", "", 0, False) # key matches target via custom params check internally
        # Google Sheet API post for direct key action
        payload = {"action": "delete", "key": "DECRYPT_VIP_ACCESS", "users": target} # Adapt key payload for safety match
        try:
            res = requests.post(SCRIPT_URL, json={"action": "delete", "key": "DECRYPT_VIP_ACCESS"}, timeout=15)
            # Standard custom trigger block
            res_all = requests.get(SCRIPT_URL).json()
            # Find and clear row manually via standard trigger rules
        except: pass
        
        # API သတ်မှတ်ချက်အရ Delete command ကို Google sheet သို့ လှမ်းပို့ခြင်း
        try:
            # Sheet ရဲ့ parameters matching အတိုင်း key နေရာတွင် target text ကို ထည့်သွင်းပြီး delete လုပ်ခိုင်းခြင်း
            res = requests.post(SCRIPT_URL, json={"action": "delete", "key": str(target)}, timeout=15)
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ VIP User ID: `{target}` ကို ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="Markdown")
        except:
            bot.reply_to(message, "❌ ဖျက်ထုတ်မှု မအောင်မြင်ပါ။ API ချိတ်ဆက်မှုကို စစ်ဆေးပါ။")
        user_states[user_id] = None

    # --- CREATE RESELLER PROCESS (ADMIN ONLY) ---
    elif state == "ADD_RES_ID":
        target = message.text.strip()
        if not target.isdigit(): return bot.reply_to(message, "❌ Telegram ID မှာ ဂဏန်းဖြစ်ရပါမည်:")
        reseller_temp_data[user_id] = {"res_id": target}
        bot.reply_to(message, "👉 Reseller ရဲ့ နာမည် သို့မဟုတ် အမှတ်အသား ပို့ပေးပါ:")
        user_states[user_id] = "ADD_RES_NAME"

    elif state == "ADD_RES_NAME":
        reseller_temp_data[user_id]["name"] = message.text.strip() + "_Reseller"
        bot.reply_to(message, "👉 Reseller ကို သတ်မှတ်ပေးမည့် **Credit Token (လအရေအတွက်)** ပို့ပေးပါ:")
        user_states[user_id] = "ADD_RES_TOKENS"

    elif state == "ADD_RES_TOKENS":
        tokens = message.text.strip()
        if not tokens.isdigit(): return bot.reply_to(message, "❌ Credit ကို ဂဏန်းသီးသန့် ပို့ပေးပါ:")
        
        target_id = reseller_temp_data[user_id]["res_id"]
        target_name = reseller_temp_data[user_id]["name"]
        
        success = push_to_google_sheet("sync_reseller", target_id, target_name, "RESELLER_ACCOUNT", "", int(tokens), is_reseller_mode=True)
        if success:
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ Reseller အကောင့်ကို Sheet ထဲသို့ အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ။\n🆔 ID: `{target_id}`\n🪙 Credit: `{tokens}` Months Token", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Google Sheet သို့ အချက်အလက်ပို့ရန် အဆင်မပြေပါ။")
        user_states[user_id] = None

    # --- DELETE RESELLER PROCESS ---
    elif state == "DEL_RES_ID":
        target = message.text.strip()
        try:
            requests.post(SCRIPT_URL, json={"action": "delete", "key": str(target)}, timeout=15)
            pull_data_from_google_sheet()
            bot.reply_to(message, f"✅ Reseller ID: `{target}` ကို စနစ်ထဲမှ ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="Markdown")
        except:
            bot.reply_to(message, "❌ မအောင်မြင်ပါ။")
        user_states[user_id] = None

# ==========================================
# 7. INLINE CALL BACK DATA (DECRYPT ENGINE)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("dec_"))
def handle_decryption_callback(call):
    user_id = call.from_user.id
    is_vip, _ = check_vip_status(user_id)
    if not is_vip and not is_admin(user_id):
        return bot.answer_callback_query(call.id, "❌ သင်သည် VIP မဟုတ်တော့သဖြင့် အသုံးပြုခွင့်မရှိပါ။", show_alert=True)
        
    try:
        idx = int(call.data.split("_")[1])
        configs = get_vpn_configs()
        if idx >= len(configs): return bot.answer_callback_query(call.id, "❌ Config ရှာမတွေ့ပါ။")
        
        target_config = configs[idx]
        bot.answer_callback_query(call.id, "⏳ Decrypting... ပြီးစီးအောင် စောင့်ဆိုင်းပေးပါ...")
        
        decrypted_json = perform_decryption(
            config_url=target_config.get("url"),
            outer_key=target_config.get("key"),
            outer_delta_raw=target_config.get("delta"),
            method=target_config.get("method")
        )
        
        formatted_json = json.dumps(decrypted_json, indent=2, ensure_ascii=False)
        filename = f"Decrypted_{target_config.get('name', 'Config')}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(formatted_json)
            
        with open(filename, "rb") as doc:
            bot.send_document(
                call.message.chat.id, 
                doc, 
                caption=f"✅ **{target_config.get('name')}** ကို အောင်မြင်စွာ Decrypt လုပ်ပြီးပါပြီ။\n\n🔓 Powered By: @AHLFLK2025",
                parse_mode="Markdown"
            )
        os.remove(filename)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Decryption Error: `{str(e)}`", parse_mode="Markdown")

if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()
    
    # Webhook Mode သို့မဟုတ် Polling Mode အဆင်ပြေရာ ရွေးချယ်အသုံးပြုနိုင်ရန်
    if PUBLIC_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")
        Thread(target=run_server).start()
        print("[+] Bot started on Webhook Mode!")
    else:
        bot.remove_webhook()
        print("[+] Bot started on Polling Mode...")
        bot.infinity_polling(skip_pending=True)
