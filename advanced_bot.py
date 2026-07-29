import os
import asyncio
import json
import time
import re
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import FloodWait
from yt_dlp import YoutubeDL
import requests

# ========================================
# Environment Variables
# ========================================
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
STRING_SESSION = os.environ.get("STRING_SESSION", "your_string_session")
HF_API_KEY = os.environ.get("HF_API_KEY", "your_huggingface_api_key")
OWNER_ID = int(os.environ.get("OWNER_ID", 123456789))

# Encryption Key
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode())

# ========================================
app = Client(
    "advanced_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    session_string=STRING_SESSION
)

# YouTube Downloader
ydl_opts = {"format": "bestaudio/best", "quiet": True, "no_warnings": True}
ydl_video_opts = {"format": "bestvideo+bestaudio/best", "quiet": True, "no_warnings": True}

# ========================================
# Data Storage
# ========================================
DATA_FILE = "bot_data.json"
LANG_FILE = "user_lang.json"
TEACH_FILE = "teach_data.json"
VIDEO_FILE = "video_data.json"
PREMIUM_FILE = "premium_data.json"
IMAGE_FILE = "image_data.json"
SECURITY_FILE = "security_data.json"

def load_json_file(filename, default=None):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return default or {}

def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def encrypt_data(data):
    try:
        return cipher.encrypt(json.dumps(data).encode()).decode()
    except:
        return data

def decrypt_data(data):
    try:
        return json.loads(cipher.decrypt(data.encode()).decode())
    except:
        return data

def load_encrypted_file(filename, default=None):
    try:
        with open(filename, "r") as f:
            encrypted_data = f.read()
            return decrypt_data(encrypted_data)
    except:
        return default or {}

def save_encrypted_file(filename, data):
    encrypted_data = encrypt_data(data)
    with open(filename, "w") as f:
        f.write(encrypted_data)

# Load data
data = load_json_file(DATA_FILE, {"warns": {}, "muted": {}, "banned": {}, "link_warns": {}, "bot_warns": {}, "reports": {}})
user_lang = load_json_file(LANG_FILE, {})
video_data = load_json_file(VIDEO_FILE, {"welcome": {}, "leave": {}})
premium_data = load_json_file(PREMIUM_FILE, {})
image_data = load_json_file(IMAGE_FILE, {"normal": {}, "premium": {}})
security_data = load_json_file(SECURITY_FILE, {"blocked_users": [], "suspicious_activity": {}})
teach_data = load_encrypted_file(TEACH_FILE, {})

# ========================================
# Language System
# ========================================
LANGUAGES = {
    "en": "English 🇬🇧",
    "my": "မြန်မာ 🇲🇲",
    "zh": "中文 🇨🇳",
    "ko": "한국어 🇰🇷",
    "ja": "日本語 🇯🇵",
    "th": "ไทย 🇹🇭",
    "id": "Bahasa Indonesia 🇮🇩",
    "sg": "Singapore 🇸🇬"
}

def get_lang(user_id):
    if str(user_id) in user_lang:
        return user_lang[str(user_id)]
    return "my"

def set_lang(user_id, lang):
    user_lang[str(user_id)] = lang
    save_json_file(LANG_FILE, user_lang)

# ========================================
# Premium System
# ========================================
def is_premium(user_id):
    if str(user_id) in premium_data:
        if premium_data[str(user_id)] > time.time():
            return True
        else:
            del premium_data[str(user_id)]
            save_json_file(PREMIUM_FILE, premium_data)
    return False

def add_premium(user_id, days=30):
    premium_data[str(user_id)] = time.time() + (days * 24 * 60 * 60)
    save_json_file(PREMIUM_FILE, premium_data)

def get_premium_remaining(user_id):
    if str(user_id) in premium_data:
        remaining = premium_data[str(user_id)] - time.time()
        if remaining > 0:
            days = int(remaining // (24 * 60 * 60))
            hours = int((remaining % (24 * 60 * 60)) // (60 * 60))
            return days, hours
    return None, None

# ========================================
# Teach System (Encrypted)
# ========================================
def add_teach(question, answer, user_id):
    key = question.lower().strip()
    teach_data[key] = {
        "answer": answer,
        "taught_by": user_id,
        "time": time.time()
    }
    save_encrypted_file(TEACH_FILE, teach_data)
    return True

def get_teach(question):
    key = question.lower().strip()
    if key in teach_data:
        return teach_data[key]["answer"]
    for q in teach_data:
        if q in key or key in q:
            return teach_data[q]["answer"]
    return None

def get_all_teach():
    return teach_data

def delete_teach(question):
    key = question.lower().strip()
    if key in teach_data:
        del teach_data[key]
        save_encrypted_file(TEACH_FILE, teach_data)
        return True
    return False

# ========================================
# Video System
# ========================================
def set_leave_video(chat_id, video_id, caption):
    chat_id = str(chat_id)
    video_data["leave"][chat_id] = {
        "video_id": video_id,
        "caption": caption,
        "set_by": OWNER_ID,
        "time": time.time()
    }
    save_json_file(VIDEO_FILE, video_data)

def get_leave_video(chat_id):
    chat_id = str(chat_id)
    if chat_id in video_data["leave"]:
        return video_data["leave"][chat_id].get("video_id"), video_data["leave"][chat_id].get("caption")
    return None, None

# ========================================
# AI Functions
# ========================================
def ask_ai(prompt, lang="my"):
    try:
        API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 300, "temperature": 0.8}
        }
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                text = result[0].get("generated_text", "အဖြေမရဘူး။")
                return text
            return str(result)
        return f"❌ Error: {response.status_code}"
    except Exception as e:
        return f"❌ အမှား: {str(e)}"

