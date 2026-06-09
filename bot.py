# # All-in-One Safe Decryptor & Telegram VIP Management Bot
# Py By @AHLFLK2025 (Directly Synced with Google Apps Script Web App - No GitHub Required)

import os
import re
import json
import struct
import base64
import sqlite3
import requests
import urllib.request
from datetime import datetime, timedelta
from flask import Flask, request, abort
import telebot
from telebot import types

# ==========================================
# 1. CONFIGURATION & CORE BOT SETUP
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TGC_ID")) if os.environ.get("TGC_ID") else None

# Google Apps Script Web App URL
SCRIPT_URL = os.environ.get("SCRIPT_URL")
PUBLIC_URL = os.environ.get("PUBLIC_URL")
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
vip_temp_data = {}
reseller_temp_data = {}

# မူရင်း Menu System တွင် သုံးသော ခလုတ်များ စာရင်း
MENU_BUTTONS = [
    "🌐 VPN Decrypt List", "➕ Add VIP User", "✏️ Edit VIP", "🗑 Delete VIP", "🌐 View All VIPs",
    "👤 Create Reseller", "📊 Reseller List", "✏️ Edit Reseller", "🗑 Delete Reseller", "💰 My Balance",
    "🔑 My VIP Users"
]

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

@app.route('/')
def home(): return "AHLFLK Decrypt Bot Server Running Successfully!"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else: abort(403)

# ==========================================
# 2. CRYPTOGRAPHY ENGINE (XXTEA DECRYPT)
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
    try:
        if isinstance(delta_val, str) and delta_val.strip().startswith('-'):
            return -int(delta_val.replace('-', '').strip(), 16)
        return int(delta_val, 16)
    except: return 0x2e0ba747

def decrypt_inner_base64_recursive(encrypted_str):
    if not isinstance(encrypted_str, str) or len(encrypted_str) < 4: return encrypted_str
    try:
        clean_str = encrypted_str.replace('\n', '').replace('\r', '').strip()
        decoded_bytes = base64.b64decode(clean_str)
        decoded_str = decoded_bytes.decode('utf-8')
        if any(x in decoded_str for x in ["HTTP/", "vless://", "vmess://", "trojan://", "ss://"]): return decoded_str
        return decrypt_inner_base64_recursive(decoded_str)
    except: return encrypted_str

def decrypt_inner_bamar(encrypted_str):
    try:
        data = base64.b64decode(encrypted_str)
        return decrypt_xxtea(data, b"9488362782103982762188", 0x2e0ba747).decode('utf-8', errors='ignore')
    except: return encrypted_str

def process_json_structure(data, method):
    if isinstance(data, dict): return {k: process_json_structure(v, method) for k, v in data.items()}
    elif isinstance(data, list): return [process_json_structure(i, method) for i in data]
    elif isinstance(data, str):
        if method == "bamar": return decrypt_inner_bamar(data)
        elif method == "base64_recursive": return decrypt_inner_base64_recursive(data)
    return data

def perform_decryption(config_url, outer_key, outer_delta_raw, method):
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(config_url, headers=headers)
    with urllib.request.urlopen(req) as response:
        enc_base64 = response.read().decode('utf-8').strip()
    outer_delta = parse_delta(outer_delta_raw)
    enc_data = base64.b64decode(enc_base64)
    dec_bytes = decrypt_xxtea(enc_data, outer_key.encode('utf-8'), outer_delta)
    json_obj = json.loads(dec_bytes.decode('utf-8', errors='ignore').replace('\\/', '/'))
    return {"AHLFLK": "Decrypted By @AHLFLK2025", **process_json_structure(json_obj, method)}

def get_vpn_configs():
    try: return json.loads(VPN_CONFIGS) if VPN_CONFIGS else []
    except: return []

