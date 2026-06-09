# # All-in-One Safe Decryptor & Telegram VIP Management Bot (With Reseller Edit & Expiry Date)
# Py By @AHLFLK2025 (Fully Fixed Reseller Bypass Leak - Token & Date Dual Protection)

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

GITHUB_TOKEN = os.environ.get("GH_TOKEN")
REPO_OWNER = "ahlflk"
REPO_NAME = "AHLFLK2025_VPN_Decrypt_Bot"
FILE_PATH = "key.txt"
RESELLER_FILE_PATH = "resellers.txt"

PUBLIC_URL = os.environ.get("PUBLIC_URL")
VPN_CONFIGS = os.environ.get("VPN_CONFIGS")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask('')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "keys_management.db")

user_states = {}
reseller_temp_data = {}

# မူရင်း Menu Buttons နေရာချထားပုံအတိုင်း ရာနှုန်းပြည့် ပြန်ထားခြင်း
MENU_BUTTONS = [
    "🌐 VPN Decrypt List", "➕ Add VIP User", "✏️ Edit VIP", "🗑 Delete VIP", "🌐 View All VIPs",
    "👤 Create Reseller", "📊 Reseller List", "✏️ Edit Reseller", "🗑 Delete Reseller", "💰 My Balance"
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
# 3. DATABASE & GITHUB SYNC SYSTEM
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

def github_api_request(path, method="GET", data=None):
    if not GITHUB_TOKEN: return None
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=10)
            return r.json() if r.status_code == 200 else None
        elif method == "PUT":
            r = requests.put(url, headers=headers, json=data, timeout=10)
            return r.status_code in [200, 201]
    except: return None

def pull_data_from_github():
    # Key.txt Sync
    res = github_api_request(FILE_PATH)
    if res and 'content' in res:
        try:
            lines = base64.b64decode(res['content']).decode('utf-8').split('\n')
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_keys")
            for line in lines:
                if not line.strip(): continue
                parts = line.split('|')
                if len(parts) >= 6:
                    cursor.execute("INSERT OR REPLACE INTO auth_keys VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                   (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6] if len(parts)>6 else datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            conn.close()
        except: pass

    # Resellers.txt Sync
    res2 = github_api_request(RESELLER_FILE_PATH)
    if res2 and 'content' in res2:
        try:
            lines = base64.b64decode(res2['content']).decode('utf-8').split('\n')
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE tg_id != ?", (ADMIN_ID,))
            for line in lines:
                if not line.strip(): continue
                parts = line.split('|')
                if len(parts) >= 4:
                    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?)", 
                                   (int(parts[0]), parts[1], parts[2], int(parts[3]), parts[4] if len(parts)>4 else '2099-12-31'))
            conn.commit()
            conn.close()
        except: pass