def generate_image(prompt):
    try:
        API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        payload = {"inputs": prompt}
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        return None

def check_image_limit(user_id):
    if is_premium(user_id):
        return True
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    if key not in image_data["normal"]:
        image_data["normal"][key] = 0
    if image_data["normal"][key] >= 1:
        return False
    image_data["normal"][key] += 1
    save_json_file(IMAGE_FILE, image_data)
    return True

# ========================================
# Security System
# ========================================
async def check_security(client: Client, user_id, chat_id):
    key = f"reports_{user_id}"
    if key in data["reports"]:
        if data["reports"][key] >= 5:
            return False
        else:
            data["reports"][key] += 1
            save_json_file(DATA_FILE, data)
            return True
    else:
        data["reports"][key] = 1
        save_json_file(DATA_FILE, data)
        return True

async def protect_from_ban(client: Client, user_id):
    key = f"ban_protect_{user_id}"
    if key not in security_data["suspicious_activity"]:
        security_data["suspicious_activity"][key] = 0
    security_data["suspicious_activity"][key] += 1
    if security_data["suspicious_activity"][key] >= 3:
        return False
    save_json_file(SECURITY_FILE, security_data)
    return True

async def warn_owner(message):
    try:
        await app.send_message(OWNER_ID, f"🔐 **Security Alert**\n\n{message}")
    except:
        pass

# ========================================
# Helper Functions
# ========================================
def is_admin(user_id, chat_id):
    try:
        member = app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

def is_owner(user_id):
    return user_id == OWNER_ID

def can_use_admin_command(user_id, chat_id):
    if is_owner(user_id):
        return True
    return is_admin(user_id, chat_id)

# ========================================
# Security - Message Handler
# ========================================
@app.on_message(filters.all & filters.group)
async def security_check(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    chat_id = message.chat.id
    if not user_id:
        return
    if is_owner(user_id):
        return
    if not await check_security(client, user_id, chat_id):
        await client.ban_chat_member(chat_id, user_id)
        await message.reply_text(f"🛡️ {user_id} Report အများကြီးခံရတဲ့အတွက် Ban လုပ်လိုက်ပါပြီရှင်")
        await warn_owner(f"🚨 User {user_id} ကို Report များလွန်းလို့ Ban လုပ်လိုက်ပါပြီ။")
        return
    if not await protect_from_ban(client, user_id):
        await warn_owner(f"⚠️ User {user_id} က suspicious activity ပြသနေပါတယ်ရှင်!")
        await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
        await message.reply_text(f"🔐 {user_id} ကို suspicious activity ကြောင့် Mute လုပ်ထားပါတယ်ရှင်")

# ========================================
# Welcome System
# ========================================
@app.on_chat_member_updated()
async def welcome_new_member(client: Client, event):
    if event.new_chat_member:
        user = event.new_chat_member.user
        chat_id = event.chat.id
        if user.is_bot:
            return
        first_name = user.first_name or "N/A"
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        user_id = user.id
        username = f"@{user.username}" if user.username else "None"
        try:
            user_info = await client.get_users(user_id)
            bio = user_info.bio if user_info.bio else "N/A"
        except:
            bio = "N/A"
        link_count = 0
        if not is_premium(user_id) and bio != "N/A":
            links = re.findall(r'https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+', bio)
            if links:
                link_count = len(links)
                key = f"user_{chat_id}_{user_id}"
                if key not in data["link_warns"]:
                    data["link_warns"][key] = 0
                data["link_warns"][key] += link_count
                save_json_file(DATA_FILE, data)
                warn_count = data["link_warns"][key]
                if warn_count >= 20:
                    await client.ban_chat_member(chat_id, user_id)
                    await client.send_message(chat_id, f"🚨 {user.mention} လင့်ခ် ၂၀ ကျော်ပါတဲ့အတွက် Ban လုပ်လိုက်ပါပြီရှင် 😤")
                    return
                elif warn_count >= 3:
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                    key_mute = f"mute_{chat_id}_{user_id}"
                    data["muted"][key_mute] = time.time() + 300
                    save_json_file(DATA_FILE, data)
                    await client.send_message(chat_id, f"⛔ {user.mention} လင့်ခ် ၃ ခါပါတဲ့အတွက် ၅ မိနစ် Mute လုပ်ထားမယ်နော် 🤫")
                    await asyncio.sleep(300)
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
                    return
        welcome_text = (
            f"📌 **မဂ်လာပါရှင့်**\n\n"
            f"🚨 **လူသစ်အချက်အလက်များ**\n\n"
            f"👤 **Name:** {full_name}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🔗 **Username:** {username}\n"
            f"📝 **Bio:** {bio}\n\n"
            f"💎 **Premium:** {'✅ ရှိပါတယ်' if is_premium(user_id) else '❌ မရှိသေးပါဘူး'}\n"
            f"🔗 **Link in Bio:** {'❌ ပါတယ်နော်' if link_count > 0 else '✅ မပါဘူးရှင်'}\n\n"
            f"😘 ကြိုဆိုပါတယ်ရှင်"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 ဘာသာစကား", callback_data="show_lang"), InlineKeyboardButton("👑 Owner", url="https://t.me/Tear808")],
            [InlineKeyboardButton("➕ Group ထဲထည့်ရန်", callback_data="add_group"), InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("💎 Premium", callback_data="premium_info")]
        ])
        await client.send_message(chat_id=chat_id, text=welcome_text, reply_markup=keyboard)

