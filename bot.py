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

# ==========================================
# 1. SOZLAMALAR VA O'ZGARUVCHILAR
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN')
DB_URL = os.environ.get('DATABASE_URL')

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))       # 1-Admin (Asosiy)
ADMIN_2_ID = int(os.environ.get('ADMIN_2_ID', 0))   # 2-Admin (Yordamchi)

CHANNELS = ['@kepakstore', '@uc_bot_tolov_kanali', '@yaxshiboy_pubgmm'] # Ikkita telegram kanal
YT_CHANNEL = 'https://youtube.com/@yaxshiboypubgm?si=A6TVCbV-g8JQb5cG'
INSTA_PROFILE = 'https://www.instagram.com/yaxshiboy_gamer?igsh=OG9uMzFiMm9oc2w2&utm_source=qr'
RECEIPT_CHANNEL = '@uc_bot_tolov_kanali' # Chek (to'lovlar) kanalingiz

MIN_WITHDRAW = 30  
REF_REWARD = 5     

bot = telebot.TeleBot(TOKEN)
pending_withdraws = {} 

# ==========================================
# 2. MA'LUMOTLAR BAZASI (POSTGRESQL)
# ==========================================
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
                cur.execute("INSERT INTO users (user_id, inviter_id, is_verified) VALUES (%s, %s, FALSE)", (user_id, inviter_id))
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
                cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (REF_REWARD, inviter_id))
                return inviter_id
        conn.commit()
    return None

def get_referral_stats(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users WHERE inviter_id = %s", (user_id,))
            total_refs = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM users WHERE inviter_id = %s AND is_verified = TRUE", (user_id,))
            verified_refs = cur.fetchone()[0]
            
            return total_refs, verified_refs

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================
def check_sub(user_id):
    """Barcha Telegram kanallarni tekshirish"""
    for channel in CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status in ['left', 'kicked']:
                return False
        except:
            return False
    return True

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("👤 Kabinet"), KeyboardButton("🔗 Referal"))
    markup.row(KeyboardButton("💸 UC yechib olish"))
    return markup

# ==========================================
# 4. START VA REGISTRATSIYA
# ==========================================
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
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
        bot.send_message(user_id, "Tizimdan foydalanish uchun telefon raqamingizni tasdiqlang.\n\n_Quyidagi tugmani bosing:_ 👇", reply_markup=markup, parse_mode="Markdown")
        return

    proceed_to_channels(user_id)

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
        for i, channel in enumerate(CHANNELS, 1):
            markup.add(InlineKeyboardButton(text=f"Telegram kanal {i}", url=f"https://t.me/{channel.replace('@', '')}"))
        markup.add(InlineKeyboardButton(text="YouTube kanal", url=YT_CHANNEL))
        markup.add(InlineKeyboardButton(text="Instagram profil", url=INSTA_PROFILE))
        markup.add(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="verify_sub"))
        
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
        bot.answer_callback_query(call.id, "❌ Siz barcha Telegram kanallarga a'zo bo'lmadingiz! Iltimos, tekshirib qayta bosing.", show_alert=True)

def reward_inviter(user_id):
    inviter_id = update_verification_and_reward(user_id)
    if inviter_id:
        try:
            bot.send_message(inviter_id, f"🎉 Yangi referal qo'shildi. Balansingiz {REF_REWARD} UC ga oshdi.")
        except:
            pass 

# ==========================================
# 5. ASOSIY MENYU TUGMALARI
# ==========================================
@bot.message_handler(func=lambda message: message.text in ["👤 Kabinet", "🔗 Referal", "💸 UC yechib olish"])
def handle_menu_buttons(message):
    user_id = message.chat.id
    user_data = get_user(user_id)
    
    if not check_sub(user_id):
        proceed_to_channels(user_id)
        return

    balance = user_data[0] 

    if message.text == "👤 Kabinet":
        bot.send_message(user_id, f"**Shaxsiy kabinet**\n\n💰 Sizning balansingiz: **{balance} UC**", parse_mode="Markdown")

    elif message.text == "🔗 Referal":
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        total_refs, verified_refs = get_referral_stats(user_id)
        
        text = (
            f"🔗 **Sizning referal havolangiz:**\n`{ref_link}`\n\n"
            f"📊 **Sizning statistikangiz:**\n"
            f"👥 Umumiy chaqirilganlar: **{total_refs} ta**\n"
            f"✅ Tasdiqlangan (UC keltirganlar): **{verified_refs} ta**\n\n"
            f"Har bir taklif qilingan va tasdiqlangan do'stingiz uchun **{REF_REWARD} UC** olasiz!"
        )
        bot.send_message(user_id, text, parse_mode="Markdown")

    elif message.text == "💸 UC yechib olish":
        if balance < MIN_WITHDRAW:
            bot.send_message(user_id, f"❌ Yechib olish uchun balansingizda kamida **{MIN_WITHDRAW} UC** bo'lishi kerak.\n\nSizda hozir: **{balance} UC**", parse_mode="Markdown")
            return
        
        amounts = [30, 60, 90, 120, 180, 240, 360, 440]
        markup = InlineKeyboardMarkup(row_width=2)
        buttons = [InlineKeyboardButton(text=f"{amt} UC", callback_data=f"wa_{amt}") for amt in amounts]
        markup.add(*buttons)
        bot.send_message(user_id, f"💰 Joriy balans: **{balance} UC**\n\nQancha UC yechib olmoqchisiz? Miqdorni tanlang:", reply_markup=markup, parse_mode="Markdown")

