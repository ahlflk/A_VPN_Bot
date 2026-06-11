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

# =========================================
# 1. CONFIGURATION & CORE BOT SETUP
# =========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TGC_ID")) if os.environ.get("TGC_ID") else None

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

ADMIN_BUTTONS = [
    "🌐 VPN Decrypt List",
    "➕ Add VIP User", "✏️ Edit VIP", "🗑 Delete VIP", "🌐 View All VIPs",
    "👤 Create Reseller", "📊 Reseller List", "🗑 Delete Reseller", "💰 My Balance"
]

RESELLER_BUTTONS = [
    "🌐 VPN Decrypt List",
    "➕ Add VIP User", "✏️ Edit VIP", "🗑 Delete VIP", "🔑 My VIP Users", "💰 My Balance"
]

def get_vpn_configs():
    try: 
        return json.loads(VPN_CONFIGS) if VPN_CONFIGS else []
    except Exception as e: 
        print(f"[-] VPN Configs Parse Error: {str(e)}")
        return []

def get_admin_contact_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💬 Contact Admin", url="https://t.me/ahlflk2025"))
    return markup

# =========================================
# 2. CRYPTOGRAPHY & DECRYPTION ENGINE (XXTEA)
# =========================================
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

# =========================================
# 3. LOCAL CACHE DATABASE & GOOGLE SHEET SYNC
# =========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_keys (
            target_id TEXT,
            key_string TEXT,
            vpn_key TEXT,
            unit_val INTEGER,
            created_at TEXT,
            added_by TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            username TEXT,
            credits INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user'
        )
    """)
    conn.commit()
    conn.close()

def pull_data_from_google_sheet():
    if not SCRIPT_URL: return
    try:
        response = requests.get(SCRIPT_URL, timeout=15)
        data = response.json()
        if isinstance(data, list):
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_keys")
            cursor.execute("DELETE FROM users WHERE role = 'reseller'")
            
            for row in data:
                target_id = str(row.get("TargetID", "")).strip()
                key_string = str(row.get("KeyString", "")).strip()
                vpn_key = str(row.get("VPNKey", "")).strip()
                unit_val = int(row.get("UnitVal", 0)) if row.get("UnitVal") else 1
                created_at = str(row.get("CreatedAt", "")).strip()
                
                if "_Reseller" in key_string:
                    reseller_name = key_string.replace("_Reseller", "")
                    cursor.execute(
                        "INSERT OR REPLACE INTO users (tg_id, username, credits, role) VALUES (?, ?, ?, 'reseller')",
                        (int(target_id), reseller_name, unit_val)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO auth_keys (target_id, key_string, vpn_key, unit_val, created_at, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                        (target_id, key_string, vpn_key, unit_val, created_at, "ADMIN")
                    )
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Error pulling from Sheet: {e}")

def post_to_google_sheet(payload):
    if not SCRIPT_URL: return False
    try:
        res = requests.post(SCRIPT_URL, json=payload, timeout=15)
        return res.json().get("status") == "success"
    except Exception as e:
        print(f"Post to Sheet Error: {e}")
        return False

# =========================================
# 4. HELPER UTILITIES & SECURITY
# =========================================
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_reseller(user_id):
    if is_admin(user_id): return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE tg_id = ? AND role = 'reseller'", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return True if row else False

def get_reseller_credits(user_id):
    if is_admin(user_id): return 999999
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE tg_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def deduct_reseller_credits(user_id, amount):
    if is_admin(user_id): return True
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits - ? WHERE tg_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return True

def get_expired_date_string(created_str, months):
    try:
        created_dt = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
    except:
        created_dt = datetime.now()
    expiry_dt = created_dt + timedelta(days=int(months) * 30)
    return expiry_dt.strftime("%Y-%m-%d %H:%M:%S")

def is_user_expired(target_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT unit_val, created_at FROM auth_keys WHERE target_id = ?", (str(target_id),))
    row = cursor.fetchone()
    conn.close()
    if not row: return True
    
    exp_str = get_expired_date_string(row[1], row[0])
    exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
    return datetime.now() > exp_dt

def make_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ADMIN_BUTTONS if is_admin(user_id) else RESELLER_BUTTONS
    
    markup.add(types.KeyboardButton("🌐 VPN Decrypt List"))
    other_buttons = [types.KeyboardButton(b) for b in buttons if b != "🌐 VPN Decrypt List"]
    markup.add(*other_buttons)
    return markup

# =========================================
# 5. STATE CLEANER INTERCEPTOR (လုပ်လက်စ ဖျက်ခြင်း)
# =========================================
@bot.message_handler(func=lambda msg: msg.text in ADMIN_BUTTONS or msg.text in RESELLER_BUTTONS)
def menu_button_interceptor(message):
    user_id = str(message.from_user.id)
    # လုပ်လက်စ အခြေအနေ ရှိနေလျှင် ဖျက်ပစ်မည်
    if user_id in user_states and user_states[user_id] is not None:
        user_states[user_id] = None
        bot.send_message(message.chat.id, "🔄 <code>ယခင်လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းပြီး အသစ်ကို စတင်လိုက်ပါပြီ။</code>", parse_mode="HTML")
    
    # ခလုတ်အလိုက် သက်ဆိုင်ရာ Function များသို့ လွှဲပေးခြင်း
    if message.text == "🌐 VPN Decrypt List": show_decrypt_configs(message)
    elif message.text == "➕ Add VIP User": add_vip_start(message)
    elif message.text == "🗑 Delete VIP": delete_vip_start(message)
    elif message.text in ["🌐 View All VIPs", "🔑 My VIP Users"]: view_vips(message)
    elif message.text == "👤 Create Reseller": create_reseller_start(message)
    elif message.text == "🗑 Delete Reseller": delete_reseller_start(message)
    elif message.text == "📊 Reseller List": view_resellers(message)
    elif message.text == "💰 My Balance": view_my_balance(message)

# =========================================
# 6. TELEGRAM BOT HANDLERS & WELCOME CARD INFO
# =========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states[str(user_id)] = None # start နှိပ်လျှင်လည်း state reset လုပ်သည်
    pull_data_from_google_sheet()
    
    # 1. Admin Info Card
    if is_admin(user_id):
        welcome_text = (
            "👑 <b>[ ACCOUNT INFO - ADMIN PANEL ]</b>\n"
            "───────────────────\n"
            f"👤 Admin Name: <code>{message.from_user.first_name}</code>\n"
            f"🆔 Telegram ID: <code>{user_id}</code>\n"
            "🌟 Role Status: <code>Super Admin</code>\n"
            "💰 Credit Balance: <code>Unlimited ♾️</code>\n"
            "───────────────────\n"
            "⚙️ စနစ်တစ်ခုလုံးကို စီမံခန့်ခွဲရန် အောက်ပါ Menu များကို အသုံးပြုနိုင်ပါသည်။"
        )
        bot.reply_to(message, welcome_text, parse_mode="HTML", reply_markup=make_main_keyboard(user_id))
    
    # 2. Reseller Info Card
    elif is_reseller(user_id):
        credits = get_reseller_credits(user_id)
        welcome_text = (
            "👤 <b>[ ACCOUNT INFO - RESELLER PANEL ]</b>\n"
            "───────────────────\n"
            f"👤 Reseller Name: <code>{message.from_user.first_name}</code>\n"
            f"🆔 Telegram ID: <code>{user_id}</code>\n"
            "🌟 Role Status: <code>Authorized Reseller</code>\n"
            f"💰 Credit Balance: <code>{credits}</code> Credits\n"
            "───────────────────\n"
            "➕ VIP အကောင့်သစ်များ ဖန်တီးရန်နှင့် စီမံရန် အသုံးပြုနိုင်ပါသည်။"
        )
        # Token ကုန်လျှင် သို့မဟုတ် ခေါ်ယူခွင့်မရှိပါက Contact Admin တွဲပြမည်
        markup = make_main_keyboard(user_id) if credits > 0 else get_admin_contact_markup()
        bot.reply_to(message, welcome_text, parse_mode="HTML", reply_markup=markup)
        
    # 3. Normal VIP User Card & Expired Protection
    else:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT unit_val, created_at, key_string FROM auth_keys WHERE target_id = ?", (str(user_id),))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            exp_date = get_expired_date_string(row[1], row[0])
            # သက်တမ်းကုန်/မကုန် စစ်ဆေးခြင်း
            if is_user_expired(user_id):
                expired_text = (
                    "⚠️ <b>[ ACCESS EXPIRED ]</b>\n"
                    "───────────────────\n"
                    f"🆔 User ID: <code>{user_id}</code>\n"
                    f"📅 Expired Date: <code>{exp_date}</code>\n"
                    "───────────────────\n"
                    "❌ လူကြီးမင်း၏ VIP သက်တမ်း ကုန်ဆုံးသွားပြီ ဖြစ်သဖြင့် အသုံးပြု၍မရတော့ပါ။ သက်တမ်းတိုးရန် Admin ကို ဆက်သွယ်ပါ။"
                )
                bot.reply_to(message, expired_text, parse_mode="HTML", reply_markup=get_admin_contact_markup())
            else:
                user_text = (
                    "🌐 <b>[ ACCOUNT INFO - VIP MEMBER ]</b>\n"
                    "───────────────────\n"
                    f"👤 Name: <code>{row[2]}</code>\n"
                    f"🆔 User ID: <code>{user_id}</code>\n"
                    "🌟 Role Status: <code>VIP Premium Member</code>\n"
                    f"📅 Expired Date: <code>{exp_date}</code>\n"
                    "───────────────────\n"
                    "🎉 လူကြီးမင်းသည် VPN Decrypt List ကို အသုံးပြုနိုင်ပါပြီ။"
                )
                # Normal User ကီးဘုတ်တွင် Decrypt List ခလုတ်တစ်ခုတည်းသာ ပေါ်စေမည်
                normal_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                normal_markup.add(types.KeyboardButton("🌐 VPN Decrypt List"))
                bot.reply_to(message, user_text, parse_mode="HTML", reply_markup=normal_markup)
        else:
            unauth_text = (
                "❌ <b>[ ACCESS DENIED ]</b>\n"
                "───────────────────\n"
                f"🆔 Your ID: <code>{user_id}</code>\n"
                "───────────────────\n"
                "သင်သည် စနစ်ထဲတွင် မှတ်ပုံတင်ထားခြင်းမရှိပါ။ အသုံးပြုလိုပါက ကတ်ဝယ်ယူရန် Admin ကို ဆက်သွယ်ပါ။"
            )
            bot.reply_to(message, unauth_text, parse_mode="HTML", reply_markup=get_admin_contact_markup())

# --- 🌐 VPN DECRYPT LIST WORKFLOW ---
def show_decrypt_configs(message):
    user_id = message.from_user.id
    if not is_admin(user_id) and not is_reseller(user_id) and is_user_expired(user_id):
        return bot.reply_to(message, "❌ သင့်သက်တမ်း ကုန်ဆုံးသွားပါသဖြင့် အသုံးပြုခွင့်မရှိတော့ပါ။", reply_markup=get_admin_contact_markup())
        
    configs = get_vpn_configs()
    if not configs:
        return bot.reply_to(message, "❌ မည်သည့် VPN Config မှ သတ်မှတ်ထားခြင်းမရှိသေးပါ။")

    markup = types.InlineKeyboardMarkup(row_width=2) 
    buttons = []
    for idx, cfg in enumerate(configs, 1):
        buttons.append(types.InlineKeyboardButton(f"[{idx}] {cfg.get('name', 'Unknown')}", callback_data=f"dec_{idx-1}"))
    
    markup.add(*buttons)
    bot.reply_to(message, "🌐 **ကျေးဇူးပြု၍ Decrypt ပြုလိုသော VPN ကို ရွေးချယ်ပေးပါ:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dec_"))
def handle_decrypt_callback(call):
    idx = int(call.data.split("_")[1])
    configs = get_vpn_configs()
    
    if idx >= len(configs):
        return bot.answer_callback_query(call.id, "❌ Config မတွေ့ရှိပါ။")
        
    selected_cfg = configs[idx]
    
    # ⚠️ ခလုတ်ကို မဖျောက်ဘဲ "⚡ Decrypt လုပ်နေသည်..." ဟု စာသားကို Edit လုပ်ပြီး ပြောင်းလဲပြသခြင်း
    original_markup = call.message.reply_markup
    bot.edit_message_text(
        text=f"⚡ <b>{selected_cfg.get('name')} ကို Decrypt လုပ်နေပါသည်... ခေတ္တစောင့်ဆိုင်းပေးပါ...⏳</b>",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="HTML",
        reply_markup=original_markup
    )
    
    try:
        decrypted_obj = perform_decryption(
            config_url=selected_cfg.get("url"),
            outer_key=selected_cfg.get("outer_key"),
            outer_delta_raw=selected_cfg.get("outer_delta", "0x2e0ba747"),
            method=selected_cfg.get("method", "base64_recursive")
        )
        
        decrypted_text = json.dumps(decrypted_obj, indent=2, ensure_ascii=False)
        output_file = f"{selected_cfg.get('id', 'vpn')}_decrypted.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(decrypted_text)
            
        with open(output_file, "rb") as f:
            bot.send_document(
                call.message.chat.id, f, 
                caption=f"✅ <b>{selected_cfg.get('name')} Decrypted Successfully!</b>\n🌐 Method: <code>{selected_cfg.get('method')}</code>", 
                parse_mode="HTML"
            )
        os.remove(output_file)
        
        # ⚠️ အောင်မြင်သွားလျှင် Message Text အား "Decrypted Successfully" သို့ ပြောင်းလဲပေးခြင်း
        bot.edit_message_text(
            text=f"✅ <b>{selected_cfg.get('name')} Decrypted Successfully!</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=original_markup
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Decryption Engine အမှားအယွင်းရှိနေပါသည်-\n<code>{str(e)}</code>", parse_mode="HTML")

# --- ADD VIP USER ---
def add_vip_start(message):
    user_id = message.from_user.id
    if get_reseller_credits(user_id) <= 0:
        return bot.reply_to(message, "❌ သင့်မှာ VIP အကောင့်ထုတ်ရန် Credit မလုံလောက်တော့ပါ။", reply_markup=get_admin_contact_markup())
    
    user_states[str(user_id)] = "WAIT_VIP_TGID"
    bot.reply_to(message, "👤 **VIP အသုံးပြုသူရဲ့ Telegram ID ကို ရိုက်ထည့်ပေးပါ:**", parse_mode="Markdown", reply_markup=types.ForceReply(selective=True))

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_VIP_TGID")
def add_vip_tgid(message):
    user_id = str(message.from_user.id)
    tg_id = message.text.strip()
    if not tg_id.isdigit():
        return bot.reply_to(message, "❌ Telegram ID သည် ဂဏန်းသီးသန့် ဖြစ်ရပါမည်။ ထပ်မံရိုက်ထည့်ပါ။")
    
    vip_temp_data[user_id] = {"target_id": tg_id}
    user_states[user_id] = "WAIT_VIP_NAME"
    bot.reply_to(message, "👤 **VIP အသုံးပြုသူရဲ့ အမည် (Name) ကို ရိုက်ထည့်ပေးပါ:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_VIP_NAME")
def add_vip_name(message):
    user_id = str(message.from_user.id)
    name = message.text.strip()
    vip_temp_data[user_id]["name"] = name
    
    user_states[user_id] = "WAIT_VIP_MONTH"
    bot.reply_to(message, "📅 **အသုံးပြုမည့် သက်တမ်းလ (Months) ကို ရိုက်ထည့်ပါ (ဥပမာ- 1 သို့မဟုတ် 3):**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_VIP_MONTH")
def add_vip_month(message):
    user_id = str(message.from_user.id)
    months = message.text.strip()
    if not months.isdigit():
        return bot.reply_to(message, "❌ သက်တမ်းလသည် ဂဏန်းသီးသန့် ဖြစ်ရပါမည်။")
    
    req_credits = int(months)
    if get_reseller_credits(int(user_id)) < req_credits:
        user_states[user_id] = None
        return bot.reply_to(message, f"❌ သင့်မှာ Credit {req_credits} ခု မရှိပါသဖြင့် VIP မဖန်တီးနိုင်ပါ။", reply_markup=get_admin_contact_markup())
    
    data = vip_temp_data[user_id]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    payload = {
        "method": "ADD_VIP",
        "targetUsers": data["target_id"],
        "targetKey": data["target_id"], 
        "nameVal": data["name"],
        "unitVal": req_credits,
        "dateVal": created_at
    }
    
    bot.send_message(message.chat.id, "⏳ Google Sheet Database သို့ လှမ်းသိမ်းနေပါသည်။...")
    if post_to_google_sheet(payload):
        deduct_reseller_credits(int(user_id), req_credits)
        pull_data_from_google_sheet()
        exp_date = get_expired_date_string(created_at, req_credits)
        
        msg_text = (
            f"✅ <b>VIP အကောင့်ကို အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။</b>\n\n"
            f"🆔 TG ID: <code>{data['target_id']}</code>\n"
            f"👤 အမည်: <code>{data['name']}</code>\n"
            f"🔑 User ID Token: <code>{data['target_id']}</code>\n"
            f"📅 Expired: <code>{exp_date}</code>\n"
            f"💰 နှုတ်ယူခဲ့သည့် Credit: <code>{req_credits}</code>"
        )
        bot.send_message(message.chat.id, msg_text, parse_mode="HTML", reply_markup=make_main_keyboard(int(user_id)))
    else:
        bot.send_message(message.chat.id, "❌ Google Sheet သို့ ဒေတာပို့ရန် တောင်းဆိုမှု မအောင်မြင်ပါ။")
    
    user_states[user_id] = None

# --- DELETE VIP ---
def delete_vip_start(message):
    user_states[str(message.from_user.id)] = "WAIT_DEL_VIP"
    bot.reply_to(message, "🗑 **ဖျက်ထုတ်လိုသော VIP အသုံးပြုသူ၏ Telegram ID ကို ရိုက်ထည့်ပေးပါ:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_DEL_VIP")
def delete_vip_execute(message):
    user_id = str(message.from_user.id)
    tg_id = message.text.strip()
    
    payload = {
        "method": "DELETE_DATA",
        "key": "VIP_ACCOUNT",
        "targetUsers": tg_id,
        "targetKey": tg_id 
    }
    
    bot.send_message(message.chat.id, "⏳ Google Sheet မှ ဒေတာ ဖျက်ထုတ်နေပါသည်...")
    if post_to_google_sheet(payload):
        pull_data_from_google_sheet()
        bot.send_message(message.chat.id, f"✅ VIP TG ID: <code>{tg_id}</code> အား အောင်မြင်စွာ ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML", reply_markup=make_main_keyboard(int(user_id)))
    else:
        bot.send_message(message.chat.id, "❌ Sheet ထဲမှ ဒေတာဖျက်ရန် တောင်းဆိုမှု မအောင်မြင်ပါ။")
    user_states[user_id] = None

# --- VIEW VIP USERS ---
def view_vips(message):
    pull_data_from_google_sheet()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, key_string, vpn_key, unit_val, created_at FROM auth_keys")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return bot.reply_to(message, "📭 လက်ရှိ VIP အသုံးပြုသူ မရှိသေးပါ။")
        
    res = f"🌐 <b>VIP အသုံးပြုသူ စာရင်း ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        exp_str = get_expired_date_string(r[4], r[3])
        res += f"🆔 TG ID: <code>{r[0]}</code>\n👤 အမည်: <code>{r[1]}</code>\n🔑 User/TG ID: <code>{r[2]}</code>\n📅 Expired: <code>{exp_str}</code>\n\n"
        
    bot.reply_to(message, res, parse_mode="HTML")

# --- CREATE RESELLER (ADMIN ONLY) ---
def create_reseller_start(message):
    if not is_admin(message.from_user.id): return
    user_states[str(message.from_user.id)] = "WAIT_RES_ID"
    bot.reply_to(message, "👤 **ဖန်တီးမည့် Reseller ရဲ့ Telegram ID ကို ထည့်ပေးပါ:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_RES_ID")
def create_reseller_id(message):
    user_id = str(message.from_user.id)
    res_id = message.text.strip()
    if not res_id.isdigit():
        return bot.reply_to(message, "❌ TG ID သည် ဂဏန်းသီးသန့် ဖြစ်ရပါမည်။")
    
    reseller_temp_data[user_id] = {"tg_id": res_id}
    user_states[user_id] = "WAIT_RES_NAME"
    bot.reply_to(message, "👤 **Reseller ရဲ့ အမည် (Name) ကို ရိုက်ထည့်ပေးပါ:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_RES_NAME")
def create_reseller_name(message):
    user_id = str(message.from_user.id)
    name = message.text.strip()
    reseller_temp_data[user_id]["name"] = name
    
    user_states[user_id] = "WAIT_RES_CREDITS"
    bot.reply_to(message, "💰 **ထည့်သွင်းပေးမည့် Credit အရေအတွက်ကို ရိုက်ထည့်ပါ:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_RES_CREDITS")
def create_reseller_credits(message):
    user_id = str(message.from_user.id)
    credits = message.text.strip()
    if not credits.isdigit():
        return bot.reply_to(message, "❌ Credit သည် ဂဏန်းသီးသန့် ဖြစ်ရပါမည်။")
        
    data = reseller_temp_data[user_id]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    payload = {
        "method": "ADD_VIP",
        "targetUsers": data["tg_id"],
        "targetKey": f"TOKEN_{data['tg_id']}", 
        "nameVal": f"{data['name']}_Reseller",
        "unitVal": int(credits),
        "dateVal": created_at
    }
    
    bot.send_message(message.chat.id, "⏳ Reseller အား Sheet ထဲသို့ သွားရောက်သိမ်းဆည်းနေပါသည်...")
    if post_to_google_sheet(payload):
        pull_data_from_google_sheet()
        bot.send_message(
            message.chat.id, 
            f"✅ <b>Reseller အသစ်ကို အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။</b>\n\n🆔 TG ID: <code>{data['tg_id']}</code>\n👤 အမည်: <code>{data['name']}</code>\n🔑 Reseller Token: <code>TOKEN_{data['tg_id']}</code>\n💰 Credits: <code>{credits}</code>", 
            parse_mode="HTML", reply_markup=make_main_keyboard(int(user_id))
        )
    else:
        bot.send_message(message.chat.id, "❌ Google Sheet သို့ ပို့ဆောင်မှု မအောင်မြင်ပါ။")
    user_states[user_id] = None

# --- DELETE RESELLER (ADMIN ONLY) ---
def delete_reseller_start(message):
    if not is_admin(message.from_user.id): return
    user_states[str(message.from_user.id)] = "WAIT_DEL_RES"
    bot.reply_to(message, "🗑 **ဖျက်ထုတ်လိုသော Reseller ၏ Telegram ID ကို ရိုက်ထည့်ပေးပါ:**", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: user_states.get(str(msg.from_user.id)) == "WAIT_DEL_RES")
def delete_reseller_execute(message):
    user_id = str(message.from_user.id)
    tg_id = message.text.strip()
    
    payload = {
        "method": "DELETE_DATA",
        "key": "RESELLER_ACCOUNT",
        "targetUsers": tg_id,
        "targetKey": ""
    }
    
    bot.send_message(message.chat.id, "⏳ Google Sheet မှ Reseller အား ဖျက်ထုတ်နေပါသည်...")
    if post_to_google_sheet(payload):
        pull_data_from_google_sheet()
        bot.send_message(message.chat.id, f"✅ Reseller TG ID: <code>{tg_id}</code> အား ဖျက်ထုတ်ပြီးပါပြီ။", parse_mode="HTML", reply_markup=make_main_keyboard(int(user_id)))
    else:
        bot.send_message(message.chat.id, "❌ Sheet ထဲမှ ဒေတာဖျက်ရန် တောင်းဆိုမှု မအောင်မြင်ပါ။")
    user_states[user_id] = None

# --- VIEW RESELLERS (ADMIN ONLY) ---
def view_resellers(message):
    if not is_admin(message.from_user.id): return
    pull_data_from_google_sheet()
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, username, credits FROM users WHERE role = 'reseller'")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: return bot.reply_to(message, "📭 Reseller မရှိသေးပါ။")
    res = f"📊 <b>Reseller စာရင်း အားလုံး ({len(rows)} ဦး):</b>\n\n"
    for r in rows:
        res += f"🆔 <code>{r[0]}</code> | 👤 <code>{r[1]}</code> | 💰 Credits: <code>{r[2]}</code>\n"
    bot.reply_to(message, res, parse_mode="HTML")

# --- MY BALANCE ---
def view_my_balance(message):
    user_id = message.from_user.id
    pull_data_from_google_sheet()
    credits = get_reseller_credits(user_id)
    
    markup = make_main_keyboard(user_id) if credits > 0 else get_admin_contact_markup()
    bot.reply_to(message, f"💰 <b>လူကြီးမင်း၏ လက်ကျန် Credit:</b> <code>{credits}</code> ခု ဖြစ်ပါသည်။", parse_mode="HTML", reply_markup=markup)

# =========================================
# 7. FLASK WEBHOOK ENGINE & WEB STARTUP
# =========================================
@app.route('/', methods=['GET'])
def index():
    return "AHLFLK XXTEA Premium Multi-User Dynamic Panel is Online!", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    else:
        abort(403)

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    init_db()
    pull_data_from_google_sheet()
    
    if PUBLIC_URL:
        bot.remove_webhook()
        bot.set_webhook(url=PUBLIC_URL + '/' + BOT_TOKEN)
        print(f"Webhook configured to: {PUBLIC_URL}")
        run_flask()
    else:
        print("Webhook URL missing! Starting Polling...")
        bot.remove_webhook()
        Thread(target=bot.infinity_polling).start()
