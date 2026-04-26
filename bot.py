import os
import telebot
import psycopg2
from telebot.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove
)

# ----------------- SOZLAMALAR -----------------
# Railway Environment Variables orqali avtomatik olinadi
TOKEN = os.environ.get('BOT_TOKEN')
DB_URL = os.environ.get('DATABASE_URL')

bot = telebot.TeleBot(TOKEN)

# Kanallaringizni shu yerda o'zgartiring
TG_CHANNEL = '@yaxshiboy_pubgmm' # O'zingizning Telegram kanalingizni yozing
YT_CHANNEL = 'https://youtube.com/@yaxshiboypubgm?si=A6TVCbV-g8JQb5cG'

# ----------------- MA'LUMOTLAR BAZASI -----------------
def get_db_connection():
    return psycopg2.connect(DB_URL)

def init_db():
    """Baza jadvallarini birinchi marta ishga tushganda yaratish"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    phone VARCHAR(20),
                    inviter_id BIGINT,
                    balance INTEGER DEFAULT 0,
                    is_verified BOOLEAN DEFAULT FALSE
                )
            ''')
        conn.commit()

init_db()

def add_user(user_id, inviter_id=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO users (user_id, inviter_id) VALUES (%s, %s)", (user_id, inviter_id))
        conn.commit()

def update_phone(user_id, phone):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET phone = %s WHERE user_id = %s", (phone, user_id))
        conn.commit()

def get_user(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance, is_verified, inviter_id, phone FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone()

def update_verification_and_reward(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET is_verified = TRUE WHERE user_id = %s RETURNING inviter_id", (user_id,))
            result = cur.fetchone()
            inviter_id = result[0] if result else None
            
            if inviter_id:
                cur.execute("UPDATE users SET balance = balance + 5 WHERE user_id = %s", (inviter_id,))
                return inviter_id
        conn.commit()
    return None

# ----------------- KANALNI TEKSHIRISH -----------------
def check_sub(user_id):
    """Faqat Telegram kanalni qat'iy tekshiradi"""
    try:
        status = bot.get_chat_member(TG_CHANNEL, user_id).status
        if status in ['left', 'kicked']:
            return False
    except:
        return False
    return True

# ----------------- ASOSIY MANTIQ -----------------
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    args = message.text.split()
    
    # Referal ID ni aniqlash
    inviter_id = None
    if len(args) > 1 and args[1].isdigit():
        inviter = int(args[1])
        if inviter != user_id:
            inviter_id = inviter

    add_user(user_id, inviter_id)
    user_data = get_user(user_id)

    # 1. Raqam borligini tekshirish
    if not user_data[3]: # Telefon raqam yo'q bo'lsa
        ask_for_contact(user_id)
        return

    # 2. Raqam bo'lsa, kanallarni ko'rsatish
    proceed_to_channels(user_id)

def ask_for_contact(user_id):
    """Raqam so'rash uchun maxsus klaviatura"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = KeyboardButton("📱 Raqamni yuborish", request_contact=True)
    markup.add(btn)
    
    bot.send_message(
        user_id, 
        "Tizimdan foydalanish uchun telefon raqamingizni tasdiqlang.\n\n_Quyidagi tugmani bosing:_ 👇", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    user_id = message.chat.id
    
    # Fake kontakt emasligini tekshirish
    if message.contact.user_id != user_id:
        bot.send_message(user_id, "Iltimos, o'zingizga tegishli bo'lgan raqamni yuboring.")
        return

    phone = message.contact.phone_number
    update_phone(user_id, phone)
    
    # Ekranni tozalab (ReplyKeyboardRemove), obunaga o'tkazish
    bot.send_message(
        user_id, 
        "✅ Raqamingiz muvaffaqiyatli qabul qilindi.", 
        reply_markup=ReplyKeyboardRemove()
    )
    proceed_to_channels(user_id)

def proceed_to_channels(user_id):
    """Minimalistik dizaynda kanallarni ko'rsatish"""
    user_data = get_user(user_id)

    if not check_sub(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        
        btn_tg = InlineKeyboardButton(text="Telegram kanal", url=f"https://t.me/{TG_CHANNEL.replace('@', '')}")
        btn_yt = InlineKeyboardButton(text="YouTube kanal", url=YT_CHANNEL)
        btn_verify = InlineKeyboardButton(text="Tasdiqlash", callback_data="verify_sub")
        
        markup.add(btn_tg, btn_yt, btn_verify)

        bot.send_message(
            user_id, 
            "Tizimdan to'liq foydalanish va balansingizni boshqarish uchun quyidagi resurslarimizga obuna bo'ling:", 
            reply_markup=markup
        )
    else:
        # Avval a'zo bo'lgan, lekin is_verified=False bo'lsa
        if not user_data[1]: 
            reward_inviter(user_id)
        show_dashboard(user_id)

@bot.callback_query_handler(func=lambda call: call.data == "verify_sub")
def verify_callback(call):
    user_id = call.message.chat.id
    
    if check_sub(user_id):
        # Eski xabarni o'chirish (tozalik uchun)
        bot.delete_message(user_id, call.message.message_id)
        
        user_data = get_user(user_id)
        if not user_data[1]:
            reward_inviter(user_id)
            
        show_dashboard(user_id)
    else:
        # Tepa qismda pop-up shaklida xatolik chiqadi
        bot.answer_callback_query(call.id, "Barcha kanallarga obuna bo'lmagansiz.", show_alert=True)

def reward_inviter(user_id):
    inviter_id = update_verification_and_reward(user_id)
    if inviter_id:
        try:
            bot.send_message(inviter_id, "🎉 Yangi referal qo'shildi. Balansingiz 5 UC ga oshdi.")
        except:
            pass 

def show_dashboard(user_id):
    """Foydalanuvchining shaxsiy kabineti"""
    user_data = get_user(user_id)
    balance = user_data[0] # Balans miqdori
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = (
        f"**Shaxsiy kabinet**\n\n"
        f"💰 Balans: **{balance} UC**\n\n"
        f"🔗 Referal havola:\n`{ref_link}`\n\n"
        f"_Do'stlaringizni taklif qiling va UC ga ega bo'ling!_"
    )
    bot.send_message(user_id, text, parse_mode="Markdown")

# Server uxlab qolmasligi uchun infinity_polling
if __name__ == "__main__":
    bot.infinity_polling()