# ==========================================
# 6. YECHIB OLISH JARAYONI
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("wa_"))
def amount_selection_callback(call):
    user_id = call.message.chat.id
    selected_amount = int(call.data.split("_")[1])
    
    user_data = get_user(user_id)
    balance = user_data[0]
    
    if balance < selected_amount:
        bot.answer_callback_query(call.id, f"❌ Balansingizda yetarli UC yo'q!\nSizning balansingiz: {balance} UC", show_alert=True)
        return
        
    pending_withdraws[user_id] = selected_amount
    bot.delete_message(user_id, call.message.message_id)
    
    msg = bot.send_message(user_id, f"Siz **{selected_amount} UC** yechib olishni tanladingiz.\n\nIltimos, o'yin ichidagi **PUBG ID** raqamingizni aniq qilib yuboring:", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_pubg_id)

def process_pubg_id(message):
    user_id = message.chat.id
    pubg_id = message.text
    
    if user_id not in pending_withdraws:
        bot.send_message(user_id, "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", reply_markup=get_main_menu())
        return
        
    amount = pending_withdraws[user_id]
    user_data = get_user(user_id)
    balance = user_data[0]
    
    if balance < amount:
        bot.send_message(user_id, "Balansingizda yetarli UC yo'q.", reply_markup=get_main_menu())
        del pending_withdraws[user_id]
        return
        
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (amount, user_id))
            cur.execute("INSERT INTO withdrawals (user_id, pubg_id, amount) VALUES (%s, %s, %s) RETURNING id", (user_id, pubg_id, amount))
            req_id = cur.fetchone()[0]
        conn.commit()
        
    del pending_withdraws[user_id]
    bot.send_message(user_id, "✅ So'rovingiz adminlarga yuborildi. Hisobingizga tushganda sizga xabar beramiz.", reply_markup=get_main_menu())
    
    admin_text = f"🔔 **Yangi UC yechish so'rovi!**\n\nUser ID: `{user_id}`\nPUBG ID: `{pubg_id}`\nMiqdor: **{amount} UC**"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(text="✅ To'landi", callback_data=f"pay_{req_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{req_id}")
    )
    
    for admin in [ADMIN_ID, ADMIN_2_ID]:
        if admin != 0:
            try:
                bot.send_message(admin, admin_text, reply_markup=markup, parse_mode="Markdown")
            except:
                pass

# ==========================================
# 7. ADMIN TASDIQLASHI VA CHEK KANAL
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_") or call.data.startswith("cancel_"))
def admin_action(call):
    action, req_id = call.data.split("_")
    req_id = int(req_id)
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, amount, status, pubg_id FROM withdrawals WHERE id = %s", (req_id,))
            req = cur.fetchone()
            
            if not req or req[2] != 'pending':
                bot.answer_callback_query(call.id, "Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
                return
                
            user_id, amount, status, pubg_id = req
            
            if action == "pay":
                cur.execute("UPDATE withdrawals SET status = 'paid' WHERE id = %s", (req_id,))
                bot.edit_message_text(f"✅ {amount} UC to'langanligi tasdiqlandi.", call.message.chat.id, call.message.message_id)
                try:
                    bot.send_message(user_id, f"🎉 **Tabriklaymiz!**\nSizning hisobingizga **{amount} UC** muvaffaqiyatli tushirildi. O'yinga kirib tekshirib ko'ring!", parse_mode="Markdown")
                except:
                    pass
                
                if RECEIPT_CHANNEL:
                    receipt_text = (
                        f"✅ **To'lov muvaffaqiyatli bajarildi**\n\n"
                        f"👤 ID: `{user_id}`\n"
                        f"🎮 PUBG ID: `{pubg_id}`\n"
                        f"💰 Miqdor: **{amount} UC**\n\n"
                        f"🤖 _Bizning bot orqali ishlangan_"
                    )
                    try:
                        bot.send_message(RECEIPT_CHANNEL, receipt_text, parse_mode="Markdown")
                    except:
                        pass
            
            elif action == "cancel":
                cur.execute("UPDATE withdrawals SET status = 'cancelled' WHERE id = %s", (req_id,))
                cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id)) 
                bot.edit_message_text(f"❌ So'rov bekor qilindi. UC balansiga qaytarildi.", call.message.chat.id, call.message.message_id)
                try:
                    bot.send_message(user_id, f"❌ Sizning {amount} UC yechish so'rovingiz bekor qilindi. UC balansingizga qaytarildi.")
                except:
                    pass
        conn.commit()