def sync_keys_to_github():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    lines = [f"{r[0]}|{r[1]}|{r[2]}|{r[3]}|{r[4]}|{r[5]}|{r[6]}" for r in rows]
    content = "\n".join(lines)
    
    res = github_api_request(FILE_PATH)
    sha = res['sha'] if res and 'sha' in res else None
    payload = {"message": "Update Keys", "content": base64.b64encode(content.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    github_api_request(FILE_PATH, "PUT", payload)

def sync_resellers_to_github():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username, role, token_balance, expire_date FROM users WHERE tg_id != ?", (ADMIN_ID,))
    rows = cursor.fetchall()
    conn.close()
    lines = [f"{r[0]}|{r[1]}|{r[2]}|{r[3]}|{r[4]}" for r in rows]
    content = "\n".join(lines)
    
    res = github_api_request(RESELLER_FILE_PATH)
    sha = res['sha'] if res and 'sha' in res else None
    payload = {"message": "Update Resellers", "content": base64.b64encode(content.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    github_api_request(RESELLER_FILE_PATH, "PUT", payload)

# ==========================================
# 4. RIGHTS & EXPIRE CHECK (Dual Layer)
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
    if not row: return False, 0, "No Reseller Account Found"
    
    tokens, exp_str = row
    try:
        expire_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        if datetime.now().date() > expire_date:
            return False, tokens, f"Expired on {exp_str}"
        if tokens <= 0:
            return False, tokens, "Out of Tokens/Credits"
        return True, tokens, exp_str
    except: return False, 0, "Date Format Error"

def check_vip_status(user_id):
    if user_id == ADMIN_ID: return True, "Unlimited (Admin)"
    
    # Reseller ဖြစ်ပါက သက်တမ်းကို အရင်စစ်ဆေးရန်
    if is_reseller(user_id):
        is_active, _, exp_msg = check_reseller_status(user_id)
        return is_active, f"Reseller ({exp_msg})"

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT unit_val, duration_type, created_at FROM auth_keys WHERE target_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    if not row: return False, "No Active VIP Plan"
    
    val, dtype, start_str = row
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        # Month system သီးသန့်ဖြင့် ရက်ပေါင်း ၃၀ စီ တွက်ချက်ခြင်း
        days_to_add = int(val) * 30
        expire_date = start_date + timedelta(days=days_to_add)
        if datetime.now().date() <= expire_date:
            return True, expire_date.strftime("%Y-%m-%d")
        return False, f"Expired on {expire_date}"
    except: return False, "Date Calculation Error"

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # မူရင်း Keyboard Row တည်ဆောက်ပုံအတိုင်း ခလုတ်များကို သေသပ်စွာ နေရာချခြင်း
    if is_admin(user_id):
        markup.row(types.KeyboardButton("🌐 VPN Decrypt List"), types.KeyboardButton("💰 My Balance"))
        markup.row(types.KeyboardButton("➕ Add VIP User"), types.KeyboardButton("✏️ Edit VIP"))
        markup.row(types.KeyboardButton("🗑 Delete VIP"), types.KeyboardButton("🌐 View All VIPs"))
        markup.row(types.KeyboardButton("👤 Create Reseller"), types.KeyboardButton("📊 Reseller List"))
        markup.row(types.KeyboardButton("✏️ Edit Reseller"), types.KeyboardButton("🗑 Delete Reseller"))
    elif is_reseller(user_id):
        is_active, _, _ = check_reseller_status(user_id)
        if is_active:
            markup.row(types.KeyboardButton("🌐 VPN Decrypt List"), types.KeyboardButton("💰 My Balance"))
            markup.row(types.KeyboardButton("➕ Add VIP User"), types.KeyboardButton("✏️ Edit VIP"))
            markup.row(types.KeyboardButton("🗑 Delete VIP"), types.KeyboardButton("🔑 My VIP Users"))
        else:
            # Reseller သက်တမ်းကုန်ပါက Balance တစ်ခုပဲ နှိပ်ခွင့်ပေးမည်
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
@bot.message_handler(func=lambda msg: msg.text in MENU_BUTTONS or msg.text == "🔑 My VIP Users")
def handle_menu_interrupts(message):
    uid = message.from_user.id
    text = message.text
    
    # State ကို အရင်ဆုံး ရှင်းထုတ်ပစ်သည်
    user_states[uid] = None
    if uid in reseller_temp_data: del reseller_temp_data[uid]
    
    # သက်တမ်းကုန် Reseller များအတွက် Block Logic
    if is_reseller(uid) and not is_admin(uid):
        is_active, _, _ = check_reseller_status(uid)
        if not is_active and text != "💰 My Balance":
            return bot.reply_to(message, "🚫 သင့်အကောင့်သည် သက်တမ်းကုန်ဆုံးသွားသဖြင့် Balance စစ်ဆေးခြင်းမှလွဲ၍ မည်သည့်အရာမျှ လုပ်ဆောင်ခွင့်မရှိတော့ပါ။", reply_markup=get_main_keyboard(uid))

    # သက်ဆိုင်ရာ Menu ရဲ့ လုပ်ဆောင်ချက်များဆီ Direct သွားစေခြင်း
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
# 6. CORE COMMANDS & FUNCTIONALITIES
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    pull_data_from_github()
    uid = message.from_user.id
    bot.reply_to(message, "👋 AHLFLK Decryptor Bot မှ ကြိုဆိုပါသည်၊", reply_markup=get_main_keyboard(uid))

def show_decrypt_list(message):
    uid = message.from_user.id
    is_vip, exp = check_vip_status(uid)
    if not is_vip: 
        return bot.reply_to(message, "🚫 သင်သည် VIP အသုံးပြုသူ မဟုတ်သဖြင့် ဤလုပ်ဆောင်ချက်ကို သုံးခွင့်မရှိပါ။", reply_markup=get_admin_contact_markup())
    
    configs = get_vpn_configs()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for vpn in configs:
        markup.add(types.InlineKeyboardButton(vpn['name'], callback_data=f"dec_{vpn['id']}"))
    bot.reply_to(message, f"⚙️ **Available VPN Configs (Exp: {exp}):**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def run_dec_callback(call):
    uid = call.from_user.id
    is_vip, _ = check_vip_status(uid)
    if not is_vip: return bot.answer_callback_query(call.id, "🚫 အသုံးပြုခွင့် သက်တမ်းကုန်ဆုံးသွားပါပြီ။")
    
    vid = call.data.split('_')[1]
    selected = next((v for v in get_vpn_configs() if v["id"] == vid), None)
    if not selected: return
    
    s_msg = bot.send_message(call.message.chat.id, "⏳ Decrypting config data, please wait...")
    try:
        res = perform_decryption(selected["url"], selected["outer_key"], selected["outer_delta"], selected["method"])
        file_path = f"{vid}_dec.json"
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(res, f, indent=4, ensure_ascii=False)
        bot.delete_message(call.message.chat.id, s_msg.message_id)
        with open(file_path, 'rb') as doc: bot.send_document(call.message.chat.id, doc, caption=f"✅ {selected['name']} Decrypted Data File!")
        os.remove(file_path)
    except Exception as e: bot.send_message(call.message.chat.id, f"❌ Decryption Failed: {e}")

# --- ADD VIP USER (MONTH ONLY) ---
def start_add_vip(message):
    uid = message.from_user.id
    if not is_admin(uid) and not is_reseller(uid): return
    user_states[uid] = 'add_vip_id'
    bot.reply_to(message, "✍️ VIP ပေးမည့်သူ၏ **Telegram ID** ကို ရိုက်ပို့ပေးပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_vip_id')
def add_vip_name(message):
    uid = message.from_user.id
    reseller_temp_data[uid] = {"id": message.text.strip()}
    user_states[uid] = 'add_vip_title'
    bot.reply_to(message, "✍️ ၎င်း VIP ရဲ့ **အသုံးပြုသူအမည် (Name)** ကို ပို့ပေးပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_vip_title')
def add_vip_value(message):
    uid = message.from_user.id
    reseller_temp_data[uid]["name"] = message.text.strip()
    user_states[uid] = 'add_vip_final'
    bot.reply_to(message, "📅 သက်တမ်းပေးလိုသော **လအရေအတွက် (Months)** ကို ဂဏန်းသက်သက် ရိုက်ထည့်ပါ (ဥပမာ- 1 သို့မဟုတ် 3):", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_vip_final')
def save_vip_to_github(message):
    uid = message.from_user.id
    val = message.text.strip()
    data = reseller_temp_data.get(uid)
    if not data or not val.isdigit(): 
        user_states[uid] = None
        return bot.reply_to(message, "❌ မှားယွင်းမှုရှိပါသည်။ ပင်မမီနူးမှ ပြန်စပါ။", reply_markup=get_main_keyboard(uid))
    
    # Credit/Token Check and Deduct for Reseller
    if not is_admin(uid):
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT token_balance FROM users WHERE tg_id = ?", (uid,))
        rem = cursor.fetchone()
        if not rem or rem[0] < int(val):
            conn.close()
            user_states[uid] = None
            return bot.reply_to(message, "❌ သင့်မှာ VIP သက်တမ်းပေးရန် လုံလောက်သော Token လက်ကျန် မရှိပါ။", reply_markup=get_main_keyboard(uid))
        cursor.execute("UPDATE users SET token_balance = token_balance - ? WHERE tg_id = ?", (int(val), uid))
        conn.commit()
        conn.close()
        sync_resellers_to_github()

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    # Month သီးသန့်စနစ်ဖြင့် Column C (Key) နေရာတွင် VIP ၏ Telegram ID ကို အလိုအလျောက် ထည့်သွင်းပေးခြင်း
    cursor.execute("INSERT OR REPLACE INTO auth_keys VALUES (?, ?, ?, ?, 'Months', ?, ?)",
                   (data["id"], data["name"], data["id"], val, str(uid), datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    
    sync_keys_to_github()
    bot.reply_to(message, f"✅ VIP User <b>{data['name']}</b> အား လအလိုက်အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ။", parse_mode="HTML", reply_markup=get_main_keyboard(uid))
    user_states[uid] = None

# --- EDIT VIP USER ---
def start_edit_vip(message):
    uid = message.from_user.id
    if not is_admin(uid) and not is_reseller(uid): return
    user_states[uid] = 'edit_vip_id'
    bot.reply_to(message, "✏️ ပြင်ဆင်လိုသော VIP ၏ **Telegram ID** ကို ရိုက်ပို့ပါ-", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'edit_vip_id')
def process_edit_vip(message):
    uid = message.from_user.id
    tid = message.text.strip()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT added_by FROM auth_keys WHERE target_id = ?", (tid,))
    row = cursor.fetchone()
    conn.close()
    
    if not is_admin(uid) and (not row or row[0] != str(uid)):
        user_states[uid] = None
        return bot.reply_to(message, "❌ ဤ VIP အကောင့်ကို ပြင်ဆင်ခွင့် သင့်မှာ မရှိပါ။", reply_markup=get_main_keyboard(uid))
        
    user_states[uid] = 'edit_vip_final'
    reseller_temp_data[uid] = {"id": tid}
    bot.reply_to(message, "✍️ ပုံစံသစ်အတိုင်း ပြင်ဆင်ပို့ပေးပါ-\n`အမည်သစ် | သက်တမ်း(လ အရေအတွက်)`\n\nဥပမာ-\n`Aung Aung | 3`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'edit_vip_final')
def save_edit_vip(message):
    uid = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 2 or not parts[1].isdigit():
        user_states[uid] = None
        return bot.reply_to(message, "❌ ပုံစံမှားယွင်းနေပါသည်။ ပင်မမီနူးမှ ပြန်စလုပ်ပါ။", reply_markup=get_main_keyboard(uid))
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO auth_keys VALUES (?, ?, ?, ?, 'Months', ?, ?)",
                   (reseller_temp_data[uid]["id"], parts[0], reseller_temp_data[uid]["id"], parts[1], str(uid), datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    
    sync_keys_to_github()
    bot.reply_to(message, "✅ VIP အချက်အလက်များကို အောင်မြင်စွာ ပြင်ဆင်ပြီးပါပြီ။", reply_markup=get_main_keyboard(uid))
    user_states[uid] = None

# --- DELETE VIP USER ---
def start_del_vip(message):
    uid = message.from_user.id
    if not is_admin(uid) and not is_reseller(uid): return
    user_states[uid] = 'del_vip_id'
    bot.reply_to(message, "🗑 ဖျက်ထုတ်လိုသော VIP ၏ **Telegram ID** ကို ရိုက်ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'del_vip_id')
def process_del_vip(message):
    uid = message.from_user.id
    tid = message.text.strip()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT added_by FROM auth_keys WHERE target_id = ?", (tid,))
    row = cursor.fetchone()
    
    if not is_admin(uid) and (not row or row[0] != str(uid)):
        conn.close()
        user_states[uid] = None
        return bot.reply_to(message, "❌ ဤ VIP အကောင့်ကို ဖျက်ပိုင်ခွင့် သင့်မှာ မရှိပါ။", reply_markup=get_main_keyboard(uid))
        
    cursor.execute("DELETE FROM auth_keys WHERE target_id = ?", (tid,))
    conn.commit()
    conn.close()
    
    sync_keys_to_github()
    bot.reply_to(message, "✅ VIP အသုံးပြုသူအား စာရင်းမှ ဖျက်ထုတ်ပြီးပါပြီ။", reply_markup=get_main_keyboard(uid))
    user_states[uid] = None

# --- CREATE RESELLER ---
def start_create_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'add_res_id'
    bot.reply_to(message, "👤 ဖန်တီးမည့် Reseller ၏ **Telegram ID** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_res_id')
def add_res_name(message):
    uid = message.from_user.id
    reseller_temp_data[uid] = {"id": message.text.strip()}
    user_states[uid] = 'add_res_name'
    bot.reply_to(message, "👤 Reseller ရဲ့ **အမည်** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_res_name')
def add_res_val(message):
    uid = message.from_user.id
    reseller_temp_data[uid]["name"] = message.text.strip()
    user_states[uid] = 'add_res_days'
    bot.reply_to(message, "📅 Reseller သက်တမ်း သတ်မှတ်ရန် **လအရေအတွက် (Months)** ကို ရိုက်ထည့်ပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_res_days')
def add_res_tokens(message):
    uid = message.from_user.id
    val = message.text.strip()
    if not val.isdigit():
        user_states[uid] = None
        return bot.reply_to(message, "❌ မှားယွင်းပါသည်။ ဂဏန်းပဲ ရိုက်ပါ။", reply_markup=get_main_keyboard(uid))
    
    days_to_add = int(val) * 30
    reseller_temp_data[uid]["exp"] = (datetime.now() + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
    user_states[uid] = 'add_res_final'
    bot.reply_to(message, f"🪙 ရရှိမည့် **Tokens (Credits)** ပမာဏကို ရိုက်ထည့်ပါ (ဥပမာ- {DEFAULT_CREDITS}):")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'add_res_final')
def save_reseller(message):
    uid = message.from_user.id
    tok = message.text.strip()
    data = reseller_temp_data.get(uid)
    if not data or not tok.isdigit():
        user_states[uid] = None
        return bot.reply_to(message, "❌ မှားယွင်းမှုရှိပါသည်။", reply_markup=get_main_keyboard(uid))
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 'reseller', ?, ?)", 
                   (int(data["id"]), data["name"], int(tok), data["exp"]))
    conn.commit()
    conn.close()
    
    sync_resellers_to_github()
    bot.reply_to(message, f"✅ Reseller: <b>{data['name']}</b> အား အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ။", parse_mode="HTML", reply_markup=get_main_keyboard(uid))
    user_states[uid] = None

# --- EDIT RESELLER ---
def start_edit_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'edit_res_id'
    bot.reply_to(message, "✏️ ပြင်ဆင်လိုသော Reseller ၏ **Telegram ID** ကို ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'edit_res_id')
def process_edit_reseller(message):
    uid = message.from_user.id
    user_states[uid] = 'edit_res_final'
    reseller_temp_data[uid] = {"id": message.text.strip()}
    bot.reply_to(message, "✍️ ပုံစံသစ်အတိုင်း ပြန်ပို့ပေးပါ-\n`အမည်သစ် | Tokenတိုးမည့်ပမာဏ | သက်တမ်းတိုးမည့်(လအရေအတွက်)`\n\nဥပမာ-\n`MgMg_Reseller | 50 | 2`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'edit_res_final')
def save_edit_reseller(message):
    uid = message.from_user.id
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        user_states[uid] = None
        return bot.reply_to(message, "❌ ပုံစံမှားယွင်းနေပါသည်။ ပြန်စလုပ်ပါ။", reply_markup=get_main_keyboard(uid))
    
    days_to_add = int(parts[2]) * 30
    new_exp = (datetime.now() + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 'reseller', ?, ?)", 
                   (int(reseller_temp_data[uid]["id"]), parts[0], int(parts[1]), new_exp))
    conn.commit()
    conn.close()
    
    sync_resellers_to_github()
    bot.reply_to(message, "✅ Reseller အား အောင်မြင်စွာ ပြင်ဆင်ပြီးပါပြီ။", reply_markup=get_main_keyboard(uid))
    user_states[uid] = None

# --- DELETE RESELLER ---
def start_del_reseller(message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = 'del_res_id'
    bot.reply_to(message, "🗑 ဖျက်ထုတ်လိုသော Reseller ၏ **Telegram ID** ကို ရိုက်ပို့ပေးပါ-")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == 'del_res_id')
def process_del_reseller(message):
    uid = message.from_user.id
    id_to_del = message.text.strip()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE tg_id = ? AND role = 'reseller'", (id_to_del,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        user_states[uid] = None
        return bot.reply_to(message, "❌ ၎င်း ID ဖြင့် Reseller ရှာမတွေ့ပါ။", reply_markup=get_main_keyboard(uid))
        
    cursor.execute("DELETE FROM users WHERE tg_id = ?", (int(id_to_del),))
    conn.commit()
    conn.close()
    
    sync_resellers_to_github()
    bot.reply_to(message, f"✅ Reseller: <b>{row[0]}</b> ကို ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML", reply_markup=get_main_keyboard(uid))
    user_states[uid] = None

# --- LIST VIEWING FUNCTIONS ---
def view_my_vips(message):
    pull_data_from_github()
    uid = message.from_user.id
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    if is_admin(uid):
        cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys")
    else:
        cursor.execute("SELECT target_id, key_string, unit_val, created_at FROM auth_keys WHERE added_by = ?", (str(uid),))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: return bot.reply_to(message, "📭 VIP အကောင့် မရှိသေးပါ။")
    res = f"🌐 <b>VIP အသုံးပြုသူ စာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        try:
            start_date = datetime.strptime(r[3], "%Y-%m-%d").date()
            exp = (start_date + timedelta(days=int(r[2])*30)).strftime("%Y-%m-%d")
        except: exp = "Unknown"
        res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | 📅 Exp: <code>{exp}</code> ({r[2]} Mos)\n"
    bot.reply_to(message, res, parse_mode="HTML")

def view_resellers(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_github()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username, token_balance, expire_date FROM users WHERE role='reseller'")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return bot.reply_to(message, "📭 Reseller မရှိသေးပါ။")
    res = "📊 **Resellers List:**\n\n"
    for r in rows: res += f"🆔 `{r[0]}` | 👤 `{r[1]}` | 🪙 Token: `{r[2]}` | 📅 Exp: `{r[3]}`\n"
    bot.reply_to(message, res, parse_mode="Markdown")

def view_all_vips_admin(message):
    if not is_admin(message.from_user.id): return
    view_my_vips(message)

def view_balance(message):
    pull_data_from_github()
    uid = message.from_user.id
    
    if is_admin(uid):
        res = f"💰 **Admin Account:**\n\n🆔 Telegram ID: `{uid}`\n📊 Status: `Main Admin (Unlimited)`"
    elif is_reseller(uid):
        is_active, tokens, exp = check_reseller_status(uid)
        res = f"💰 **Reseller Account Info:**\n\n🆔 Telegram ID: `{uid}`\n🪙 Token Balance: `{tokens}`\n📅 Expiration: `{exp}`\n📊 Status: `{'Active' if is_active else 'Expired/Blocked'}`"
    else:
        is_vip, exp = check_vip_status(uid)
        res = f"💰 **User Account Info:**\n\n🆔 Telegram ID: `{uid}`\n📊 Status: `{'Active VIP' if is_vip else 'Inactive'}`\n📅 Expiration: `{exp}`"
        
    bot.reply_to(message, res, reply_markup=get_main_keyboard(uid), parse_mode="Markdown")

# ==========================================
# 7. RUN EXECUTION
# ==========================================
if __name__ == "__main__":
    init_db()
    pull_data_from_github()
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