# ==========================================
# 3. DATABASE & GOOGLE SHEET SYNC SYSTEM (GAS Match)
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS auth_keys (
            target_id TEXT PRIMARY KEY, key_string TEXT, vpn_key TEXT, 
            unit_val TEXT, duration_type TEXT, added_by TEXT, created_at TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, username TEXT, role TEXT,
            token_balance INTEGER DEFAULT 0, expire_date TEXT DEFAULT '2099-12-31'
        )''')
        cursor.execute("INSERT OR IGNORE INTO users (tg_id, username, role, token_balance) VALUES (?, ?, ?, ?)", (ADMIN_ID, 'Main_Admin', 'admin', 999999))
        conn.commit()
    finally: conn.close()

def parse_sheet_date(date_str):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try: return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except: continue
    return datetime.now().strftime("%Y-%m-%d")

def pull_data_from_google_sheet():
    if not SCRIPT_URL: return
    try:
        response = requests.get(SCRIPT_URL, timeout=12)
        if response.status_code == 200:
            data_list = response.json()
            if not isinstance(data_list, list): return
            
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_keys")
            cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
            
            for row in data_list:
                # GAS Apps Script ရဲ့ JSON Output Keys တွေအတိုင်း တိုက်ရိုက်ဖတ်ယူခြင်း
                t_id = str(row.get("Users", "")).strip()
                name_str = str(row.get("Name", "")).strip()
                v_key = str(row.get("Key", "")).strip()
                start_date = str(row.get("Start", "")).strip()
                month_val = str(row.get("Month", "")).strip()
                
                if not t_id: continue
                parsed_start = parse_sheet_date(start_date)
                
                # _Reseller ဟု အမည်ပါက Reseller အဖြစ် သတ်မှတ်ဖတ်ယူခြင်း
                if "_Reseller" in name_str:
                    # Month column ထဲက တန်ဖိုးကို Token / Months အဖြစ် ယူဆတွက်ချက်ခြင်း
                    tok_or_mos = int(month_val) if month_val.isdigit() else 1
                    days_to_add = tok_or_mos * 30
                    exp_date_calc = (datetime.strptime(parsed_start, "%Y-%m-%d") + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO users (tg_id, username, role, token_balance, expire_date)
                        VALUES (?, ?, 'reseller', ?, ?)
                    """, (int(t_id), name_str, tok_or_mos, exp_date_calc))
                else:
                    pure_num = "".join(filter(str.isdigit(), month_val)) or "1"
                    cursor.execute("""
                        INSERT OR REPLACE INTO auth_keys (target_id, key_string, vpn_key, unit_val, duration_type, added_by, created_at)
                        VALUES (?, ?, ?, ?, 'Months', 'Sheet_Sync', ?)
                    """, (t_id, name_str, v_key, pure_num, parsed_start))
            conn.commit()
            conn.close()
    except Exception as e: print(f"[-] Sheet Pull Error: {e}")

def send_post_request(payload):
    if not SCRIPT_URL: return False
    try:
        # GAS Apps Script ဆီသို့ JSON Format အမှန်အတိုင်း POST တိုက်ရိုက်ပစ်ခြင်း
        headers = {'Content-Type': 'application/json'}
        response = requests.post(SCRIPT_URL, data=json.dumps(payload), headers=headers, timeout=12)
        return "success" in response.text.lower() or response.status_code == 200
    except: return False

# ==========================================
# 4. RIGHTS & EXPIRE CHECK (Strict Block)
# ==========================================
def is_admin(user_id): return user_id == ADMIN_ID

def is_reseller(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def check_reseller_status(user_id):
    if user_id == ADMIN_ID: return True, 999999, "2099-12-31"
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT token_balance, expire_date FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row: return False, 0, "No Account"
    
    tokens, exp_str = row
    try:
        expire_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        if datetime.now().date() > expire_date:
            return False, tokens, f"Expired ({exp_str})"
        if tokens <= 0:
            return False, tokens, f"Out of Tokens ({exp_str})"
        return True, tokens, exp_str
    except: return False, 0, "Date Error"

def check_vip_status(user_id):
    if user_id == ADMIN_ID: return True, "Unlimited (Admin)"
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role, expire_date FROM users WHERE tg_id = ?", (user_id,))
    u_row = cursor.fetchone()
    if u_row and u_row[0] == 'reseller':
        conn.close()
        is_active, _, exp_msg = check_reseller_status(user_id)
        return is_active, f"Reseller ({exp_msg})"

    cursor.execute("SELECT unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    if not row: return False, "Not VIP"
    
    val, start_str = row
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        days_to_add = int(val) * 30
        expire_date = start_date + timedelta(days=days_to_add)
        if datetime.now().date() <= expire_date:
            return True, expire_date.strftime("%Y-%m-%d")
        return False, "Expired VIP"
    except: return False, "Date Error"

# --- Keyboard Layout ပြင်ဆင်ခြင်း (ပုံပါအတိုင်း အတိအကျ) ---
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if is_admin(user_id):
        # Admin Layout - ခလုတ် ၁၀ ခု (၅ တန်း တိတိကျကျ)
        markup.row(types.KeyboardButton("🌐 VPN Decrypt List"), types.KeyboardButton("➕ Add VIP User"))
        markup.row(types.KeyboardButton("✏️ Edit VIP"), types.KeyboardButton("🗑 Delete VIP"))
        markup.row(types.KeyboardButton("🌐 View All VIPs"), types.KeyboardButton("👤 Create Reseller"))
        markup.row(types.KeyboardButton("📊 Reseller List"), types.KeyboardButton("✏️ Edit Reseller"))
        markup.row(types.KeyboardButton("🗑 Delete Reseller"), types.KeyboardButton("💰 My Balance"))
    elif is_reseller(user_id):
        is_active, _, _ = check_reseller_status(user_id)
        if is_active:
            # Reseller Layout - ၃ တန်း (ပုံစံအတိုင်း My VIP Users အောက်ဆုံးတန်းတွင် ပါဝင်သည်)
            markup.row(types.KeyboardButton("🌐 VPN Decrypt List"), types.KeyboardButton("➕ Add VIP User"))
            markup.row(types.KeyboardButton("✏️ Edit VIP"), types.KeyboardButton("💰 My Balance"))
            markup.row(types.KeyboardButton("🗑 Delete VIP"), types.KeyboardButton("🔑 My VIP Users"))
        else:
            # သက်တမ်းကုန်ပါက Balance တစ်ခုတည်းသာ ကျန်မည်
            markup.row(types.KeyboardButton("💰 My Balance"))
    else:
        is_vip, _ = check_vip_status(user_id)
        if is_vip:
            markup.row(types.KeyboardButton("🌐 VPN Decrypt List"), types.KeyboardButton("💰 My Balance"))
        else:
            markup.row(types.KeyboardButton("💰 My Balance"))
    return markup

# ==========================================
# 5. STATE INTERRUPT FILTER (လုပ်လက်စဖျက်ခြင်း)
# ==========================================
@bot.message_handler(func=lambda msg: msg.text in MENU_BUTTONS)
def handle_menu_interrupts(message):
    uid = message.from_user.id
    text = message.text
    
    # ပြုလုပ်ဆဲ လုပ်ဆောင်ချက်များကို ချက်ချင်း Reset ချဖျက်ပစ်ခြင်း
    user_states[uid] = None
    if uid in vip_temp_data: del vip_temp_data[uid]
    if uid in reseller_temp_data: del reseller_temp_data[uid]
    
    # သက်တမ်းကုန် Reseller ဟု နှိပ်ပါက ကန့်သတ်ခြင်း 
    if is_reseller(uid) and not is_admin(uid):
        is_active, _, _ = check_reseller_status(uid)
        if not is_active and text != "💰 My Balance":
            return bot.reply_to(message, "🚫 သင့်အကောင့်သည် သက်တမ်းကုန်ဆုံးသွားသဖြင့် Balance စစ်ဆေးခြင်းမှလွဲ၍ မည်သည့်အရာမျှ လုပ်ဆောင်ခွင့်မရှိတော့ပါ။", reply_markup=get_main_keyboard(uid))

    # သက်ဆိုင်ရာ နှိပ်လိုက်သော ခလုတ်၏ အလုပ်ကို တိုက်ရိုက်လုပ်ဆောင်စေခြင်း
    if text == "🌐 VPN Decrypt List": show_decrypt_list(message)
    elif text == "💰 My Balance": view_balance(message)
    elif text == "➕ Add VIP User": start_add_vip(message)
    elif text == "✏️ Edit VIP": start_edit_vip(message)
    elif text == "🗑 Delete VIP": start_del_vip(message)
    elif text == "🌐 View All VIPs": view_all_vips_admin(message)
    elif text == "🔑 My VIP Users": view_my_vips(message)
    elif text == "👤 Create Reseller": start_create_reseller(message)
    elif text == "📊 Reseller List": view_resellers(message)
    elif text == "✏️ Edit Reseller": start_edit_reseller(message)
    elif text == "🗑 Delete Reseller": start_del_reseller(message)

# ==========================================
# 6. TELEGRAM BOT HANDLERS & ROUTINES
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    pull_data_from_google_sheet()
    uid = message.from_user.id
    bot.reply_to(message, "👋 AHLFLK Decryptor Bot မှ ကြိုဆိုပါသည်၊", reply_markup=get_main_keyboard(uid))

def show_decrypt_list(message):
    uid = message.from_user.id
    is_vip, exp = check_vip_status(uid)
    if not is_vip and not is_reseller(uid): 
        return bot.reply_to(message, "🚫 သက်တမ်းမရှိပါ။", reply_markup=get_admin_contact_markup())
    
    configs = get_vpn_configs()
    # Inline Keyboard ကို ဘေးချင်းကပ် ၂ ခုစီ စီရန် row_width=2 သတ်မှတ်ခြင်း
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for vpn in configs:
        buttons.append(types.InlineKeyboardButton(vpn['name'], callback_data=f"dec_{vpn['id']}"))
    
    # ခလုတ်များကို ဘေးချင်းကပ် ၂ ခုစီ ဇယားပုံစံအဖြစ် ပေါင်းထည့်ခြင်း
    markup.add(*buttons)
    bot.reply_to(message, f"⚙️ **Available VPN Configs (Exp: {exp}):**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def run_dec_callback(call):
    uid = call.from_user.id
    is_vip, _ = check_vip_status(uid)
    if not is_vip and not is_reseller(uid): 
        return bot.answer_callback_query(call.id, "🚫 သက်တမ်းကုန်ဆုံးပါပြီ။")
    
    vid = call.data.split('_')[1]
    selected = next((v for v in get_vpn_configs() if v["id"] == vid), None)
    if not selected: return
    
    s_msg = bot.send_message(call.message.chat.id, "⏳ Decrypting...")
    try:
        res = perform_decryption(selected["url"], selected["outer_key"], selected["outer_delta"], selected["method"])
        file_path = f"{vid}_dec.json"
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(res, f, indent=4, ensure_ascii=False)
        bot.delete_message(call.message.chat.id, s_msg.message_id)
        with open(file_path, 'rb') as doc: bot.send_document(call.message.chat.id, doc, caption=f"✅ {selected['name']} Decrypted!")
        os.remove(file_path)
    except Exception as e: bot.send_message(call.message.chat.id, f"❌ Error: {e}")

# --- ADD VIP USER (MONTH ONLY) ---
def start_add_vip(message):
    uid = message.from_user.id
    user_states[uid] = 'add_vip_id'
    bot.reply_to(message, "✍️ VIP ပေးမည့်သူ၏ **Telegram ID** ကို ပို့ပေးပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_vip_id')
def add_vip_name(message):
    uid = message.from_user.id
    vip_temp_data[uid] = {"id": message.text.strip()}
    user_states[uid] = 'add_vip_title'
    bot.reply_to(message, "✍️ အသုံးပြုသူ၏ **အမည်** ကို ပို့ပေးပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_vip_title')
def add_vip_value(message):
    uid = message.from_user.id
    vip_temp_data[uid]["name"] = message.text.strip()
    user_states[uid] = 'add_vip_final'
    bot.reply_to(message, "📅 သက်တမ်းပေးလိုသော လအရေအတွက်ကို ဂဏန်းသက်သက် ရိုက်ထည့်ပါ (ဥပမာ- 1 သို့မဟုတ် 3):")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_vip_final')
def save_vip_to_sheet(message):
    uid = message.from_user.id
    val = message.text.strip()
    data = vip_temp_data.get(uid)
    if not data or not val.isdigit(): 
        user_states[uid] = None
        return bot.reply_to(message, "❌ မှားယွင်းမှုရှိပါသည်။ ပြန်စလုပ်ပါ။", reply_markup=get_main_keyboard(uid))
    
    # GAS Code ပါ တကယ့် Parameters (action=sync, users, name, key, start, month) အတိုင်း ပို့ဆောင်ခြင်း
    payload = {
        "action": "sync",
        "users": data["id"],
        "name": data["name"],
        "key": data["id"], # Column C (Key) နေရာတွင် VIP ၏ Telegram ID အား ထည့်သွင်းခြင်း
        "start": datetime.now().strftime("%d/%m/%Y"),
        "month": int(val),
        "added_by": str(uid)
    }
    
    s_msg = bot.reply_to(message, "⏳ Google Sheet သို့ သိမ်းဆည်းနေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ VIP အသုံးပြုသူအား အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    else: 
        bot.edit_message_text("❌ ဒေတာသွင်းရန် မအောင်မြင်ပါ။ Google Script App URL ကို စစ်ဆေးပါ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    user_states[uid] = None
    bot.send_message(message.chat.id, "🏡 ပင်မမီနူးသို့ ပြန်ရောက်ပါပြီ။", reply_markup=get_main_keyboard(uid))

# --- EDIT VIP USER (MONTH ONLY) ---
def start_edit_vip(message):
    uid = message.from_user.id
    user_states[uid] = 'edit_vip_id'
    bot.reply_to(message, "✏️ ပြင်ဆင်လိုသော VIP ၏ **Telegram ID** ကို ရိုက်ပို့ပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'edit_vip_id')
def process_edit_vip(message):
    uid = message.from_user.id
    user_states[uid] = 'edit_vip_final'
    vip_temp_data[uid] = {"id": message.text.strip()}
    bot.reply_to(message, "✍️ ပုံစံသစ်အတိုင်း ပြင်ဆင်ပို့ပေးပါ-\n`အမည်သစ် | သက်တမ်း(လ အရေအတွက်)`\n\nဥပမာ-\n`Aung Aung | 3`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'edit_vip_final')
def save_edit_vip(message):
    uid = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 2 or not parts[1].isdigit(): 
        user_states[uid] = None
        return bot.reply_to(message, "❌ ပုံစံမှားယွင်းနေပါသည်။", reply_markup=get_main_keyboard(uid))
    
    payload = {
        "action": "sync",
        "users": vip_temp_data[uid]["id"],
        "name": parts[0],
        "key": vip_temp_data[uid]["id"],
        "start": datetime.now().strftime("%d/%m/%Y"),
        "month": int(parts[1]),
        "added_by": str(uid)
    }
    s_msg = bot.reply_to(message, "⏳ ဒေတာ ပြင်ဆင်နေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ VIP ပြင်ဆင်မှု အောင်မြင်ပါပြီ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    else: 
        bot.edit_message_text("❌ ပြင်ဆင်ရန် မအောင်မြင်ပါ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    user_states[uid] = None
    bot.send_message(message.chat.id, "🏡 ပင်မမီနူးသို့ ပြန်ရောက်ပါပြီ။", reply_markup=get_main_keyboard(uid))

# --- DELETE VIP USER ---
def start_del_vip(message):
    user_states[message.from_user.id] = 'del_vip_id'
    bot.reply_to(message, "🗑 ဖျက်ထုတ်လိုသော VIP ၏ **Telegram ID** ကို ရိုက်ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(message.from_user.id) == 'del_vip_id')
def process_del_vip(message):
    uid = message.from_user.id
    key_id = message.text.strip()
    payload = {"action": "delete", "key": key_id}
    s_msg = bot.reply_to(message, "⏳ ဖျက်ထုတ်နေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ ဖျက်ထုတ်ပြီးပါပြီ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    else: 
        bot.edit_message_text("❌ မအောင်မြင်ပါ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    user_states[uid] = None
    bot.send_message(message.chat.id, "🏡 ပင်မမီနူးသို့ ပြန်ရောက်ပါပြီ။", reply_markup=get_main_keyboard(uid))

# --- CREATE RESELLER ---
def start_create_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'add_res_id'
    bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller ၏ **Telegram ID** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(message.from_user.id) == 'add_res_id')
def add_res_name(message):
    uid = message.from_user.id
    reseller_temp_data[uid] = {"id": message.text.strip()}
    user_states[uid] = 'add_res_name'
    bot.reply_to(message, "👤 Reseller ၏ **အမည်** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(message.from_user.id) == 'add_res_name')
def add_res_val(message):
    uid = message.from_user.id
    reseller_temp_data[uid]["name"] = message.text.strip()
    user_states[uid] = 'add_res_final'
    bot.reply_to(message, "📅 သက်တမ်း မည်မျှပေးမည်နည်း (လ အရေအတွက် သက်သက် - ဥပမာ 5 သို့မဟုတ် 10):")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_res_final')
def save_reseller(message):
    uid = message.from_user.id
    months = message.text.strip()
    data = reseller_temp_data.get(uid)
    if not data or not months.isdigit(): 
        user_states[uid] = None
        return bot.reply_to(message, "❌ မှားယွင်းမှုရှိပါသည်။", reply_markup=get_main_keyboard(uid))
    
    payload = {
        "action": "sync",
        "users": data["id"],
        "name": f"{data['name']}_Reseller",
        "key": data["id"],
        "start": datetime.now().strftime("%d/%m/%Y"),
        "month": int(months),
        "added_by": str(uid)
    }
    s_msg = bot.reply_to(message, "⏳ Reseller အား Sheet သို့ သိမ်းဆည်းနေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ Reseller အကောင့်အား အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    else: 
        bot.edit_message_text("❌ မအောင်မြင်ပါ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    user_states[uid] = None
    bot.send_message(message.chat.id, "🏡 ပင်မမီနူးသို့ ပြန်ရောက်ပါပြီ။", reply_markup=get_main_keyboard(uid))

# --- EDIT RESELLER ---
def start_edit_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'edit_res_id'
    bot.reply_to(message, "✏️ ပြင်ဆင်လိုသော Reseller ၏ **Telegram ID** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(message.from_user.id) == 'edit_res_id')
def process_edit_reseller(message):
    uid = message.from_user.id
    user_states[uid] = 'edit_res_final'
    reseller_temp_data[uid] = {"id": message.text.strip()}
    bot.reply_to(message, "✍️ ပုံစံသစ်အတိုင်း ပြန်ပို့ပေးပါ-\n`အမည်သစ် | သက်တမ်းတိုးမည့်(လ)`")

@bot.message_handler(func=lambda msg: user_states.get(message.from_user.id) == 'edit_res_final')
def save_edit_reseller(message):
    uid = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 2 or not parts[1].isdigit(): 
        user_states[uid] = None
        return bot.reply_to(message, "❌ ပုံစံမှားယွင်းနေပါသည်။", reply_markup=get_main_keyboard(uid))
    
    payload = {
        "action": "sync",
        "users": reseller_temp_data[uid]["id"],
        "name": f"{parts[0]}_Reseller",
        "key": reseller_temp_data[uid]["id"],
        "start": datetime.now().strftime("%d/%m/%Y"),
        "month": int(parts[1]),
        "added_by": str(uid)
    }
    s_msg = bot.reply_to(message, "⏳ ပြင်ဆင်နေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ Reseller ပြင်ဆင်မှု အောင်မြင်ပါပြီ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    else: 
        bot.edit_message_text("❌ မအောင်မြင်ပါ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    user_states[uid] = None
    bot.send_message(message.chat.id, "🏡 ပင်မမီနူးသို့ ပြန်ရောက်ပါပြီ။", reply_markup=get_main_keyboard(uid))

# --- DELETE RESELLER ---
def start_del_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'del_res_id'
    bot.reply_to(message, "🗑 ဖျက်ထုတ်လိုသော Reseller ၏ **Telegram ID** ကို ရိုက်ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(message.from_user.id) == 'del_res_id')
def process_del_reseller(message):
    uid = message.from_user.id
    res_id = message.text.strip()
    payload = {"action": "delete", "key": res_id}
    s_msg = bot.reply_to(message, "⏳ Sheet မှ ဖျက်ထုတ်နေပါသည်...")
    if send_post_request(payload):
        pull_data_from_google_sheet()
        bot.edit_message_text("✅ Reseller အား အောင်မြင်စွာ ဖြုတ်ချပြီးပါပြီ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    else: 
        bot.edit_message_text("❌ မအောင်မြင်ပါ။", chat_id=message.chat.id, message_id=s_msg.message_id)
    user_states[uid] = None
    bot.send_message(message.chat.id, "🏡 ပင်မမီနူးသို့ ပြန်ရောက်ပါပြီ။", reply_markup=get_main_keyboard(uid))

# --- LIST VIEWING FUNCTIONS ---
def view_my_vips(message):
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 VIP အသုံးပြုသူ မရှိသေးပါ။")
    res = "🔑 **VIP Users List:**\n\n"
    for r in rows:
        try:
            start_date = datetime.strptime(r[3], "%Y-%m-%d").date()
            days = int(r[2]) * 30
            exp = (start_date + timedelta(days=days)).strftime("%Y-%m-%d")
        except: 
            exp = "Unknown"
        res += f"🆔 TG: `{r[0]}` | 👤 Name: `{r[1]}` | 📅 Exp: `{exp}`\n"
    bot.reply_to(message, res, parse_mode="Markdown")

def view_resellers(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role='reseller'")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Reseller မရှိသေးပါ။")
    res = "📊 **Resellers List:**\n\n"
    for r in rows: 
        res += f"🆔 `{r[0]}` | 👤 `{r[1]}` | 🪙 Balance/Months: `{r[2]}` | Exp: `{r[3]}`\n"
    bot.reply_to(message, res, parse_mode="Markdown")

def view_all_vips_admin(message):
    if not is_admin(message.from_user.id): return
    view_my_vips(message)

def view_balance(message):
    pull_data_from_google_sheet()
    uid = message.from_user.id
    
    if is_admin(uid):
        res = f"💰 **Admin Account:**\n\n🆔 Telegram ID: `{uid}`\n📊 Status: `Main Admin`"
    elif is_reseller(uid):
        is_active, tokens, exp = check_reseller_status(uid)
        res = f"💰 **Reseller Account Information:**\n\n🆔 Telegram ID: `{uid}`\n🪙 Token Balance: `{tokens}`\n📅 Expiration: `{exp}`\n📊 Status: `{'Active' if is_active else 'Expired/Blocked'}`"
    else:
        is_vip, exp = check_vip_status(uid)
        res = f"💰 **User Account Information:**\n\n🆔 Telegram ID: `{uid}`\n📊 Status: `{"Active VIP" if is_vip else "Inactive"}`\n📅 Expiration: `{exp}`"
        
    bot.reply_to(message, res, reply_markup=get_main_keyboard(uid), parse_mode="Markdown")

# ==========================================
# 7. RUN EXECUTION
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()
    if PUBLIC_URL:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=f"{PUBLIC_URL}/{BOT_TOKEN}")
        except: pass
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        bot.remove_webhook()
        bot.infinity_polling()