# ==========================================
# 8. ADMIN KOMANDALARI VA REKLAMA
# ==========================================
@bot.message_handler(commands=['adduc'])
def admin_add_uc(message):
    admin_id = message.chat.id
    if admin_id not in [ADMIN_ID, ADMIN_2_ID]:
        return

    args = message.text.split()
    if len(args) != 3:
        bot.send_message(admin_id, "❌ **Xato format.**\n`/adduc [user_id] [miqdor]`", parse_mode="Markdown")
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
            cur.execute("SELECT user_id, balance FROM users WHERE user_id = %s", (target_user_id,))
            user = cur.fetchone()
            if not user:
                bot.send_message(admin_id, f"❌ `{target_user_id}` ID topilmadi.", parse_mode="Markdown")
                return
            cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, target_user_id))
            new_balance = user[1] + amount
        conn.commit()

    bot.send_message(admin_id, f"✅ Qo'shildi: **{amount} UC**\nYangi balans: **{new_balance} UC**", parse_mode="Markdown")
    if amount > 0:
        try:
            bot.send_message(target_user_id, f"🎁 Admin tomonidan hisobingizga **{amount} UC** qo'shildi!", parse_mode="Markdown")
        except:
            pass

@bot.message_handler(commands=['reklama'])
def broadcast_command(message):
    admin_id = message.chat.id
    if admin_id != ADMIN_ID: # Faqat 1-Adminga ruxsat
        return

    msg = bot.send_message(admin_id, "📢 **Reklama yuborish bo'limi**\n\nBarcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni tashlang:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    admin_id = message.chat.id
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users")
            users = cur.fetchall()
            
    bot.send_message(admin_id, "⏳ Reklama yuborish boshlandi...")
    success_count = 0
    for user in users:
        try:
            bot.copy_message(user[0], admin_id, message.message_id)
            success_count += 1
        except:
            pass
    bot.send_message(admin_id, f"✅ **Reklama yakunlandi!**\n\nMuvaffaqiyatli yuborildi: **{success_count} ta** foydalanuvchiga.", parse_mode="Markdown")

@bot.message_handler(commands=['kanalga_post'])
def channel_broadcast_command(message):
    admin_id = message.chat.id
    if admin_id != ADMIN_ID: # Faqat 1-Adminga ruxsat
        return

    msg = bot.send_message(admin_id, "📢 **Kanallarga post joylash**\n\nBarcha homiy kanallarga yubormoqchi bo'lgan xabaringizni tashlang:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_channel_broadcast)

def process_channel_broadcast(message):
    admin_id = message.chat.id
    bot.send_message(admin_id, "⏳ Kanallarga xabar joylash boshlandi...")
    success_count = 0
    for channel in CHANNELS:
        try:
            bot.copy_message(channel, admin_id, message.message_id)
            success_count += 1
        except:
            bot.send_message(admin_id, f"⚠️ Xatolik ({channel}): Kanalda admin emas yoki xabar yozish ruxsati yo'q.")
    bot.send_message(admin_id, f"✅ **Post yakunlandi!**\n\nMuvaffaqiyatli joylandi: **{success_count} ta** kanalga.", parse_mode="Markdown")

# ==========================================
# 9. KANALDAN CHIQIB KETGANLARNI JAZOLASH (ANTI-CHEAT)
# ==========================================
@bot.chat_member_handler()
def handle_chat_member(message):
    if message.new_chat_member.status in ['left', 'kicked']:
        user_id = message.new_chat_member.user.id
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT inviter_id, is_verified FROM users WHERE user_id = %s", (user_id,))
                user = cur.fetchone()
                
                if user and user[0] and user[1]:
                    inviter_id = user[0]
                    cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (REF_REWARD, inviter_id))
                    cur.execute("UPDATE users SET is_verified = FALSE WHERE user_id = %s", (user_id,))
                    try:
                        bot.send_message(inviter_id, f"⚠️ **Ogohlantirish!**\n\nSiz taklif qilgan do'stlaringizdan biri homiy kanallarni tark etdi. Shu sababli balansingizdan **{REF_REWARD} UC** ayirildi.", parse_mode="Markdown")
                    except:
                        pass
            conn.commit()

# ==========================================
# 10. BOTNI ISHGA TUSHIRISH
# ==========================================
if __name__ == "__main__":
    # Avvalgi ulanishlarni uzib tashlash (409 Conflict oldini oladi)
    bot.remove_webhook()
    
    # Botga barcha turdagi xabarlarni o'qishga ruxsat berish
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'chat_member'])
