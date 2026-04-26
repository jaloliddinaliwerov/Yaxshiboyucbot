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
TOKEN = os.environ.get('BOT_TOKEN')
DB_URL = os.environ.get('DATABASE_URL')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0)) 

TG_CHANNEL = '@yaxshiboy_pubgmm' 
YT_CHANNEL = 'https://youtube.com/@yaxshiboypubgm?si=A6TVCbV-g8JQb5cG'

MIN_WITHDRAW = 30  # Yechish uchun minimal miqdor
REF_REWARD = 5     # 1 ta referal uchun beriladigan UC

bot = telebot.TeleBot(TOKEN)

# ----------------- MA'LUMOTLAR BAZASI -----------------
def get_db_connection():
    return psycopg2.connect(DB_URL)

def init_db():
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
            cur.execute('''
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    pubg_id VARCHAR(50),
                    amount INTEGER,
                    status VARCHAR(20) DEFAULT 'pending'
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
                # Referal uchun 5 UC qo'shish
                cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (REF_REWARD, inviter_id))
                return inviter_id
        conn.commit()
    return None

def check_sub(user_id):
    try:
        status = bot.get_chat_member(TG_CHANNEL, user_id).status
        if status in ['left', 'kicked']:
            return False
    except:
        return False
    return True

# ----------------- ASOSIY MENYU TUGMALARI -----------------
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("👤 Kabinet"), KeyboardButton("🔗 Referal"))
    markup.row(KeyboardButton("💸 UC yechib olish"))
    return markup

# ----------------- ASOSIY MANTIQ -----------------
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    args = message.text.split()
    
    inviter_id = None
    if len(args) > 1 and args[1].isdigit():
        inviter = int(args[1])
        if inviter != user_id:
            inviter_id = inviter

    add_user(user_id, inviter_id)
    user_data = get_user(user_id)

    if not user_data[3]: 
        ask_for_contact(user_id)
        return

    proceed_to_channels(user_id)

def ask_for_contact(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    bot.send_message(user_id, "Tizimdan foydalanish uchun telefon raqamingizni tasdiqlang.\n\n_Quyidagi tugmani bosing:_ 👇", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    user_id = message.chat.id
    if message.contact.user_id != user_id:
        bot.send_message(user_id, "Iltimos, o'zingizga tegishli bo'lgan raqamni yuboring.")
        return

    update_phone(user_id, message.contact.phone_number)
    bot.send_message(user_id, "✅ Raqamingiz muvaffaqiyatli qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    proceed_to_channels(user_id)

def proceed_to_channels(user_id):
    user_data = get_user(user_id)

    if not check_sub(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(text="Telegram kanal", url=f"https://t.me/{TG_CHANNEL.replace('@', '')}"),
            InlineKeyboardButton(text="YouTube kanal", url=YT_CHANNEL),
            InlineKeyboardButton(text="Tasdiqlash", callback_data="verify_sub")
        )
        bot.send_message(user_id, "Balansingizni boshqarish uchun quyidagi resurslarimizga obuna bo'ling:", reply_markup=markup)
    else:
        if not user_data[1]: 
            reward_inviter(user_id)
        bot.send_message(user_id, "✅ Bosh menyuga xush kelibsiz!", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "verify_sub")
def verify_callback(call):
    user_id = call.message.chat.id
    if check_sub(user_id):
        bot.delete_message(user_id, call.message.message_id)
        user_data = get_user(user_id)
        if not user_data[1]:
            reward_inviter(user_id)
        bot.send_message(user_id, "✅ Muvaffaqiyatli tasdiqlandi. Bosh menyuga xush kelibsiz!", reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "Barcha kanallarga obuna bo'lmagansiz.", show_alert=True)

def reward_inviter(user_id):
    inviter_id = update_verification_and_reward(user_id)
    if inviter_id:
        try:
            bot.send_message(inviter_id, f"🎉 Yangi referal qo'shildi. Balansingiz {REF_REWARD} UC ga oshdi.")
        except:
            pass 

# ----------------- TUGMALARNI BOSHQARISH -----------------
@bot.message_handler(func=lambda message: message.text in ["👤 Kabinet", "🔗 Referal", "💸 UC yechib olish"])
def handle_menu_buttons(message):
    user_id = message.chat.id
    user_data = get_user(user_id)
    
    # Har qanday tugmani bosganda avval obunani tekshirish
    if not check_sub(user_id):
        proceed_to_channels(user_id)
        return

    balance = user_data[0] 

    if message.text == "👤 Kabinet":
        text = f"**Shaxsiy kabinet**\n\n💰 Sizning balansingiz: **{balance} UC**"
        bot.send_message(user_id, text, parse_mode="Markdown")

    elif message.text == "🔗 Referal":
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        text = (
            f"🔗 **Sizning referal havolangiz:**\n`{ref_link}`\n\n"
            f"Har bir taklif qilingan va kanallarga a'zo bo'lgan do'stingiz uchun **{REF_REWARD} UC** olasiz!"
        )
        bot.send_message(user_id, text, parse_mode="Markdown")

    elif message.text == "💸 UC yechib olish":
        if balance < MIN_WITHDRAW:
            bot.send_message(user_id, f"❌ Yechib olish uchun balansingizda kamida **{MIN_WITHDRAW} UC** bo'lishi kerak.\n\nSizda hozir: **{balance} UC**", parse_mode="Markdown")
            return
        
        msg = bot.send_message(user_id, "Iltimos, o'yin ichidagi **PUBG ID** raqamingizni aniq qilib yuboring:", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_pubg_id)

# ----------------- UC YECHIB OLISH MANTIQI -----------------
def process_pubg_id(message):
    user_id = message.chat.id
    pubg_id = message.text
    
    user_data = get_user(user_id)
    balance = user_data[0]
    
    if balance < MIN_WITHDRAW:
        bot.send_message(user_id, "Balansingizda yetarli UC yo'q.", reply_markup=get_main_menu())
        return
        
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (balance, user_id))
            cur.execute("INSERT INTO withdrawals (user_id, pubg_id, amount) VALUES (%s, %s, %s) RETURNING id", (user_id, pubg_id, balance))
            req_id = cur.fetchone()[0]
        conn.commit()
        
    bot.send_message(user_id, "✅ So'rovingiz adminga yuborildi. Hisobingizga tushganda sizga xabar beramiz.", reply_markup=get_main_menu())
    
    if ADMIN_ID != 0:
        admin_text = f"🔔 **Yangi UC yechish so'rovi!**\n\nUser ID: `{user_id}`\nPUBG ID: `{pubg_id}`\nMiqdor: **{balance} UC**"
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton(text="✅ To'landi", callback_data=f"pay_{req_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{req_id}")
        )
        try:
            bot.send_message(ADMIN_ID, admin_text, reply_markup=markup, parse_mode="Markdown")
        except:
            pass

# ----------------- ADMIN BOSHQARUVI -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_") or call.data.startswith("cancel_"))
def admin_action(call):
    action, req_id = call.data.split("_")
    req_id = int(req_id)
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = %s", (req_id,))
            req = cur.fetchone()
            
            if not req or req[2] != 'pending':
                bot.answer_callback_query(call.id, "Bu so'rov allaqachon bajarilgan.", show_alert=True)
                return
                
            user_id, amount, status = req
            
            if action == "pay":
                cur.execute("UPDATE withdrawals SET status = 'paid' WHERE id = %s", (req_id,))
                bot.edit_message_text(f"✅ {amount} UC to'langanligi tasdiqlandi.", call.message.chat.id, call.message.message_id)
                bot.send_message(user_id, f"🎉 **Tabriklaymiz!**\nSizning hisobingizga **{amount} UC** muvaffaqiyatli tushirildi. O'yinga kirib tekshirib ko'ring!", parse_mode="Markdown")
            
            elif action == "cancel":
                cur.execute("UPDATE withdrawals SET status = 'cancelled' WHERE id = %s", (req_id,))
                cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id)) 
                bot.edit_message_text(f"❌ So'rov bekor qilindi. UC qaytarildi.", call.message.chat.id, call.message.message_id)
                bot.send_message(user_id, f"❌ Sizning {amount} UC yechish so'rovingiz bekor qilindi. UC balansingizga qaytarildi.")
                
        conn.commit()
# ----------------- UC QO'SHISH (ADMIN YASHIRIN KOMANDASI) -----------------
@bot.message_handler(commands=['adduc'])
def admin_add_uc(message):
    admin_id = message.chat.id
    
    # Faqat ADMIN_ID ga ruxsat berish
    if admin_id != ADMIN_ID:
        return

    args = message.text.split()
    
    # Formatni tekshirish
    if len(args) != 3:
        bot.send_message(
            admin_id, 
            "❌ **Xato format.**\n\nTo'g'ri foydalanish:\n`/adduc [foydalanuvchi_id] [miqdor]`\n_Masalan: /adduc 123456789 100_", 
            parse_mode="Markdown"
        )
        return

    target_user_id = args[1]
    amount = args[2]

    if not target_user_id.isdigit() or not amount.lstrip('-').isdigit():
        bot.send_message(admin_id, "❌ ID va miqdor faqat raqamlardan iborat bo'lishi kerak.")
        return

    target_user_id = int(target_user_id)
    amount = int(amount)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Foydalanuvchi bazada borligini tekshirish
            cur.execute("SELECT user_id, balance FROM users WHERE user_id = %s", (target_user_id,))
            user = cur.fetchone()
            
            if not user:
                bot.send_message(admin_id, f"❌ `{target_user_id}` ID li foydalanuvchi bazada topilmadi.", parse_mode="Markdown")
                return
            
            # Balansni yangilash
            cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, target_user_id))
            new_balance = user[1] + amount
            
        conn.commit()

    # Adminga hisobot
    bot.send_message(
        admin_id, 
        f"✅ **Muvaffaqiyatli!**\n\nFoydalanuvchi: `{target_user_id}`\nQo'shildi: **{amount} UC**\nYangi balans: **{new_balance} UC**", 
        parse_mode="Markdown"
    )
    
    # Foydalanuvchiga xabar yuborish
    try:
        if amount > 0:
            bot.send_message(
                target_user_id, 
                f"🎁 **Bonus!**\n\nAdmin tomonidan hisobingizga **{amount} UC** qo'shildi!\nKabinetga kirib balansingizni tekshirishingiz mumkin.", 
                parse_mode="Markdown"
            )
    except:
        bot.send_message(admin_id, "⚠️ Foydalanuvchi botni bloklagan ko'rinadi, shuning uchun unga xabar bormadi. Lekin balans bazada yangilandi.")
if __name__ == "__main__":
    bot.infinity_polling()