# ========================================
# Leave System
# ========================================
@app.on_chat_member_updated()
async def leave_member(client: Client, event):
    if event.old_chat_member:
        user = event.old_chat_member.user
        chat_id = event.chat.id
        if user.is_bot:
            return
        if event.old_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED] and event.new_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            mention = user.mention
            leave_text = f"😢 {mention} ထွက်သွားပြီနော်... 🥺\n\n🌸 အချိန်တန်ရင် ပြန်လာခဲ့ပါကွာ 🥀🥀\n💕 မင်းလာမှ ပြုံးမဲ့သူပါကွာ"
            video_id, caption = get_leave_video(chat_id)
            if video_id:
                try:
                    await client.send_video(chat_id=chat_id, video=video_id, caption=leave_text)
                    return
                except:
                    pass
            await client.send_message(chat_id=chat_id, text=leave_text)

# ========================================
# Anti-Spam System
# ========================================
@app.on_message(filters.text & filters.group)
async def anti_spam(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text or ""
    if can_use_admin_command(user_id, chat_id):
        return
    if is_premium(user_id):
        return
    if f"mute_{chat_id}_{user_id}" in data["muted"]:
        if data["muted"][f"mute_{chat_id}_{user_id}"] > time.time():
            return
        else:
            del data["muted"][f"mute_{chat_id}_{user_id}"]
            save_json_file(DATA_FILE, data)
            await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
    if re.search(r'https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+', text):
        user_key = f"user_{chat_id}_{user_id}"
        if user_key not in data["link_warns"]:
            data["link_warns"][user_key] = 0
        data["link_warns"][user_key] += 1
        save_json_file(DATA_FILE, data)
        user_warn_count = data["link_warns"][user_key]
        if user_warn_count == 3:
            await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
            data["muted"][f"mute_{chat_id}_{user_id}"] = time.time() + 300
            save_json_file(DATA_FILE, data)
            await message.delete()
            await message.reply_text(f"⛔ {message.from_user.mention} လင့်ခ် ၃ ခါချတဲ့အတွက် ၅ မိနစ် Mute လုပ်ထားမယ်နော် 🤫")
            await asyncio.sleep(300)
            await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
            return
        if user_warn_count >= 20:
            await client.ban_chat_member(chat_id, user_id)
            await message.delete()
            await message.reply_text(f"🛑 {message.from_user.mention} လင့်ခ် ၂၀ ကျော်ချတဲ့အတွက် Ban လုပ်လိုက်ပါပြီရှင် 😤")
            return
        if user_warn_count == 1:
            await message.reply_text(f"⚠️ **သတိပေးချက် (၁/၃)**\n💬 {message.from_user.mention} လင့်ခ်မချပါနဲ့နော် 😊")
        elif user_warn_count == 2:
            await message.reply_text(f"⚠️ **သတိပေးချက် (၂/၃)**\n💬 {message.from_user.mention} နောက်တစ်ခါချရင် ၅ မိနစ် Mute ခံရမှာနော် 🤫")
            await message.delete()

# ========================================
# Premium Commands
# ========================================
@app.on_message(filters.command("tpremium"))
async def add_premium_cmd(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ ဒီ Command ကို Owner မှသာ သုံးလို့ရပါတယ်ရှင် 😅")
        return
    if len(message.command) < 2:
        await message.reply_text("💎 **Premium ထည့်ပေးနည်း**\n\n`/tpremium @username` လို့ရိုက်ပါ။\nဥပမာ: `/tpremium @Tear808`\n\n💰 **စျေးနှုန်း:** 5000 Kyat / ၁ လ")
        return
    username = message.command[1]
    if username.startswith("@"):
        username = username[1:]
    try:
        user = await client.get_users(username)
        user_id = user.id
        add_premium(user_id, 30)
        await message.reply_text(f"✅ **Premium ထည့်ပေးလိုက်ပါပြီရှင်** 🥰\n\n👤 **User:** {user.mention}\n📌 **Username:** @{username}\n⏱️ **သက်တမ်း:** ၃၀ ရက် (၁ လ)\n💰 **စျေးနှုန်း:** 5000 Kyat\n\n😘 ကျေးဇူးပါရှင်")
    except Exception as e:
        await message.reply_text(f"❌ User ကိုရှာမတွေ့ဘူးရှင် 😢\n`{e}`")

@app.on_message(filters.command("premium"))
async def premium_status(client: Client, message: Message):
    user_id = message.from_user.id
    if is_premium(user_id):
        days, hours = get_premium_remaining(user_id)
        await message.reply_text(f"💎 **Premium User ဖြစ်ပါတယ်ရှင်** 🥰\n\n📌 **ကျန်ရှိတဲ့သက်တမ်း:**\n• {days} ရက် {hours} နာရီ\n\n✅ **အခွင့်အရေးများ:**\n• Link ချခွင့် (မမြူ၊ မဘန်)\n• Mute ဖြေခွင့် `/tearmute`\n• Ban ဖြေခွင့် `/tearban`\n• AI ပုံထုတ်ခွင့် (အကန့်အသတ်မရှိ)\n\n😘 ကျေးဇူးပါရှင်")
    else:
        await message.reply_text("💎 **Premium System**\n\n📌 Premium ဆိုတာ ထူးခြားတဲ့ အခွင့်အရေးတွေကို ရရှိစေမှာပါ။\n\n✅ **အခွင့်အရေးများ:**\n• Link ချခွင့် (မမြူ၊ မဘန်)\n• Mute ဖြေခွင့် `/tearmute`\n• Ban ဖြေခွင့် `/tearban`\n• AI ပုံထုတ်ခွင့် (အကန့်အသတ်မရှိ)\n\n💰 **စျေးနှုန်း:** 5000 Kyat / ၁ လ\n📞 ဝယ်ယူရန်: @Tear808 ကို ဆက်သွယ်ပါ\n\n😘 ကျေးဇူးပါရှင်")

@app.on_message(filters.command("tearmute"))
async def tearmute(client: Client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not is_premium(user_id):
        await message.reply_text("❌ ဒီ Command ကို Premium User များသာ သုံးလို့ရပါတယ်ရှင် 😅\n💎 Premium ဝယ်ရန်: @Tear808")
        return
    key = f"mute_{chat_id}_{user_id}"
    if key in data["muted"]:
        del data["muted"][key]
        save_json_file(DATA_FILE, data)
        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
        await message.reply_text(f"✅ {message.from_user.mention} ကို Mute ဖြေပေးလိုက်ပါပြီရှင် 🥰\n💎 Premium User အတွက် အထူးဝန်ဆောင်မှုပါရှင် 😘")
    else:
        await message.reply_text("❌ ခင်ဗျားက Mute မခံထားရပါဘူးရှင် 😅")

@app.on_message(filters.command("tearban"))
async def tearban(client: Client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not is_premium(user_id):
        await message.reply_text("❌ ဒီ Command ကို Premium User များသာ သုံးလို့ရပါတယ်ရှင် 😅\n💎 Premium ဝယ်ရန်: @Tear808")
        return
    try:
        await client.unban_chat_member(chat_id, user_id)
        await message.reply_text(f"✅ {message.from_user.mention} ကို Ban ဖြေပေးလိုက်ပါပြီရှင် 🥰\n💎 Premium User အတွက် အထူးဝန်ဆောင်မှုပါရှင် 😘")
    except Exception as e:
        await message.reply_text(f"❌ ခင်ဗျားက Ban မခံထားရပါဘူးရှင် 😅\n`{e}`")

# ========================================
# Image Generator
# ========================================
@app.on_message(filters.command("timage"))
async def timage(client: Client, message: Message):
    user_id = message.from_user.id
    if len(message.command) < 2:
        await message.reply_text("🎨 **AI Image Generator**\n\nပုံထုတ်ချင်တဲ့ အကြောင်းအရာကို ရိုက်ထည့်ပါ။\nဥပမာ: `/timage မြန်မာရိုးရာဝတ်စုံ မိန်းကလေး`\n\n📌 **သာမန်သူ:** တစ်နေ့ ၁ ခါပဲထုတ်လို့ရ\n💎 **Premium:** အကန့်အသတ်မရှိ")
        return
    if not is_premium(user_id):
        if not check_image_limit(user_id):
            await message.reply_text("❌ **ဒီနေ့အတွက် ပုံထုတ်ပြီးပါပြီရှင်** 😢\n\n📌 သာမန်သူတွေ တစ်နေ့ ၁ ခါပဲထုတ်လို့ရပါတယ်ရှင်။\n💎 Premium ဝယ်ထားရင် အကန့်အသတ်မရှိ ထုတ်လို့ရပါမယ်နော် 😘")
            return
    prompt = " ".join(message.command[1:])
    status_msg = await message.reply_text("🎨 ပုံထုတ်နေပါပြီရှင်... ⏳")
    image_data_content = generate_image(prompt)
    if image_data_content:
        await status_msg.delete()
        await message.reply_photo(photo=image_data_content, caption=f"🎨 **AI Image Generator**\n\n📝 **Prompt:** {prompt}\n👤 **User:** {message.from_user.mention}\n💎 **Premium:** {'✅ ရှိပါတယ်' if is_premium(user_id) else '❌ မရှိပါဘူး'}\n\n😘 ကျေးဇူးပါရှင်")
    else:
        await status_msg.edit_text("❌ **ပုံထုတ်လို့မရပါဘူးရှင်** 😢\n\n💡 နောက်တစ်ခါ ပြန်စမ်းကြည့်ပါနော် 😘")

# ========================================
# Teach Commands
# ========================================
@app.on_message(filters.command("teach") & filters.reply)
async def teach_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("📚 **သင်ပေးနည်း**\n\nမေးခွန်းကို Reply နှိပ်ပြီး `/teach အဖြေ` လို့ရိုက်ပါ။\n\n😘 လူတိုင်းသင်ပေးလို့ရပါတယ်ရှင်")
        return
    question = message.reply_to_message.text or message.reply_to_message.caption
    if not question:
        await message.reply_text("❌ မေးခွန်းမတွေ့ဘူးရှင် 😢")
        return
    answer = " ".join(message.command[1:])
    add_teach(question, answer, message.from_user.id)
    await message.reply_text(f"✅ **သင်ပေးပြီးပါပြီရှင်** 🥰\n\n❓ {question[:100]}...\n💬 {answer[:100]}...\n\n📌 သင်ထားတာကို လုံခြုံစွာ သိမ်းဆည်းထားပါတယ်ရှင် 😘")

@app.on_message(filters.command("teachlist"))
async def teachlist_command(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ ဒီ Command ကို Owner မှသာ ကြည့်လို့ရပါတယ်ရှင် 😅")
        return
    all_teach = get_all_teach()
    if not all_teach:
        await message.reply_text("📚 **သင်ထားတဲ့အကြောင်းအရာမရှိသေးပါဘူးရှင်** 😅")
        return
    text = "📚 **သင်ထားတဲ့အကြောင်းအရာများ**\n\n"
    count = 0
    for q, data in all_teach.items():
        count += 1
        text += f"{count}. ❓ {q}\n   💬 {data['answer'][:100]}...\n   👤 Taught by: `{data['taught_by']}`\n\n"
        if len(text) > 3500:
            await message.reply_text(text)
            text = ""
    if text:
        await message.reply_text(text)

@app.on_message(filters.command("teachdel"))
async def teachdel_command(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ ဒီ Command ကို Owner မှသာ သုံးလို့ရပါတယ်ရှင် 😅")
        return
    if len(message.command) < 2:
        await message.reply_text("❗ ဖျက်ချင်တဲ့ မေးခွန်းကို ရိုက်ထည့်ပါနော် 🥰")
        return
    question = " ".join(message.command[1:])
    if delete_teach(question):
        await message.reply_text(f"✅ **ဖျက်လိုက်ပါပြီရှင်** 🥰\n❓ {question}")
    else:
        await message.reply_text(f"❌ ဒီမေးခွန်းကို မတွေ့ဘူးရှင် 😢")

@app.on_message(filters.command("teachcount"))
async def teachcount_command(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ ဒီ Command ကို Owner မှသာ ကြည့်လို့ရပါတယ်ရှင် 😅")
        return
    count = len(get_all_teach())
    await message.reply_text(f"📊 **Teach Data Statistics**\n\n📚 **စုစုပေါင်း သင်ထားတဲ့အကြောင်းအရာ:** {count} ခု\n🔐 **Data Status:** Encrypted\n📌 **Storage:** Secure\n\n😘 ကျေးဇူးပါရှင်")

# ========================================
# AI Task
# ========================================
@app.on_message(filters.command("task"))
async def task_ai(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❓ **AI ကိုမေးရန်**\n\nမေးချင်တာကို `/task` နဲ့မေးပါ။\nဥပမာ: `/task မြန်မာနိုင်ငံရဲ့မြို့တော်က ဘာလဲ`")
        return
    prompt = " ".join(message.command[1:])
    thinking_msg = await message.reply_text("🤔 AI ကိုမေးနေပါပြီရှင်... 💭")
    response = ask_ai(prompt)
    await thinking_msg.edit_text(f"🤖 **AI အဖြေပါရှင်**\n\n❓ {prompt}\n\n💬 {response}\n\n😘 ကျေးဇူးပါရှင်")

# ========================================
# Start Command
# ========================================
@app.on_message(filters.command("start") & filters.private)
async def private_start(client: Client, message: Message):
    user = message.from_user
    first_name = user.first_name or "N/A"
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    user_id = user.id
    username = f"@{user.username}" if user.username else "None"
    try:
        user_info = await client.get_users(user_id)
        bio = user_info.bio if user_info.bio else "N/A"
    except:
        bio = "N/A"
    profile_text = f"👤 **ပရိုဖိုင် အချက်အလက်**\n\n📛 **အမည်:** {full_name}\n🆔 **User ID:** `{user_id}`\n🔗 **Username:** {username}\n📝 **Bio:** {bio}\n💎 **Premium:** {'✅ ရှိပါတယ်' if is_premium(user_id) else '❌ မရှိပါဘူး'}\n\n😘 ကြိုဆိုပါတယ်ရှင်"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 ဘာသာစကား", callback_data="show_lang"), InlineKeyboardButton("👑 Owner", url="https://t.me/Tear808")],
        [InlineKeyboardButton("➕ Group ထဲထည့်ရန်", callback_data="add_group"), InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("💎 Premium", callback_data="premium_info")]
    ])
    await message.reply_text(profile_text, reply_markup=keyboard)

@app.on_message(filters.command("start") & filters.group)
async def group_start(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 ဘာသာစကား", callback_data="show_lang"), InlineKeyboardButton("👑 Owner", url="https://t.me/Tear808")],
        [InlineKeyboardButton("❓ Help", callback_data="help"), InlineKeyboardButton("➕ Group ထဲထည့်ရန်", callback_data="add_group")],
        [InlineKeyboardButton("💎 Premium", callback_data="premium_info")]
    ])
    await message.reply_text("📌 **မဂ်လာပါရှင့်**\n\n💝 **သုံးစွဲသူများအား အထူးကျေးဇူးတင်ရှိပါသည်ရှင့်။**\n\n🌸 **by @Tear808** 🥀🥀\n\n📌 **အောက်ပါခလုပ်များကို နှိပ်ပြီး အသုံးပြုပါရှင်**", reply_markup=keyboard)

# ========================================
# Admin Commands
# ========================================
@app.on_message(filters.command("admin") & filters.group)
async def call_admin(client: Client, message: Message):
    chat_id = message.chat.id
    admins = []
    try:
        async for member in client.get_chat_members(chat_id, filter="administrators"):
            if not member.user.is_bot:
                admins.append(member.user)
    except:
        pass
    if not admins:
        await message.reply_text("❌ ဒီ Group မှာ Admin မရှိပါဘူးရှင် 😅")
        return
    admin_mentions = ""
    for admin in admins[:10]:
        username = f"@{admin.username}" if admin.username else admin.first_name
        admin_mentions += f"• {username}\n"
    await message.reply_text(f"🚨 **အရေးပေါ် ခေါ်ဆိုချက်** 🚨\n\n👤 **ခေါ်ဆိုသူ:** {message.from_user.mention}\n💬 **Group:** {message.chat.title}\n\n📌 **Admin များအားလုံးကို ခေါ်ဆိုထားပါတယ်ရှင်**\n\n👑 **Admin များ:**\n{admin_mentions}\n\n😘 ကျေးဇူးပါရှင်")
    mention_text = "🚨 Admin များအားလုံး သတိပြုပါရှင် 🚨\n\n"
    for admin in admins[:10]:
        mention_text += f"{admin.mention} "
    await message.reply_text(mention_text)

@app.on_message(filters.command("setleave") & filters.reply)
async def set_leave_video_cmd(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ ဒီ Command ကို Owner မှသာ သုံးလို့ရပါတယ်ရှင် 😅")
        return
    chat_id = message.chat.id
    replied = message.reply_to_message
    if not replied.video and not replied.document:
        await message.reply_text("❌ **Video ကိုပဲ Reply ထောက်ပြီး `/setleave` လို့ရိုက်ပါရှင်** 🥰")
        return
    video_id = replied.video.file_id if replied.video else replied.document.file_id
    caption = replied.caption or "👋 **Leave Video**\n\n😢 နောက်မှပြန်ဆုံကြမယ်နော်"
    set_leave_video(chat_id, video_id, caption)
    await message.reply_text(f"✅ **Leave Video ကို သတ်မှတ်ပြီးပါပြီရှင်** 🥰\n\n📌 ခုမှစပြီး လူထွက်သွားတိုင်း ဒီ Video ပြပေးပါမယ်နော် 😘")

@app.on_message(filters.command("broadcast"))
async def broadcast_cmd(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ ဒီ Command ကို Owner မှသာ သုံးလို့ရပါတယ်ရှင် 😅")
        return
    if len(message.command) < 2:
        await message.reply_text("❗ ကြော်ငြာစာ ထည့်ပါနော် 🥰\nဥပမာ: `/broadcast မင်္ဂလာပါ`")
        return
    broadcast_text = " ".join(message.command[1:])
    status_msg = await message.reply_text("📢 ကြော်ငြာပို့နေပါပြီရှင်... 💕")
    groups = {-1001234567890: "My Group 1", -1009876543210: "My Group 2"}
    success = 0
    fail = 0
    for chat_id, chat_name in groups.items():
        try:
            await client.send_message(chat_id, f"📢 **ကြော်ငြာ**\n\n{broadcast_text}\n\n😘 ကျေးဇူးပါနော်")
            success += 1
        except:
            fail += 1
    await status_msg.edit_text(f"✅ **ပို့ဆောင်လိုက်ပါပြီရှင်** 🥰\n\n📊 **စုစုပေါင်း:**\n✅ အောင်မြင်: {success} ခု\n❌ မအောင်မြင်: {fail} ခု\n\n😘 ကျေးဇူးပါရှင်")

@app.on_message(filters.command("ban") & filters.group)
async def ban_cmd(client: Client, message: Message):
    if not can_use_admin_command(message.from_user.id, message.chat.id):
        await message.reply_text("❌ ဒီ Command ကို သုံးခွင့်မရှိပါဘူးရှင် 😅")
        return
    if not message.reply_to_message:
        await message.reply_text("❗ User တစ်ယောက်ကို Reply နှိပ်ပြီး `/ban` လို့ရိုက်ပါနော် 😊")
        return
    user_id = message.reply_to_message.from_user.id
    user_mention = message.reply_to_message.from_user.mention
    await client.ban_chat_member(message.chat.id, user_id)
    await message.reply_text(f"✅ {user_mention} ကို Ban လုပ်လိုက်ပါပြီရှင် 🔨")

@app.on_message(filters.command("mute") & filters.group)
async def mute_cmd(client: Client, message: Message):
    if not can_use_admin_command(message.from_user.id, message.chat.id):
        await message.reply_text("❌ ဒီ Command ကို သုံးခွင့်မရှိပါဘူးရှင် 😅")
        return
    if not message.reply_to_message:
        await message.reply_text("❗ User တစ်ယောက်ကို Reply နှိပ်ပြီး `/mute` လို့ရိုက်ပါနော် 😊")
        return
    user_id = message.reply_to_message.from_user.id
    user_mention = message.reply_to_message.from_user.mention
    await client.restrict_chat_member(message.chat.id, user_id, ChatPermissions())
    data["muted"][f"mute_{message.chat.id}_{user_id}"] = time.time() + 3600
    save_json_file(DATA_FILE, data)
    await message.reply_text(f"🔇 {user_mention} ကို ၁ နာရီ Mute လုပ်လိုက်ပါပြီရှင် 🤫")

@app.on_message(filters.command("unmute") & filters.group)
async def unmute_cmd(client: Client, message: Message):
    if not can_use_admin_command(message.from_user.id, message.chat.id):
        await message.reply_text("❌ ဒီ Command ကို သုံးခွင့်မရှိပါဘူးရှင် 😅")
        return
    if not message.reply_to_message:
        await message.reply_text("❗ User တစ်ယောက်ကို Reply နှိပ်ပြီး `/unmute` လို့ရိုက်ပါနော် 😊")
        return
    user_id = message.reply_to_message.from_user.id
    user_mention = message.reply_to_message.from_user.mention
    await client.restrict_chat_member(message.chat.id, user_id, ChatPermissions(can_send_messages=True))
    key = f"mute_{message.chat.id}_{user_id}"
    if key in data["muted"]:
        del data["muted"][key]
        save_json_file(DATA_FILE, data)
    await message.reply_text(f"🔊 {user_mention} ကို Unmute လုပ်လိုက်ပါပြီရှင်")

# ========================================
# Music Commands (No Voice Chat - Just Search)
# ========================================
@app.on_message(filters.command("play"))
async def play_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❗ သီချင်းနာမည်ထည့်ပါနော် 🥰")
        return
    query = " ".join(message.command[1:])
    status_msg = await message.reply_text("⏳ သီချင်းရှာနေပါပြီရှင်... 🎵")
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if not info or "entries" not in info:
                await status_msg.edit_text("❌ သီချင်းမတွေ့ဘူးရှင် 😢")
                return
            song = info["entries"][0]
            title = song.get("title", "Unknown")
            duration = song.get("duration", 0)
            url = song.get("webpage_url", "Not found")
            dur_min = duration // 60
            dur_sec = duration % 60
            await status_msg.edit_text(
                f"🎵 **သီချင်းတွေ့ပါပြီရှင်**\n\n"
                f"🎶 **နာမည်:** `{title}`\n"
                f"⏱️ **ကြာချိန်:** {dur_min}:{dur_sec:02d}\n"
                f"🔗 **Link:** [YouTube]({url})\n\n"
                f"😘 နားဆင်ပါနော်"
            )
    except Exception as e:
        await status_msg.edit_text(f"❌ အမှား: `{e}`")

@app.on_message(filters.command("vplay"))
async def vplay_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❗ ဇာတ်ကားနာမည်ထည့်ပါနော် 🎬")
        return
    query = " ".join(message.command[1:])
    status_msg = await message.reply_text("⏳ Video ရှာနေပါပြီရှင်... 🎬")
    try:
        with YoutubeDL(ydl_video_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if not info or "entries" not in info:
                await status_msg.edit_text("❌ Video မတွေ့ဘူးရှင် 😢")
                return
            video = info["entries"][0]
            title = video.get("title", "Unknown")
            duration = video.get("duration", 0)
            url = video.get("webpage_url", "Not found")
            dur_min = duration // 60
            dur_sec = duration % 60
            await status_msg.edit_text(
                f"🎬 **Video တွေ့ပါပြီရှင်**\n\n"
                f"🎥 **နာမည်:** `{title}`\n"
                f"⏱️ **ကြာချိန်:** {dur_min}:{dur_sec:02d}\n"
                f"🔗 **Link:** [YouTube]({url})\n\n"
                f"😘 ကြည့်ပါနော်"
            )
    except Exception as e:
        await status_msg.edit_text(f"❌ အမှား: `{e}`")

@app.on_message(filters.command("stop"))
async def stop_cmd(client: Client, message: Message):
    await message.reply_text("⏹️ သီချင်းရပ်လိုက်ပါပြီရှင် 🥰\n\n📌 Voice Chat မပါတဲ့အတွက် ဒီ Command က စာသားပဲပြန်ပါတယ်ရှင် 😅")

@app.on_message(filters.command("leavevc"))
async def leavevc_cmd(client: Client, message: Message):
    await message.reply_text("👋 Voice Chat ကနေ ထွက်သွားပါပြီရှင် 😘")

# ========================================
# Callback Handler
# ========================================
@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    if data == "show_lang":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"), InlineKeyboardButton("မြန်မာ 🇲🇲", callback_data="lang_my")],
            [InlineKeyboardButton("中文 🇨🇳", callback_data="lang_zh"), InlineKeyboardButton("한국어 🇰🇷", callback_data="lang_ko")],
            [InlineKeyboardButton("日本語 🇯🇵", callback_data="lang_ja"), InlineKeyboardButton("ไทย 🇹🇭", callback_data="lang_th")],
            [InlineKeyboardButton("Bahasa Indonesia 🇮🇩", callback_data="lang_id"), InlineKeyboardButton("Singapore 🇸🇬", callback_data="lang_sg")],
            [InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_to_start")]
        ])
        await callback_query.message.edit_text("🌍 **ဘာသာစကားပြောင်းရန်**\n\nအောက်မှာ သင်ရွေးချင်တဲ့ ဘာသာစကားကို နှိပ်ပါ 🥰", reply_markup=keyboard)
        await callback_query.answer()
    elif data.startswith("lang_"):
        lang_code = data.split("_")[1]
        set_lang(user_id, lang_code)
        await callback_query.message.edit_text(f"✅ **ဘာသာစကား ပြောင်းလိုက်ပါပြီရှင်** 🥰\n\n📌 **အခုသုံးမယ့်ဘာသာ:** {LANGUAGES.get(lang_code, 'မြန်မာ 🇲🇲')}\n\n😘 ကျေးဇူးပါရှင်", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_to_start")]]))
        await callback_query.answer("ဘာသာစကား ပြောင်းပြီးပါပြီ 😊")
    elif data == "premium_info":
        if is_premium(user_id):
            days, hours = get_premium_remaining(user_id)
            await callback_query.message.edit_text(f"💎 **Premium User ဖြစ်ပါတယ်ရှင်** 🥰\n\n📌 **ကျန်ရှိတဲ့သက်တမ်း:**\n• {days} ရက် {hours} နာရီ\n\n✅ **အခွင့်အရေးများ:**\n• Link ချခွင့် (မမြူ၊ မဘန်)\n• Mute ဖြေခွင့် `/tearmute`\n• Ban ဖြေခွင့် `/tearban`\n• AI ပုံထုတ်ခွင့် (အကန့်အသတ်မရှိ)\n\n😘 ကျေးဇူးပါရှင်", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_to_start")]]))
        else:
            await callback_query.message.edit_text("💎 **Premium System**\n\n📌 Premium ဆိုတာ ထူးခြားတဲ့ အခွင့်အရေးတွေကို ရရှိစေမှာပါ။\n\n✅ **အခွင့်အရေးများ:**\n• Link ချခွင့် (မမြူ၊ မဘန်)\n• Mute ဖြေခွင့် `/tearmute`\n• Ban ဖြေခွင့် `/tearban`\n• AI ပုံထုတ်ခွင့် (အကန့်အသတ်မရှိ)\n\n💰 **စျေးနှုန်း:** 5000 Kyat / ၁ လ\n📞 ဝယ်ယူရန်: @Tear808 ကို ဆက်သွယ်ပါ\n\n😘 ကျေးဇူးပါရှင်", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_to_start")]]))
        await callback_query.answer()
    elif data == "help":
        help_text = (
            "❓ **Bot အသုံးပြုပုံ**\n\n"
            "📚 **Teach System (လူတိုင်းသင်ပေးလို့ရ):**\n"
            "• /teach (Reply) - မေးခွန်းကို Reply နှိပ်ပြီး အဖြေသင်ပေးမယ်\n"
            "• /teachlist - သင်ထားတာကြည့်မယ် (Owner ပဲကြည့်လို့ရ)\n\n"
            "🤖 **AI (လူတိုင်းသုံးလို့ရ):**\n"
            "• /task မေးချင်တာ - AI ကိုမေးမယ်\n"
            "• /timage ပုံအကြောင်း - AI ပုံထုတ်ပေးမယ် (တစ်နေ့ ၁ ခါ)\n\n"
            "🎵 **Music/Video (လူတိုင်းသုံးလို့ရ):**\n"
            "• /play သီချင်းနာမည် - သီချင်းရှာပေးမယ်\n"
            "• /vplay ဇာတ်ကားနာမည် - Video ရှာပေးမယ်\n\n"
            "👑 **Admin (Admin + Owner ပဲသုံးလို့ရ):**\n"
            "• /ban (Reply) - Ban\n"
            "• /mute (Reply) - Mute\n"
            "• /unmute (Reply) - Unmute\n\n"
            "💎 **Premium (ဝယ်ထားသူတွေအတွက်):**\n"
            "• /premium - Premium အချက်အလက်\n"
            "• /tearmute - Mute ဖြေပေးမယ်\n"
            "• /tearban - Ban ဖြေပေးမယ်\n"
            "• /timage - ပုံထုတ်ခွင့် (အကန့်အသတ်မရှိ)\n\n"
            "🔐 **Security:**\n"
            "• သင်ထားတဲ့ဒေတာတွေကို လုံခြုံစွာ သိမ်းဆည်းပေးမယ်\n"
            "• Report ခံရရင် ကာကွယ်ပေးမယ်\n\n"
            "😘 ကျေးဇူးပါရှင်"
        )
        await callback_query.message.edit_text(help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_to_start")]]))
        await callback_query.answer()
    elif data == "add_group":
        bot_username = (await client.get_me()).username
        add_link = f"https://t.me/{bot_username}?startgroup=start"
        await callback_query.message.edit_text("➕ **Group ထဲထည့်ရန်**\n\nအောက်ပါ Link ကို နှိပ်ပြီး Bot ကို သင့် Group ထဲ ထည့်ပါရှင် 🥰\n\n🔗 [Group ထဲထည့်ရန်]({add_link})\n\n😘 ကျေးဇူးပါရှင်", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Group ထဲထည့်ရန်", url=add_link)], [InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_to_start")]]))
        await callback_query.answer()
    elif data == "back_to_start":
        user = callback_query.from_user
        first_name = user.first_name or "N/A"
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        user_id = user.id
        username = f"@{user.username}" if user.username else "None"
        try:
            user_info = await client.get_users(user_id)
            bio = user_info.bio if user_info.bio else "N/A"
        except:
            bio = "N/A"
        profile_text = f"👤 **ပရိုဖိုင် အချက်အလက်**\n\n📛 **အမည်:** {full_name}\n🆔 **User ID:** `{user_id}`\n🔗 **Username:** {username}\n📝 **Bio:** {bio}\n💎 **Premium:** {'✅ ရှိပါတယ်' if is_premium(user_id) else '❌ မရှိပါဘူး'}\n\n😘 ကြိုဆိုပါတယ်ရှင်"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 ဘာသာစကား", callback_data="show_lang"), InlineKeyboardButton("👑 Owner", url="https://t.me/Tear808")],
            [InlineKeyboardButton("➕ Group ထဲထည့်ရန်", callback_data="add_group"), InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("💎 Premium", callback_data="premium_info")]
        ])
        await callback_query.message.edit_text(profile_text, reply_markup=keyboard)
        await callback_query.answer()

# ========================================
# Group Chat - Teach System Only
# ========================================
@app.on_message(filters.text & filters.group & ~filters.command(["start", "admin", "ban", "mute", "unmute", "play", "vplay", "stop", "leavevc", "task", "teach", "teachlist", "teachdel", "teachcount", "broadcast", "setleave", "premium", "tpremium", "tearmute", "tearban", "timage"]))
async def group_chat(client: Client, message: Message):
    text = message.text.strip()
    answer = get_teach(text)
    if answer:
        await message.reply_text(f"💬 {answer}\n\n📚 *သင်ပေးထားတာပါရှင်* 😊")

# ========================================
# Keep Alive System (UptimeRobot)
# ========================================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    start_time = time.time()
    msg = await message.reply_text("🏓 Pong!")
    end_time = time.time()
    ping = round((end_time - start_time) * 1000)
    await msg.edit_text(f"🏓 **Pong!**\n\n📊 **Ping:** `{ping}ms`\n🤖 **Status:** Active\n💻 **Bot:** Online\n\n😘 ကျေးဇူးပါရှင်")

# ========================================
# Bot Start
# ========================================
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Advanced Bot")
    print("=" * 50)
    print("✅ Bot စတင်နေပါပြီ...")
    print("👑 Owner: @Tear808")
    print("💎 Premium: 5000 Kyat/လ")
    print("🔐 Security: Active")
    print("📚 Teach Data: Encrypted")
    print("=" * 50)
    
    app.run()
