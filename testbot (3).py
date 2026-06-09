import os
import sqlite3
from datetime import datetime
import telebot
from telebot import types

# ---------------------------------------------------------------------------
# 1. CONFIGURATION & CONFIG CONSTANTS
# ---------------------------------------------------------------------------
API_TOKEN = '8710564963:AAE9C_nU8fG26-slpTWQpAdBk6YPVdZo-7U'  # Iyong Token
bot = telebot.TeleBot(API_TOKEN)

OWNER_ID = 6531314640
EXTRA_ADMIN = 8650959684
ADMINS = [OWNER_ID, EXTRA_ADMIN]

STARS_CHANNEL_ID = -1003846885691
LOGS_GROUP_ID = -1003957577057
GARAGE_LOGS_GROUP_ID = -1003957577057

# Static asset filenames from specification
REGULAR_PROD_IMG = "IMG_20260607_23110111_1_guid(17708fca83e048ddb7ed03bfa63579f0)_gallery.jpg"
VIP_PROD_IMG = "IMG_20260608_00485017_0_guid(ec43f17fb1cf48d78d6cf8de8ed700f2)_gallery.jpg"

PAYPAL_EMAIL_1 = "markryanmanoguid867@gmail.com"
PAYPAL_EMAIL_2 = "tnremail@gmail.com"

PAYMAYA_NAME = "MARKRYAN MANOGUID"
PAYMAYA_NUM = "09281630511"

# Temporary session management dictionary
user_states = {}

# ---------------------------------------------------------------------------
# 2. DATABASE INITIALIZATION
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_purchase_date TEXT,
            last_purchase_date TEXT,
            total_orders INTEGER DEFAULT 0
        )
    ''')
    
    # Regular Inventory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regular_inventory (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_email TEXT,
            date_added TEXT,
            time_added TEXT
        )
    ''')
    
    # VIP Inventory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vip_inventory (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_email TEXT,
            date_added TEXT,
            time_added TEXT
        )
    ''')
    
    # Stock Metadata Table to store last restocked timestamps
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_metadata (
            product_type TEXT PRIMARY KEY,
            last_restock_date TEXT,
            last_restock_time TEXT
        )
    ''')
    
    # Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product TEXT,
            quantity INTEGER,
            payment_method TEXT,
            amount TEXT,
            status TEXT,
            date TEXT,
            time TEXT
        )
    ''')
    
    # Reviews Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product TEXT,
            rating TEXT,
            review_message TEXT,
            screenshot_path TEXT,
            date TEXT,
            time TEXT
        )
    ''')

    # Garage Cars Inventory Table (Bago para sa TNNR Garage)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS garage_cars (
            car_id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT,
            owner TEXT,
            price_stars INTEGER,
            price_paypal REAL,
            price_paymaya REAL,
            photo_file_id TEXT,
            date_added TEXT,
            time_added TEXT
        )
    ''')
    
    # --- FIXED MIGRATION GUARD ---
    try:
        cursor.execute("ALTER TABLE reviews ADD COLUMN username TEXT;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE reviews ADD COLUMN user_id INTEGER;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE reviews ADD COLUMN rating TEXT;")
    except sqlite3.OperationalError:
        pass
        
    # Insert default meta fields if missing
    cursor.execute("INSERT OR IGNORE INTO stock_metadata VALUES ('REGULAR', 'N/A', 'N/A')")
    cursor.execute("INSERT OR IGNORE INTO stock_metadata VALUES ('VIP', 'N/A', 'N/A')")
    cursor.execute("INSERT OR IGNORE INTO stock_metadata VALUES ('GARAGE', 'N/A', 'N/A')")
    
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------------------------
# 3. HELPER METRICS & DATA ENGINE FUNCTIONS
# ---------------------------------------------------------------------------
def get_stock_count(table_name):
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_restock_meta(product_type):
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT last_restock_date, last_restock_time FROM stock_metadata WHERE product_type=?", (product_type,))
    meta = cursor.fetchone()
    conn.close()
    return meta if meta else ("N/A", "N/A")

def register_user_if_new(user_id, username):
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, total_orders) VALUES (?, ?, 0)", (user_id, username or "Anonymous"))
        conn.commit()
    conn.close()

def process_auto_delivery(user_id, username, product_name, qty, payment_method, total_price_str):
    table = "regular_inventory" if "REGULAR" in product_name.upper() else "vip_inventory"
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT account_id, account_email FROM {table} ORDER BY account_id ASC LIMIT ?", (qty,))
    items = cursor.fetchall()
    
    if len(items) < qty:
        conn.close()
        return None
    
    allocated_accounts = []
    ids_to_delete = []
    for item_id, email in items:
        allocated_accounts.append(email)
        ids_to_delete.append(item_id)
        
    for target_id in ids_to_delete:
        cursor.execute(f"DELETE FROM {table} WHERE account_id = ?", (target_id,))
        
    now = datetime.now()
    cur_date = now.strftime("%m/%d/%Y")
    cur_time = now.strftime("%I:%M %p")
    
    cursor.execute('''
        INSERT INTO orders (user_id, username, product, quantity, payment_method, amount, status, date, time)
        VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?)
    ''', (user_id, username or "Anonymous", product_name, qty, payment_method, total_price_str, cur_date, cur_time))
    
    cursor.execute("UPDATE users SET total_orders = total_orders + 1, last_purchase_date = ? WHERE user_id = ?", (cur_date, user_id))
    
    conn.commit()
    conn.close()
    return allocated_accounts

def create_pending_order(user_id, username, product_name, qty, payment_method, total_price_str):
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    now = datetime.now()
    cur_date = now.strftime("%m/%d/%Y")
    cur_time = now.strftime("%I:%M %p")
    
    cursor.execute('''
        INSERT INTO orders (user_id, username, product, quantity, payment_method, amount, status, date, time)
        VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
    ''', (user_id, username or "Anonymous", product_name, qty, payment_method, total_price_str, cur_date, cur_time))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id, cur_date, cur_time

# ---------------------------------------------------------------------------
# 4. MARKUP KEYBOARD LAYOUT GENERATORS
# ---------------------------------------------------------------------------
def main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🛒 SHOP"), types.KeyboardButton("📦 MY ORDERS"))
    markup.add(types.KeyboardButton("🛍 PREVIEWS"), types.KeyboardButton("📤 SEND PREVIEWS"))
    markup.add(types.KeyboardButton("📜 MY PURCHASE HISTORY"))
    if user_id in ADMINS:
        markup.add(types.KeyboardButton("📦🚘 INVENTORY 🚘📦"))
    return markup

def shop_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎁 REGULAR ACCOUNTS", callback_data="prod_regular"),
        types.InlineKeyboardButton("🎁 ACCOUNTS WITH 12K COINS", callback_data="prod_vip"),
        types.InlineKeyboardButton("🎁 DAILY COINFARM", callback_data="prod_coinfarm"),
        types.InlineKeyboardButton("🎁 CHANGE EMAIL & PASSWORD", callback_data="prod_changepw"),
        types.InlineKeyboardButton("🎁 TNNR GARAGE 🚘", callback_data="prod_garage"),
        types.InlineKeyboardButton("🎁 PREVIEWS", callback_data="view_previews"),
        types.InlineKeyboardButton("🎁 SEND PREVIEWS", callback_data="init_send_preview")
    )
    return markup

def buy_quantity_keyboard(prod_code):
    markup = types.InlineKeyboardMarkup(row_width=3)
    volumes = [1, 3, 5, 10, 15, 20, 30, 50]
    buttons = [types.InlineKeyboardButton(f"🛒 BUY {v}", callback_data=f"buy_{prod_code}_{v}") for v in volumes]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("⬅ BACK", callback_data="back_to_shop"))
    return markup

def coinfarm_plans_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛒 BUY 1 MONTH", callback_data="cf_plan_1m"),
        types.InlineKeyboardButton("🛒 BUY 3 MONTHS", callback_data="cf_plan_3m"),
        types.InlineKeyboardButton("🛒 BUY 5 MONTHS", callback_data="cf_plan_5m"),
        types.InlineKeyboardButton("🛒 BUY 10 MONTHS", callback_data="cf_plan_10m"),
        types.InlineKeyboardButton("🛒 BUY LIFETIME", callback_data="cf_plan_lt"),
        types.InlineKeyboardButton("⬅ BACK", callback_data="back_to_shop")
    )
    return markup

def changepw_plans_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛒 BUY 1 MONTH", callback_data="pw_plan_1m"),
        types.InlineKeyboardButton("🛒 BUY 3 MONTHS", callback_data="pw_plan_3m"),
        types.InlineKeyboardButton("🛒 BUY 5 MONTHS", callback_data="pw_plan_5m"),
        types.InlineKeyboardButton("🛒 BUY 10 MONTHS", callback_data="pw_plan_10m"),
        types.InlineKeyboardButton("🛒 BUY LIFETIME", callback_data="pw_plan_lt"),
        types.InlineKeyboardButton("⬅ BACK", callback_data="back_to_shop")
    )
    return markup

def payment_method_keyboard(prod_code, plan_or_qty, stars_avail=True):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if stars_avail:
        markup.add(types.InlineKeyboardButton("⭐ PAY WITH STARS", callback_data=f"pay_stars_{prod_code}_{plan_or_qty}"))
    markup.add(
        types.InlineKeyboardButton("💵 PAY WITH PAYPAL", callback_data=f"pay_paypal_{prod_code}_{plan_or_qty}"),
        types.InlineKeyboardButton("💴 PAY WITH PAYMAYA", callback_data=f"pay_pmaya_{prod_code}_{plan_or_qty}"),
        types.InlineKeyboardButton("⬅ BACK", callback_data="back_to_shop")
    )
    return markup

def admin_order_keyboard(order_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ CONFIRM ORDER", callback_data=f"admin_confirm_{order_id}"),
        types.InlineKeyboardButton("❌ DECLINE ORDER", callback_data=f"admin_decline_{order_id}")
    )
    return markup

# ---------------------------------------------------------------------------
# 5. CORE ROUTING ENGINE COMMAND HANDLING & CORE TELEGRAM ROOT SYSTEM
# ---------------------------------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    register_user_if_new(message.from_user.id, message.from_user.username)
    welcome_text = (
        "👋 Welcome to the TNNR SHOP BOT 🫶\n\n"
        "🚘 Car Parking Multiplayer 2 (CPM2) 🚘\n\n"
        "☠️💀 UNDERGROUND STORE 💀☠️\n\n"
        "Products Available\n"
        "🛍 Products\n"
        "📦 REGULAR ACCOUNTS WITH 20 RANDOM CARS\n"
        "📦 VIP ACCOUNTS WITH 12K COINS\n"
        "🪙 DAILY COINFARM SYSTEM\n"
        "📧 CHANGE EMAIL & PASSWORD BOT\n"
        "🚘 TNNR GARAGE 🚘\n\n"
        "⚡ Instant delivery on most items\n"
        "💯 Verified accounts, guaranteed quality\n"
        "💯 TRUSTED\n\n"
        "Use the buttons below to get started."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_keyboard(message.from_user.id))

@bot.message_handler(func=lambda msg: msg.text in ["🛒 SHOP", "📦 MY ORDERS", "🛍 PREVIEWS", "📤 SEND PREVIEWS", "📜 MY PURCHASE HISTORY", "📦🚘 INVENTORY 🚘📦"])
def handle_root_reply_kb(message):
    user_id = message.from_user.id
    register_user_if_new(user_id, message.from_user.username)
    
    if message.text == "🛒 SHOP":
        bot.send_message(message.chat.id, "Select a product category below:", reply_markup=shop_menu_keyboard())
        
    elif message.text == "📦 MY ORDERS":
        render_my_orders(message.chat.id, user_id)
        
    elif message.text == "🛍 PREVIEWS":
        render_previews(message.chat.id)
        
    elif message.text == "📤 SEND PREVIEWS":
        init_preview_workflow(message.chat.id, user_id)
        
    elif message.text == "📜 MY PURCHASE HISTORY":
        render_purchase_history(message.chat.id, user_id)
        
    elif message.text == "📦🚘 INVENTORY 🚘📦":
        if user_id not in ADMINS:
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📦 REGULAR ACCOUNTS INVENTORY", callback_data="inv_view_reg"),
            types.InlineKeyboardButton("🎁 VIP ACCOUNTS INVENTORY", callback_data="inv_view_vip"),
            types.InlineKeyboardButton("🚘 TNNR GARAGE INVENTORY", callback_data="inv_view_garage"),
            types.InlineKeyboardButton("⬅ BACK", callback_data="close_menu")
        )
        bot.send_message(message.chat.id, "📦📦 INVENTORY CONFIG 📦📦", reply_markup=markup)

# ---------------------------------------------------------------------------
# 6. INLINE CALLBACK DIALOG MANAGEMENT LOGIC
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    username = call.from_user.username or "Anonymous"
    chat_id = call.message.chat.id
    data = call.data

    bot.answer_callback_query(call.id)

    if data == "skip_photo_step":
        user_states[f"rev_photo_{user_id}"] = ""
        advance_to_review_msg(chat_id, user_id)
        return

    if data == "back_to_shop":
        bot.edit_message_text("Select a product category below:", chat_id, call.message.message_id, reply_markup=shop_menu_keyboard())
        return

    if data == "close_menu":
        bot.delete_message(chat_id, call.message.message_id)
        return

    if data == "prod_regular":
        stock = get_stock_count("regular_inventory")
        r_date, r_time = get_restock_meta("REGULAR")
        caption = (
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 REGULAR ACCOUNTS WITH 20 RANDOM CARS 📦\n\n"
            "🛍 REGULAR ACCOUNTS WITH 20 RANDOM CARS\n\n"
            "📝 Description:\n"
            "You can get good accounts based on your luck, so good luck bro bro.\n\n"
            f"📦 Stock:\n{stock}\n\n"
            "⚡ Delivery: Instant\n\n"
            f"🕐 Time of Restocked:\n{r_time}\n\n"
            f"📅 Date of Restocked:\n{r_date}\n\n"
            "💰 Price:\n"
            "⭐ 30 Telegram Stars\n"
            "💵 $2 USD\n"
            "💵 ₱60 PHP\n\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        if os.path.exists(REGULAR_PROD_IMG):
            with open(REGULAR_PROD_IMG, 'rb') as photo:
                bot.send_photo(chat_id, photo, caption=caption, reply_markup=buy_quantity_keyboard("regular"))
        else:
            bot.send_message(chat_id, caption, reply_markup=buy_quantity_keyboard("regular"))

    elif data == "prod_vip":
        stock = get_stock_count("vip_inventory")
        r_date, r_time = get_restock_meta("VIP")
        caption = (
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 VIP ACCOUNTS WITH 12K COINS 📦\n\n"
            "📝 Description:\n"
            "You can get good accounts with 12,000 coins based on your luck, so good luck bro bro.\n\n"
            f"📦 Stock:\n{stock}\n\n"
            "⚡ Delivery: Instant\n\n"
            f"🕐 Time of Restocked:\n{r_time}\n\n"
            f"📅 Date of Restocked:\n{r_date}\n\n"
            "💰 Price:\n"
            "⭐ 200 Telegram Stars\n"
            "💵 $4 USD\n"
            "💵 ₱200 PHP\n\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        if os.path.exists(VIP_PROD_IMG):
            with open(VIP_PROD_IMG, 'rb') as photo:
                bot.send_photo(chat_id, photo, caption=caption, reply_markup=buy_quantity_keyboard("vip"))
        else:
            bot.send_message(chat_id, caption, reply_markup=buy_quantity_keyboard("vip"))

    elif data == "prod_coinfarm":
        text = (
            "🪙 DAILY COINFARM SYSTEM 🪙\n"
            "CPM2 - CAR PARKING MULTIPLAYER 2\n\n"
            "📝 Description:\n"
            "You need to submit your account information so it can be added to the Daily Coinfarm System.\n"
            "Payment must be completed first before the service can be activated.\n"
            "🪙 Estimated Earnings: 1,000 - 1,300 Coins Per Day\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "PRICING\n"
            "Monthly Plan\n"
            "⭐ 300 Telegram Stars\n"
            "💵 $5 USD\n"
            "💵 ₱250 PHP\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Lifetime Plan\n"
            "💵 $60 USD\n"
            "💵 ₱2,500 PHP\n"
            "⚠️ No Telegram Stars payment available for Lifetime Plan.\n"
            "Lifetime purchases are only available through:\n"
            "💵 PayPal\n"
            "💴 PayMaya"
        )
        bot.send_message(chat_id, text, reply_markup=coinfarm_plans_keyboard())

    elif data == "prod_changepw":
        text = (
            "📧 CHANGE EMAIL & PASSWORD BOT 📧\n\n"
            "📝 Description:\n"
            "Hi bro, this product is designed to help you change your email and password more easily.\n"
            "Get yours now bro bro.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "PRICING\n"
            "Monthly Subscription\n"
            "⭐ 150 Telegram Stars\n"
            "💵 $5 USD\n"
            "💵 ₱250 PHP\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Lifetime License\n"
            "💵 $60 USD\n"
            "💵 ₱2,500 PHP\n"
            "⚠️ No Telegram Stars available for Lifetime purchases.\n"
            "Lifetime purchases can only be paid through:\n"
            "💵 PayPal\n"
            "💴 PayMaya"
        )
        bot.send_message(chat_id, text, reply_markup=changepw_plans_keyboard())

    # --- TNNR GARAGE CORE WORKFLOW ---
    elif data == "prod_garage":
        cars_count = get_stock_count("garage_cars")
        g_date, g_time = get_restock_meta("GARAGE")
        text = (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🚘 TNNR GARAGE 🚘\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 Description:\n"
            "You can see all of the available cars in tnnr garage\n\n"
            f"🚘 Available Cars: {cars_count}\n\n"
            "⚡ Delivery: Instant\n"
            f"🕐 Time of Restocked: {g_time}\n"
            f"📅 DATE OF Restocked: {g_date}\n\n"
            "💰 Price:\n"
            "it depends on what cars bro bro you can see the prize under the picture of the car you like\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("WINDOW SHOPPING", callback_data="garage_window_shopping"),
            types.InlineKeyboardButton("WANNA BUY SOME GOOD CARS?", callback_data="garage_wanna_buy"),
            types.InlineKeyboardButton("⬅ BACK", callback_data="back_to_shop")
        )
        bot.send_message(chat_id, text, reply_markup=markup)

    elif data in ["garage_window_shopping", "garage_wanna_buy"]:
        mode = "window" if data == "garage_window_shopping" else "buy"
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, owner, price_stars, price_paypal, price_paymaya, photo_file_id, car_id FROM garage_cars ORDER BY car_id DESC")
        cars = cursor.fetchall()
        conn.close()

        if not cars:
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅ BACK", callback_data="prod_garage"))
            bot.send_message(chat_id, "🚘 No cars in the garage at the moment. Come back later!.", reply_markup=markup)
            return

        for brand, owner, p_stars, p_pp, p_pm, photo_id, car_id in cars:
            caption = (
                f"💵 Prize:\n"
                f"⭐ Telegram stars :{p_stars}\n"
                f"💵 PayPal : ${p_pp:,.0f}\n"
                f"💵 PayMaya : {p_pm:,.0f} ( only Philippines🇵🇭 )\n\n"
                f"👑 owner of the car: {owner}\n"
                f"🚘 Brand ng Car: {brand}\n\n"
                f"💵 Payment method:\n"
                f"⭐ Telegram stars\n"
                f"💵 PayPal\n"
                f"💵 PayMaya( only Philippines🇵🇭 )"
            )
            
            markup = types.InlineKeyboardMarkup()
            if mode == "buy":
                markup.add(types.InlineKeyboardButton("WANNA BUY THIS?", callback_data=f"garbuy_confirm_{car_id}"))
            else:
                markup.add(types.InlineKeyboardButton("🚘 TNNR GARAGE", callback_data="prod_garage"))

            try:
                bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, caption, reply_markup=markup)

    elif data.startswith("garbuy_confirm_"):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, owner, price_stars, price_paypal, price_paymaya, photo_file_id FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        conn.close()

        if not car:
            bot.send_message(chat_id, "❌ Hindi nahanap ang kotse na napili mo, bro.")
            return

        brand, owner, p_stars, p_pp, p_pm, photo_id = car
        
        caption = (
            f"💵 Prize:\n"
            f"⭐ Telegram stars :{p_stars}\n"
            f"💵 PayPal : ${p_pp:,.0f}\n"
            f"{f'💵 PayMaya : {p_pm:,.0f}' if owner == '@Maarkryan' else ''}\n"
            f"👑 owner of the car: {owner}\n"
            f"🚘 Brand ng Car: {brand}"
        )
        
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➡ CONTINUE TO PAYMENT METHOD", callback_data=f"garcheckout_{car_id}"))
        try:
            bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, caption, reply_markup=markup)

    elif data.startswith("garcheckout_"):
        car_id = int(data.split("_")[1])
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, owner, price_stars, price_paypal, price_paymaya FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        conn.close()

        if not car:
            bot.send_message(chat_id, "❌ Error loading car details.")
            return

        brand, owner, p_stars, p_pp, p_pm = car
        
        text = (
            "💳 SELECT PAYMENT METHOD 💳\n\n"
            "Available Payment Methods:\n"
            "💵 PayPal\n"
            "⭐ Telegram Stars\n"
            f"{' can apply: 💴 PayMaya (Philippines Only)' if owner == '@Maarkryan' else ''}\n\n"
            "---\n"
            "TOTAL:\n"
            f"⭐ {p_stars:,} Stars\n"
            f"💵 ${p_pp:,.0f} USD\n"
            f"{f'💴 ₱{p_pm:,.0f} PHP' if owner == '@Maarkryan' else ''}\n"
            "---"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("⭐ PAY WITH STARS", callback_data=f"garpay_stars_{car_id}"))
        markup.add(types.InlineKeyboardButton("💵 PAY WITH PAYPAL", callback_data=f"garpay_paypal_{car_id}"))
        if owner == "@Maarkryan":
            markup.add(types.InlineKeyboardButton("💴 PAY WITH PAYMAYA", callback_data=f"garpay_paymaya_{car_id}"))
        markup.add(types.InlineKeyboardButton("⬅ BACK", callback_data=f"garbuy_confirm_{car_id}"))
        
        bot.send_message(chat_id, text, reply_markup=markup)

    # --- GARAGE PAYMENT SELECTIONS ---
    elif data.startswith("garpay_stars_"):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, price_stars FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        conn.close()

        if not car: return
        brand, p_stars = car

        payload = f"carstars:{car_id}:{user_id}"
        prices = [types.LabeledPrice(label=f"1x Car — {brand}", amount=p_stars)]

        try:
            bot.send_invoice(
                chat_id=chat_id,
                title="🚘 Buy Car via Stars",
                description=f"Pay {p_stars} Stars to deliver your car automatically via log workflow.",
                invoice_payload=payload,
                provider_token="",  
                currency="XTR",
                prices=prices,
                start_parameter="tnnr-car-checkout"
            )
        except Exception as e:
            bot.send_message(chat_id, f"❌ Invoice generation failure: {e}")

    elif data.startswith("garpay_paypal_"):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, price_paypal FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        conn.close()

        if not car: return
        brand, p_pp = car

        text = (
            "1 Car(s) — RANDOM CARS (Example Purchase)\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 PAY ${p_pp:,.0f}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "PAYPAL PAYMENT EMAILS\n"
            f"📩 {PAYPAL_EMAIL_1}\n"
            f"📩 {PAYPAL_EMAIL_2}"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("📋 COPY EMAIL #1", callback_data="copy_em1"),
                   types.InlineKeyboardButton("📋 COPY EMAIL #2", callback_data="copy_em2"))
        markup.add(types.InlineKeyboardButton("✅ I PAID TO EMAIL #1", callback_data=f"garsub_pp_1_{car_id}"),
                   types.InlineKeyboardButton("✅ I PAID TO EMAIL #2", callback_data=f"garsub_pp_2_{car_id}"))
        markup.add(types.InlineKeyboardButton("⬅ BACK", callback_data=f"garcheckout_{car_id}"))
        bot.send_message(chat_id, text, reply_markup=markup)

    elif data.startswith("garsub_pp_"):
        state_key = f"pp_click_{user_id}"
        user_states[state_key] = user_states.get(state_key, 0) + 1
        if user_states[state_key] > 2:
            bot.send_message(chat_id, "⚠️ CHOOSE ONE AND DON'T PLAY WITH THE BUTTONS")
            return

        parts = data.split("_")
        idx = parts[2]
        car_id = int(parts[3])
        email_used = PAYPAL_EMAIL_1 if idx == "1" else PAYPAL_EMAIL_2

        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, owner, price_paypal FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        conn.close()

        if not car: return
        brand, owner, p_pp = car

        # Sinalpakan ng structural identifier para mahanap ang car_id mamaya sa confirm system [ID: car_id]
        order_id, d, t = create_pending_order(user_id, username, f"CAR: {brand} ({owner}) [ID: {car_id}]", 1, "PAYPAL", f"${p_pp}")
        
        log_txt = (
            f"DATE OF PURCHASE: {d}\n"
            f"TIME OF PURCHASE: {t}\n"
            f"BUYER USERNAME: @{username}\n"
            f"BUYER ID: {user_id}\n"
            f"PRODUCT: 1 Car\n"
            f"PAYMENT METHOD: PAYPAL\n"
            f"PAYMENT AMOUNT: ${p_pp}\n"
            f"PAYPAL EMAIL USED: {email_used}"
        )
        bot.send_message(LOGS_GROUP_ID, log_txt, reply_markup=admin_order_keyboard(order_id))
        bot.send_message(chat_id, "✅ Purchase request pushed to administrators. Please await verification processing.")

    elif data.startswith("garpay_paymaya_"):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, price_paymaya FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        conn.close()

        if not car: return
        brand, p_pm = car

        text = (
            "1 Car(s) — 1 CAR\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"💴 PAY ₱{p_pm:,.0f}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "PAYMAYA INFORMATION\n"
            f"Name:\n{PAYMAYA_NAME}\n"
            f"Number:\n{PAYMAYA_NUM}"
        )
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ I HAVE SENT THE PAYMENT", callback_data=f"garsub_pm_{car_id}"))
        bot.send_message(chat_id, text, reply_markup=markup)

    elif data.startswith("garsub_pm_"):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, owner, price_paymaya FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        conn.close()

        if not car: return
        brand, owner, p_pm = car

        # Sinalpakan din ng identifier [ID: car_id]
        order_id, d, t = create_pending_order(user_id, username, f"CAR: {brand} ({owner}) [ID: {car_id}]", 1, "PAYMAYA", f"₱{p_pm}")

        log_txt = (
            f"DATE OF PURCHASE: {d}\n"
            f"TIME OF PURCHASE: {t}\n"
            f"BUYER USERNAME: @{username}\n"
            f"BUYER ID: {user_id}\n"
            f"PRODUCT: 1 Car\n"
            f"PAYMENT METHOD: PAYMAYA\n"
            f"PAYMENT AMOUNT: ₱{p_pm}"
        )
        bot.send_message(GARAGE_LOGS_GROUP_ID, log_txt, reply_markup=admin_order_keyboard(order_id))
        bot.send_message(chat_id, "✅ Notification sent directly to clearing group log terminal ID -1003957577057.")

    # --- REST OF ORIGINAL HANDLERS FROM HERE ---
    elif data in ["inv_view_reg", "inv_view_vip", "inv_view_garage"]:
        if user_id not in ADMINS: return
        if data == "inv_view_garage":
            conn = sqlite3.connect('tnnr_shop.db')
            cursor = conn.cursor()
            cursor.execute("SELECT car_id, brand, owner, price_stars FROM garage_cars")
            rows = cursor.fetchall()
            conn.close()
            out = "🚘🚘 TNNR GARAGE STOCK 🚘🚘\n\n"
            for r in rows:
                out += f"ID: #{r[0]} | {r[1]} | Owner: {r[2]} | ⭐️ {r[3]}\n"
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅ BACK", callback_data="close_menu"))
            bot.send_message(chat_id, out, reply_markup=markup)
            return
            
        table = "regular_inventory" if data == "inv_view_reg" else "vip_inventory"
        p_name = "REGULAR ACCOUNT" if data == "inv_view_reg" else "VIP ACCOUNT"
        
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute(f"SELECT account_id, account_email FROM {table}")
        rows = cursor.fetchall()
        conn.close()
        
        out = f"📦📦 {p_name} INVENTORY 📦📦\n\n"
        for r in rows:
            out += f"━━━━━━━━━━━━━━━━━━━━━\n{p_name} #{r[0]}\nEmail: {r[1]}\n"
        out += f"━━━━━━━━━━━━━━━━━━━━━\nTotal Stock: {len(rows)}\n━━━━━━━━━━━━━━━━━━━━━"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅ BACK", callback_data="close_menu"))
        bot.send_message(chat_id, out, reply_markup=markup)

    elif data.startswith("buy_regular_") or data.startswith("buy_vip_"):
        parts = data.split("_")
        prod = parts[1]
        qty = int(parts[2])
        
        stock_avail = get_stock_count("regular_inventory" if prod == "regular" else "vip_inventory")
        if stock_avail == 0:
            bot.send_message(chat_id, "❌ OUT OF STOCK\nPlease wait for the next restock.")
            return
        if stock_avail < qty:
            bot.send_message(chat_id, f"❌ NOT ENOUGH STOCK AVAILABLE\n\nAvailable Stock: {stock_avail} Accounts\nPlease choose a lower quantity or wait for restock.")
            return
            
        if prod == "regular":
            stars = qty * 30
            usd = qty * 2
            php = qty * 60
            p_title = "REGULAR ACCOUNTS WITH 20 RANDOM CARS"
            m_title = "REGULAR ACCOUNTS"
        else:
            stars = qty * 200
            usd = qty * 4
            php = qty * 200
            p_title = "ACCOUNTS WITH 12K COINS"
            m_title = "VIP ACCOUNTS"

        summary = (
            f"🛒 {p_title} 🛒\n\n"
            f"Quantity:\n{qty} {m_title}\n\n"
            f"💰 Total Price\n\n"
            f"⭐ Telegram Stars:\n{stars:,} Stars\n\n"
            f"💵 USD:\n${usd:,}\n\n"
            f"💵 PHP:\n₱{php:,.0f}"
        )
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➡ CONTINUE TO PAYMENT METHOD", callback_data=f"checkout_{prod}_{qty}"))
        bot.send_message(chat_id, summary, reply_markup=markup)

    elif data.startswith("checkout_"):
        parts = data.split("_")
        prod = parts[1]
        qty = int(parts[2])
        
        if prod == "regular":
            stars, usd, php = qty*20, qty*1, qty*50
        else:
            stars, usd, php = qty*150, qty*4, qty*130
            
        text = (
            "💳 SELECT PAYMENT METHOD 💳\n\n"
            "Available Payment Methods:\n\n"
            "💵 PayPal\n\n"
            "⭐ Telegram Stars\n\n"
            "💴 PayMaya (Philippines Only)\n\n"
            "----------------------------\n"
            f"TOTAL:\n"
            f"⭐ {stars:,} Stars\n"
            f"💵 ${usd:,} USD\n"
            f"💴 ₱{php:,.0f} PHP"
        )
        bot.send_message(chat_id, text, reply_markup=payment_method_keyboard(prod, qty, True))

    elif data.startswith("cf_plan_") or data.startswith("pw_plan_"):
        prod_type = "coinfarm" if data.startswith("cf_") else "changepw"
        plan = data.split("_")[2]
        
        stars_avail = True
        if plan == "1m":
            p_txt, stars, usd, php = "1 MONTH PLAN", 300 if prod_type == "coinfarm" else 150, 5, 250
        elif plan == "3m":
            p_txt, stars, usd, php = "3 MONTHS PLAN", 900 if prod_type == "coinfarm" else 450, 15, 750
        elif plan == "5m":
            p_txt, stars, usd, php = "5 MONTHS PLAN", 1500 if prod_type == "coinfarm" else 750, 25, 1250
        elif plan == "10m":
            p_txt, stars, usd, php = "10 MONTHS PLAN", 3000 if prod_type == "coinfarm" else 1500, 50, 2500
        elif plan == "lt":
            p_txt, stars, usd, php = "LIFETIME PLAN", 0, 60, 2500
            stars_avail = False
            
        p_name = "DAILY COINFARM SYSTEM" if prod_type == "coinfarm" else "CHANGE EMAIL & PASSWORD BOT"
        text = (
            "💳 SELECT PAYMENT METHOD 💳\n\n"
            f"Product: {p_name}\n"
            f"Plan: {p_txt}\n\n"
            "Available:\n"
            f"{'⭐ Telegram Stars' if stars_avail else ''}\n"
            "💵 PayPal\n"
            "💴 PayMaya\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "TOTAL:\n"
            f"{f'⭐ {stars:,} Stars' if stars_avail else 'No Telegram Stars Available for Lifetime'}\n"
            f"💵 ${usd} USD\n"
            f"💴 ₱{php:,} PHP"
        )
        bot.send_message(chat_id, text, reply_markup=payment_method_keyboard(prod_type, plan, stars_avail))

    elif data.startswith("pay_stars_"):
        parts = data.split("_")
        prod = parts[2]
        val = parts[3]
        
        if prod == "regular":
            qty = int(val)
            stars = qty * 20
            p_full = f"{qty} REGULAR ACCOUNTS"
            header = "REGULAR ACCOUNTS"
        elif prod == "vip":
            qty = int(val)
            stars = qty * 150
            p_full = f"{qty} VIP ACCOUNTS"
            header = "VIP ACCOUNTS"
        elif prod == "coinfarm":
            qty = 1
            p_full = f"DAILY COINFARM {val.upper()} PLAN"
            header = "DAILY COINFARM"
            stars = 300 if val == "1m" else (900 if val == "3m" else (1500 if val == "5m" else 3000))
        else:
            qty = 1
            p_full = f"CHANGE EMAIL & PASSWORD {val.upper()} PLAN"
            header = "CHANGE EMAIL & PASSWORD"
            stars = 150 if val == "1m" else (450 if val == "3m" else (750 if val == "5m" else 1500))

        payload = f"stars_buy:{prod}:{val}:{qty}:{user_id}"
        currency = "XTR"
        prices = [types.LabeledPrice(label=p_full, amount=stars)]

        try:
            bot.send_invoice(
                chat_id=chat_id,
                title=f"💳 Buy {header}",
                description=f"Pay {stars} Stars to have your order delivered automatically. 🚀",
                invoice_payload=payload,
                provider_token="",  
                currency=currency,
                prices=prices,
                start_parameter="tnnr-shop-stars-checkout"
            )
        except Exception as e:
            bot.send_message(chat_id, f"❌ Payment Interface Error: {e}")

    elif data.startswith("pay_paypal_"):
        parts = data.split("_")
        prod = parts[2]
        val = parts[3]
        
        if prod == "regular":
            amt = f"${int(val) * 1}"
            header = f"{val} Car(s) — RANDOM CARS (Example Purchase)"
        elif prod == "vip":
            amt = f"${int(val) * 4}"
            header = f"{val} Account(s) — VIP ACCOUNTS WITH 12K COINS"
        elif prod == "coinfarm":
            header = f"DAILY COINFARM SYSTEM {val.upper()} PLAN"
            amt = "$5" if val == "1m" else ("$15" if val == "3m" else ("$25" if val == "5m" else ("$50" if val == "10m" else "$60")))
        else:
            header = f"CHANGE EMAIL & PASSWORD BOT {val.upper()} PLAN"
            amt = "$5" if val == "1m" else ("$15" if val == "3m" else ("$25" if val == "5m" else ("$50" if val == "10m" else "$60")))

        text = (
            f"{header}\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 PAY {amt}\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"PAYPAL PAYMENT EMAILS\n"
            f"📩 Email 1: {PAYPAL_EMAIL_1}\n"
            f"📩 Email 2: {PAYPAL_EMAIL_2}"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📋 COPY EMAIL #1", callback_data="copy_em1"),
            types.InlineKeyboardButton("📋 COPY EMAIL #2", callback_data="copy_em2")
        )
        markup.add(
            types.InlineKeyboardButton("✅ I PAID TO EMAIL #1", callback_data=f"submit_pp_1_{prod}_{val}"),
            types.InlineKeyboardButton("✅ I PAID TO EMAIL #2", callback_data=f"submit_pp_2_{prod}_{val}")
        )
        markup.add(types.InlineKeyboardButton("⬅ BACK", callback_data="back_to_shop"))
        bot.send_message(chat_id, text, reply_markup=markup)

    elif data.startswith("copy_em"):
        em = PAYPAL_EMAIL_1 if "1" in data else PAYPAL_EMAIL_2
        bot.send_message(chat_id, f"`{em}`", parse_mode="Markdown")

    elif data.startswith("submit_pp_"):
        state_key = f"pp_click_{user_id}"
        user_states[state_key] = user_states.get(state_key, 0) + 1
        if user_states[state_key] > 2:
            bot.send_message(chat_id, "⚠️ CHOOSE ONE AND DON'T PLAY WITH THE BUTTONS")
            return
            
        parts = data.split("_")
        idx = parts[2]
        prod = parts[3]
        val = parts[4]
        email_used = PAYPAL_EMAIL_1 if idx == "1" else PAYPAL_EMAIL_2
        
        if prod == "regular":
            amt, qty, p_full = f"${int(val)*1}", int(val), f"{val} REGULAR CARS"
        elif prod == "vip":
            amt, qty, p_full = f"${int(val)*4}", int(val), f"{val} VIP ACCOUNTS"
        elif prod == "coinfarm":
            qty, p_full = 1, f"DAILY COINFARM SYSTEM {val.upper()} PLAN"
            amt = "$5" if val == "1m" else ("$15" if val == "3m" else ("$25" if val == "5m" else ("$50" if val == "10m" else "$60")))
        else:
            qty, p_full = 1, f"CHANGE EMAIL & PASSWORD BOT {val.upper()} PLAN"
            amt = "$5" if val == "1m" else ("$15" if val == "3m" else ("$25" if val == "5m" else ("$50" if val == "10m" else "$60")))

        order_id, d, t = create_pending_order(user_id, username, p_full, qty, "PAYPAL", amt)
        
        log_txt = (
            f"DATE OF PURCHASE: {d}\n"
            f"TIME OF PURCHASE: {t}\n"
            f"BUYER USERNAME: @{username}\n"
            f"BUYER ID: {user_id}\n"
            f"PRODUCT: {p_full}\n"
            f"PAYMENT METHOD: PAYPAL\n"
            f"PAYMENT AMOUNT: {amt}\n"
            f"PAYPAL EMAIL USED: {email_used}"
        )
        bot.send_message(LOGS_GROUP_ID, log_txt, reply_markup=admin_order_keyboard(order_id))
        bot.send_message(chat_id, "✅ Purchase request pushed to administrators. Please await verification processing.")

    elif data.startswith("pay_pmaya_"):
        parts = data.split("_")
        prod = parts[2]
        val = parts[3]
        
        if prod == "regular":
            amt, qty, p_full = f"₱{int(val)*50:,}", int(val), f"{val} REGULAR CARS"
        elif prod == "vip":
            amt, qty, p_full = f"₱{int(val)*130:,}", int(val), f"{val} VIP ACCOUNTS"
        elif prod == "coinfarm":
            qty, p_full = 1, f"DAILY COINFARM SYSTEM {val.upper()} PLAN"
            amt = "₱250" if val == "1m" else ("₱750" if val == "3m" else ("₱1,250" if val == "5m" else "₱2,500"))
        else:
            qty, p_full = 1, f"CHANGE EMAIL & PASSWORD BOT {val.upper()} PLAN"
            amt = "₱250" if val == "1m" else ("₱750" if val == "3m" else ("₱1,250" if val == "5m" else "₱2,500"))

        text = (
            f"{p_full}\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"💴 PAY {amt}\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"PAYMAYA INFORMATION\n"
            f"Name: {PAYMAYA_NAME}\n"
            f"Number: {PAYMAYA_NUM}"
        )
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ I HAVE SENT THE PAYMENT", callback_data=f"submit_pm_{prod}_{val}"))
        bot.send_message(chat_id, text, reply_markup=markup)

    elif data.startswith("submit_pm_"):
        parts = data.split("_")
        prod = parts[2]
        val = parts[3]
        
        if prod == "regular":
            amt, qty, p_full = f"₱{int(val)*50:,}", int(val), f"{val} REGULAR CARS"
        elif prod == "vip":
            amt, qty, p_full = f"₱{int(val)*130:,}", int(val), f"{val} VIP ACCOUNTS"
        elif prod == "coinfarm":
            qty, p_full = 1, f"DAILY COINFARM SYSTEM {val.upper()} PLAN"
            amt = "₱250" if val == "1m" else ("₱750" if val == "3m" else ("₱1,250" if val == "5m" else "₱2,500"))
        else:
            qty, p_full = 1, f"CHANGE EMAIL & PASSWORD BOT {val.upper()} PLAN"
            amt = "₱250" if val == "1m" else ("₱750" if val == "3m" else ("₱1,250" if val == "5m" else "₱2,500"))

        order_id, d, t = create_pending_order(user_id, username, p_full, qty, "PAYMAYA", amt)
        
        log_txt = (
            f"DATE OF PURCHASE: {d}\n"
            f"TIME OF PURCHASE: {t}\n"
            f"BUYER USERNAME: @{username}\n"
            f"BUYER ID: {user_id}\n"
            f"PRODUCT: {p_full}\n"
            f"PAYMENT METHOD: PAYMAYA\n"
            f"PAYMENT AMOUNT: {amt}"
        )
        bot.send_message(LOGS_GROUP_ID, log_txt, reply_markup=admin_order_keyboard(order_id))
        bot.send_message(chat_id, "✅ Notification sent directly to clearing group log terminal ID -1003957577057.")

    elif data.startswith("admin_confirm_"):
        if user_id not in ADMINS: return
        oid = int(data.split("_")[2])
        
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, product, quantity, payment_method, amount FROM orders WHERE order_id=?", (oid,))
        order = cursor.fetchone()
        
        if not order:
            conn.close()
            return
            
        b_id, b_user, prod_name, qty, pay_meth, amt = order
        
        # Checking if it's a TNNR Garage vehicle order
        if "CAR:" in prod_name.upper():
            # I-update ang order status sa db pipeline
            cursor.execute("UPDATE orders SET status='COMPLETED' WHERE order_id=?", (oid,))
            
            # AUTOMATIC AUTO-DELETE MECHANISM SA STOCK NG KOTSE:
            try:
                # Kukunin ang pinasok na ID sa string profile "[ID: xx]"
                if "[ID:" in prod_name:
                    target_car_id = int(prod_name.split("[ID:")[1].replace("]", "").strip())
                    cursor.execute("DELETE FROM garage_cars WHERE car_id=?", (target_car_id,))
            except Exception as e:
                print(f"Error handling stock clear node: {e}")
                
            conn.commit()
            conn.close()

            # Dynamic parsing values out of structural string "CAR: Porsche 911 (@Maarkryan)"
            clean_brand = prod_name.replace("CAR:", "").split("(")[0].strip()
            clean_owner = "@Maarkryan" if "@Maarkryan" in prod_name else "@JustTnnr"

            deliv_msg = (
                "✅ ORDER CONFIRMED & DELIVERED\n"
                "Product: Cars \n"
                f"🚘 Brand of the cars: {clean_brand}\n"
                f"💀 Owner of the : {clean_owner}\n"
                "Quantity: 1\n"
                f"Payment Used : {pay_meth}\n"
                "Status: ✅ COMPLETED\n"
                "Thank you for your purchase!\n"
                "💯 TRUSTED\n\n"
                "👉 send this screenshot to the Owner Of that Car So he can deliver it to you"
            )
            bot.send_message(b_id, deliv_msg)
            bot.edit_message_text(f"✅ Car Order #{oid} Approved & Stock automatically cleaned out.", chat_id, call.message.message_id)
            return

        if "REGULAR ACCOUNTS" in prod_name.upper() or "VIP ACCOUNTS" in prod_name.upper() or "REGULAR CARS" in prod_name.upper():
            p_type = "regular_inventory" if ("REGULAR" in prod_name.upper() or "CAR" in prod_name.upper()) else "vip_inventory"
            cursor.execute(f"SELECT account_id, account_email FROM {p_type} ORDER BY account_id ASC LIMIT ?", (qty,))
            items = cursor.fetchall()
            
            if len(items) < qty:
                bot.send_message(chat_id, "❌ Verification processing halted: Missing asset depth inside structural internal engine databases.")
                conn.close()
                return
                
            allocated = []
            for item_id, email in items:
                allocated.append(email)
                cursor.execute(f"DELETE FROM {p_type} WHERE account_id=?", (item_id,))
                
            cursor.execute("UPDATE orders SET status='COMPLETED' WHERE order_id=?", (oid,))
            cursor.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (b_id,))
            conn.commit()
            conn.close()
            
            formatted_accs = "\n".join(allocated)
            deliv_msg = (
                "✅ ORDER CONFIRMED & DELIVERED\n"
                f"Product: {'REGULAR CARS' if ('REGULAR' in prod_name.upper() or "CAR" in prod_name.upper()) else 'VIP ACCOUNTS'}\n"
                f"Quantity: {qty}\n"
                f"Account Details:\n{formatted_accs}\n"
                "Status: ✅ COMPLETED\n\n"
                "Thank you for your purchase!\n💯 TRUSTED"
            )
            bot.send_message(b_id, deliv_msg)
            bot.edit_message_text(f"✅ Order #{oid} Approved & Assets Released.", chat_id, call.message.message_id)
            
        elif "DAILY COINFARM" in prod_name.upper():
            cursor.execute("UPDATE orders SET status='COMPLETED' WHERE order_id=?", (oid,))
            conn.commit()
            conn.close()
            
            cf_msg = (
                "✅ ORDER CONFIRMED & DELIVERED\n"
                "Product: DAILY COINFARM SYSTEM\n"
                f"Plan: {prod_name}\n"
                "Account: example@gmail.com\n\n"
                "‼️ Screenshot this and send it to @JustTnnr ‼️\n"
                "🎁 This will be your receipt for your purchase.\n"
                "Status: ✅ COMPLETED\n\n"
                "Thank you for your purchase!\n💯 TRUSTED"
            )
            bot.send_message(b_id, cf_msg)
            bot.edit_message_text(f"✅ Coinfarm Plan #{oid} Activated.", chat_id, call.message.message_id)
            
        else:
            cursor.execute("UPDATE orders SET status='COMPLETED' WHERE order_id=?", (oid,))
            conn.commit()
            conn.close()
            
            cp_msg = (
                "✅ ORDER CONFIRMED & DELIVERED\n"
                "Product: CHANGE EMAIL & PASSWORD BOT\n"
                f"Plan: {prod_name}\n"
                f"BUYER USERNAME: @{b_user}\n"
                f"BUYER ID: {b_id}\n\n"
                "‼️ Screenshot this and send it to @JustTnnr ‼️\n"
                "🎁 This will be your receipt for your purchase.\n"
                "Status: ✅ COMPLETED\n\n"
                "Thank you for your purchase!\n💯 TRUSTED"
            )
            bot.send_message(b_id, cp_msg)
            bot.edit_message_text(f"✅ ChangePassword Token #{oid} Assigned.", chat_id, call.message.message_id)

    elif data.startswith("admin_decline_"):
        if user_id not in ADMINS: return
        oid = int(data.split("_")[2])
        
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM orders WHERE order_id=?", (oid,))
        row = cursor.fetchone()
        if row:
            b_id = row[0]
            cursor.execute("UPDATE orders SET status='DECLINED' WHERE order_id=?", (oid,))
            conn.commit()
            
            dec_msg = (
                "❌ ORDER DECLINED\n"
                "Reason: Payment could not be verified.\n"
                "Please contact support if you believe this is a mistake."
            )
            bot.send_message(b_id, dec_msg)
        conn.close()
        bot.edit_message_text(f"❌ Order #{oid} set to DECLINED status configurations.", chat_id, call.message.message_id)

    elif data == "view_previews":
        render_previews(chat_id)
    elif data == "init_send_preview":
        init_preview_workflow(chat_id, user_id)
    elif data.startswith("rev_prod_"):
        selected_p = data.split("_")[2]
        mapping = {"reg": "REGULAR CARS", "vip": "VIP ACCOUNTS", "cf": "DAILY COINFARM SYSTEM", "pw": "CHANGE EMAIL & PASSWORD BOT"}
        user_states[f"rev_prod_{user_id}"] = mapping.get(selected_p, "UNKNOWN")
        
        p_sel = user_states.get(f"rev_prod_{user_id}", "None")
        p_rat = user_states.get(f"rev_rating_{user_id}", "10/10")
        p_msg = user_states.get(f"rev_msg_{user_id}", "N/A")
        has_img = "Uploaded" if user_states.get(f"rev_photo_{user_id}") else "Skipped"
        
        summary = (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 PRODUCT: {p_sel}\n"
            f"⭐ RATING: {p_rat}\n"
            f"📝 REVIEW: {p_msg}\n"
            f"📷 SCREENSHOT: {has_img}\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ CONFIRM REVIEW", callback_data="rev_finalize_submit"),
            types.InlineKeyboardButton("❌ CANCEL", callback_data="back_to_shop")
        )
        bot.send_message(chat_id, summary, reply_markup=markup)

    elif data == "rev_finalize_submit":
        p_sel = user_states.get(f"rev_prod_{user_id}", "GENERAL")
        p_rat = user_states.get(f"rev_rating_{user_id}", "10/10")
        p_msg = user_states.get(f"rev_msg_{user_id}", "No content.")
        p_file = user_states.get(f"rev_photo_{user_id}", "")
        
        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute('''
            INSERT INTO reviews (user_id, username, product, rating, review_message, screenshot_path, date, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, p_sel, p_rat, p_msg, p_file, now.strftime("%m/%d/%Y"), now.strftime("%I:%M %p")))
        cursor.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        
        for k in [f"rev_prod_{user_id}", f"rev_rating_{user_id}", f"rev_msg_{user_id}", f"rev_photo_{user_id}", f"step_{user_id}"]:
            user_states.pop(k, None)
            
        bot.send_message(chat_id, "✅ Review verified and committed into internal index pipeline successfully.")


# =======================================================================
# 🌟 TUNAY NA TELEGRAM STARS VALIDATION & DELIVERY SYSTEMS
# =======================================================================
@bot.pre_checkout_query_handler(func=lambda query: True)
def validate_stars_stock(pre_checkout_query):
    payload = pre_checkout_query.invoice_payload
    
    if payload.startswith("carstars:"):
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        return
        
    if not payload.startswith("stars_buy:"):
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Invalid request.")
        return

    parts = payload.split(":")
    prod = parts[1]
    qty = int(parts[3])

    if prod in ["regular", "vip"]:
        table = "regular_inventory" if prod == "regular" else "vip_inventory"
        stock = get_stock_count(table)
        if stock < qty:
            bot.answer_pre_checkout_query(
                pre_checkout_query.id, 
                ok=False, 
                error_message=f"❌ Out of Stock! Paumanhin bro, kulang ang stock sa system natin. Available: {stock}"
            )
            return
            
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=['successful_payment'])
def handle_stars_success_payment(message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    
    # --- AUTOMATIC TELEGRAM STARS CAR PROCESSING DELIVERY ---
    if payload.startswith("carstars:"):
        parts = payload.split(":")
        car_id = int(parts[1])
        buyer_id = int(parts[2])
        buyer_uname = message.from_user.username or "Anonymous"

        conn = sqlite3.connect('tnnr_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT brand, owner FROM garage_cars WHERE car_id=?", (car_id,))
        car = cursor.fetchone()
        
        # AUTOMATIC CAR STOCKS DELETE KAPAG STARS ANG PINANG-BAYAD:
        if car:
            cursor.execute("DELETE FROM garage_cars WHERE car_id=?", (car_id,))
        conn.commit()
        conn.close()

        brand = car[0] if car else "Unknown Car"
        owner = car[1] if car else "@JustTnnr"

        now = datetime.now()
        d_str = now.strftime('%m/%d/%Y')
        t_str = now.strftime('%I:%M %p')

        log_channel_text = (
            f"DATE OF PURCHASE: {d_str}\n"
            f"TIME OF PURCHASE: {t_str}\n"
            f"BUYER USERNAME: @{buyer_uname}\n"
            f"BUYER ID: {buyer_id}\n"
            f"PRODUCT: 1 Car\n"
            f"PAYMENT METHOD: {payment_info.total_amount} TELEGRAM STARS"
        )
        bot.send_message(STARS_CHANNEL_ID, log_channel_text)

        order_id, d, t = create_pending_order(buyer_id, buyer_uname, f"CAR: {brand} ({owner})", 1, "TELEGRAM STARS", f"⭐️ {payment_info.total_amount}")
        
        # Pushes log inline dashboard buttons directly for administrative verification
        bot.send_message(LOGS_GROUP_ID, log_channel_text, reply_markup=admin_order_keyboard(order_id))

        deliv_msg = (
            "✅ ORDER CONFIRMED & DELIVERED\n"
            "Product: Cars \n"
            f"🚘 Brand of the cars: {brand}\n"
            f"💀 Owner of the : {owner}\n"
            "Quantity: 1\n"
            "Payment Used : Telegram Stars\n"
            "Status: ✅ COMPLETED\n"
            "Thank you for your purchase!\n"
            "💯 TRUSTED\n\n"
            "👉 send this screenshot to the Owner Of that Car So he can deliver it to you"
        )
        bot.send_message(buyer_id, deliv_msg)
        return

    if not payload.startswith("stars_buy:"):
        return

    parts = payload.split(":")
    prod = parts[1]
    val = parts[2]
    qty = int(parts[3])
    buyer_id = int(parts[4])
    buyer_uname = message.from_user.username or "Anonymous"

    now = datetime.now()
    d_str = now.strftime('%m/%d/%Y')
    t_str = now.strftime('%I:%M %p')

    log_channel_text = (
        f"DATE OF PURCHASE: {d_str}\n"
        f"TIME OF PURCHASE: {t_str}\n"
        f"BUYER USERNAME: @{buyer_uname}\n"
        f"BUYER ID: {buyer_id}\n"
        f"PRODUCT: {qty}x {prod.upper()} ({val})\n"
        f"PAYMENT METHOD: {payment_info.total_amount} TELEGRAM STARS\n"
        f"STATUS: ✅ DELIVERED"
    )
    bot.send_message(STARS_CHANNEL_ID, log_channel_text)

    if prod in ["regular", "vip"]:
        p_name = "REGULAR CARS" if prod == "regular" else "VIP ACCOUNTS"
        res = process_auto_delivery(buyer_id, buyer_uname, p_name, qty, "TELEGRAM STARS", f"⭐ {payment_info.total_amount}")
        
        if res:
            formatted_accs = "\n".join(res)
            deliv_msg = (
                "✅ ORDER CONFIRMED & DELIVERED\n"
                f"Product: {p_name}\n"
                f"Quantity: {qty}\n"
                f"Account Details:\n{formatted_accs}\n"
                "Status: ✅ COMPLETED\n\n"
                "Thank you for your purchase!\n💯 TRUSTED"
            )
            bot.send_message(buyer_id, deliv_msg)
        else:
            bot.send_message(buyer_id, "❌ Auto allocation crashed but Stars received. Please send logs to admin support.")
            
    else:
        p_name = "DAILY COINFARM" if prod == "coinfarm" else "CHANGE EMAIL & PASSWORD"
        create_pending_order(buyer_id, buyer_uname, f"{p_name} {val.upper()}", 1, "TELEGRAM STARS", f"⭐ {payment_info.total_amount}")
        
        cf_msg = (
            "✅ ORDER CONFIRMED\n"
            f"Product: {p_name}\n"
            f"Plan: {val.upper()} PLAN\n\n"
            "‼️ Screenshot this and send it to @JustTnnr ‼️\n"
            "🎁 Your system activation token is being built.\n"
            "Status: 🟡 PENDING ADMIN SETUP\n\n"
            "Thank you for your purchase!\n💯 TRUSTED"
        )
        bot.send_message(buyer_id, cf_msg)

    bot.send_message(LOGS_GROUP_ID, f"🔔 **Stars Audit Log:** User @{buyer_uname} paid {payment_info.total_amount} Stars for {prod.upper()} package configurations.")

# ---------------------------------------------------------------------------
# 7. MULTI-STEP SUBMISSION FLOW HANDLERS (REVIEWS LOGIC ENGINE)
# ---------------------------------------------------------------------------
def init_preview_workflow(chat_id, user_id):
    user_states[f"step_{user_id}"] = "WAITING_FOR_PHOTO"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("⏭ SKIP", callback_data="skip_photo_step"), types.InlineKeyboardButton("⬅ BACK", callback_data="back_to_shop"))
    bot.send_message(chat_id, "📷 Step 1: Upload Screenshot (Optional)\nYou may skip this step if you do not want to upload a screenshot.", reply_markup=markup)

@bot.message_handler(func=lambda msg: user_states.get(f"step_{msg.from_user.id}") in ["WAITING_FOR_PHOTO", "WAITING_FOR_MSG", "WAITING_FOR_RATING"], content_types=['photo', 'text'])
def processing_review_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(f"step_{user_id}")
    
    if state == "WAITING_FOR_PHOTO":
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            local_path = f"rev_snap_{user_id}_{datetime.now().strftime('%s')}.jpg"
            with open(local_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            user_states[f"rev_photo_{user_id}"] = local_path
            advance_to_review_msg(message.chat.id, user_id)
        else:
            bot.reply_to(message, "Please send an image attachment file or click the ⏭ SKIP parameter.")

    elif state == "WAITING_FOR_MSG":
        if message.content_type == 'text':
            user_states[f"rev_msg_{user_id}"] = message.text
            user_states[f"step_{user_id}"] = "WAITING_FOR_RATING"
            bot.send_message(message.chat.id, "⭐ Step 3: Enter Your Rating\n\nExample fields: 10/10, 9/10, 5/5")
        else:
            bot.reply_to(message, "Provide string text values for standard summary fields description.")

    elif state == "WAITING_FOR_RATING":
        if message.content_type == 'text':
            user_states[f"rev_rating_{user_id}"] = message.text
            user_states[f"step_{user_id}"] = "WAITING_FOR_PROD_PICK"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📦 REGULAR CARS", callback_data="rev_prod_reg"),
                types.InlineKeyboardButton("🎁 VIP ACCOUNTS", callback_data="rev_prod_vip"),
                types.InlineKeyboardButton("🪙 DAILY COINFARM SYSTEM", callback_data="rev_prod_cf"),
                types.InlineKeyboardButton("📧 CHANGE EMAIL & PASSWORD BOT", callback_data="rev_prod_pw")
            )
            bot.send_message(message.chat.id, "📦 Step 4: Select Purchased Product Category Model", reply_markup=markup)

def advance_to_review_msg(chat_id, user_id):
    user_states[f"step_{user_id}"] = "WAITING_FOR_MSG"
    bot.send_message(chat_id, "📝 Step 2: Enter Your Review Message\n\nExample:\nFast delivery bro. Trusted seller. Will buy again.")

# ---------------------------------------------------------------------------
# 8. RENDER EXTENSION FUNCTIONS FOR TABULAR/LIST VIEWS
# ---------------------------------------------------------------------------
def render_previews(chat_id):
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT date, username, user_id, product, rating, review_message, screenshot_path FROM reviews ORDER BY review_id DESC LIMIT 10")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    
    if not rows:
        bot.send_message(chat_id, "No customer structural previews indexed inside system nodes.")
        return
        
    for r in rows:
        uname = f"@{r[1]}" if r[1] else "Anonymous"
        text = (
            f"📅 DATE OF PURCHASE: {r[0]}\n"
            f"👤 BUYER USERNAME: {uname}\n"
            f"🆔 BUYER ID: {r[2]}\n"
            f"📦 PURCHASED PRODUCT: {r[3]}\n"
            f"⭐ CUSTOMER RATING: {r[4]}\n"
            "💯 TRUSTED\n"
            f"📝 CUSTOMER MESSAGE: {r[5]}"
        )
        if r[6] and os.path.exists(r[6]):
            with open(r[6], 'rb') as f:
                bot.send_photo(chat_id, f, caption=text)
        else:
            bot.send_message(chat_id, text)

def render_my_orders(chat_id, user_id):
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT order_id, date, time, product, status FROM orders WHERE user_id=? ORDER BY order_id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(chat_id, "📦 No active historical order tickets registered against profile ID.")
        return
        
    out = ""
    for r in rows:
        stat_ico = "🟡" if r[4] == "PENDING" else ("🟢" if r[4] == "COMPLETED" else "🔴")
        out += (
            f"📦 ORDER ID: #{r[0]}\n"
            f"📅 DATE: {r[1]}\n"
            f"🕐 TIME: {r[2]}\n"
            f"📦 PRODUCT: {r[3]}\n"
            f"📊 STATUS: {stat_ico} {r[4]}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
        )
    bot.send_message(chat_id, out)

def render_purchase_history(chat_id, user_id):
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date, time, product, payment_method, amount, status FROM orders WHERE user_id=? AND status='COMPLETED' ORDER BY order_id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(chat_id, "📜 Historical transaction registry blank.")
        return
        
    out = ""
    for r in rows:
        out += (
            f"📅 DATE: {r[0]}\n"
            f"🕐 TIME: {r[1]}\n"
            f"📦 PRODUCT: {r[2]}\n"
            f"💳 PAYMENT METHOD: {r[3]}\n"
            f"💰 PAYMENT: {r[4]}\n"
            f"📊 STATUS: COMPLETED\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
        )
    bot.send_message(chat_id, out)

# ---------------------------------------------------------------------------
# 9. ADMIN ONLY MANAGEMENT RESTOCK SUBSYSTEM COMMANDS
# ---------------------------------------------------------------------------
@bot.message_handler(commands=['restock_regular', 'restock_vip'])
def restock_routing_entry(message):
    if message.from_user.id not in ADMINS: 
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Syntax Error!\n\nUse this format exactly:\n`/restock_regular 3` or `/restock_vip 3`", parse_mode="Markdown")
        return
        
    try:
        qty = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ Invalid Quantity! Please provide a valid number. Example: `/restock_regular 5`", parse_mode="Markdown")
        return

    command_clean = parts[0].lower().split('@')[0]
    p_type = "REGULAR" if "regular" in command_clean else "VIP"
    
    msg_prompt = bot.reply_to(
        message, 
        f"📋 *Admin Mode: Restocking {p_type} Accounts*\n\n"
        f"Please reply to this message by pasting exactly **{qty}** lines of account information.\n"
        f"Format: `email:password` (one account per line).",
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(msg_prompt, process_restock_payload, p_type, qty)

def process_restock_payload(message, p_type, target_qty):
    if message.text and message.text.startswith('/'):
        bot.reply_to(message, "❌ Restock cancelled. New command detected.")
        return

    lines = [line.strip() for line in message.text.split('\n') if line.strip()]
    table = "regular_inventory" if p_type == "REGULAR" else "vip_inventory"
    
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    
    now = datetime.now()
    d_str = now.strftime("%m/%d/%Y")
    t_str = now.strftime("%I:%M %p")
    
    count = 0
    for line in lines:
        cursor.execute(f"INSERT INTO {table} (account_email, date_added, time_added) VALUES (?, ?, ?)", (line, d_str, t_str))
        count += 1
        
    cursor.execute("INSERT OR REPLACE INTO stock_metadata (product_type, last_restock_date, last_restock_time) VALUES (?, ?, ?)", (p_type, d_str, t_str))
    
    conn.commit()
    conn.close()
    
    bot.reply_to(
        message, 
        f"✅ *DB Engine Sync Complete!*\n\n"
        f"📦 *Product:* {p_type} Accounts\n"
        f"📥 *Stored:* {count} records successfully to database.\n"
        f"📆 *Date:* {d_str} | {t_str}",
        parse_mode="Markdown"
    )

# --- DYNAMIC ADMIN COMMAND FOR ADDING CARS TO TNNR GARAGE ---
@bot.message_handler(commands=['addcar'])
def init_add_car_command(message):
    if message.from_user.id not in ADMINS: return
    msg = bot.reply_to(message, "🏎️ **[Admin Mode]** Please send the **Car Brand** (Example: Porsche 911):")
    bot.register_next_step_handler(msg, process_car_brand)

def process_car_brand(message):
    user_id = message.from_user.id
    user_states[f"addcar_brand_{user_id}"] = message.text
    msg = bot.reply_to(message, "👑 Who's the' **Owner of the car**? (Pick one: `@Maarkryan` o `@JustTnnr`):")
    bot.register_next_step_handler(msg, process_car_owner)

def process_car_owner(message):
    user_id = message.from_user.id
    owner = message.text.strip()
    if owner not in ["@Maarkryan", "@JustTnnr"]:
        bot.reply_to(message, "❌ Invalid Owner. Dapat `@Maarkryan` o `@JustTnnr` lang. Try again bro`/addcar` command.")
        return
    user_states[f"addcar_owner_{user_id}"] = owner
    msg = bot.reply_to(message, "💰 Put the prize for **Telegram Stars** (Number only, ex: 350):")
    bot.register_next_step_handler(msg, process_car_stars)

def process_car_stars(message):
    user_id = message.from_user.id
    try:
        stars = int(message.text.strip())
    except ValueError:
        bot.reply_to(message, "❌ Number only, bro. Try again bro `/addcar`.")
        return
    user_states[f"addcar_stars_{user_id}"] = stars
    msg = bot.reply_to(message, "💵 Put The Prize For  **PayPal USD** (Number only, ex: 7):")
    bot.register_next_step_handler(msg, process_car_paypal)

def process_car_paypal(message):
    user_id = message.from_user.id
    try:
        paypal = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "❌ Invalid number. Try again bro `/addcar`.")
        return
    user_states[f"addcar_paypal_{user_id}"] = paypal
    
    # Kung si @Maarkryan ang owner, hihingi din tayo ng PayMaya price
    if user_states[f"addcar_owner_{user_id}"] == "@Maarkryan":
        msg = bot.reply_to(message, "💴 Ilagay ang presyo sa **PayMaya PHP** (Numero lang, ex: 430):")
        bot.register_next_step_handler(msg, process_car_paymaya)
    else:
        user_states[f"addcar_paymaya_{user_id}"] = 0.0
        prompt_for_photo(message, user_id)

def process_car_paymaya(message):
    user_id = message.from_user.id
    try:
        paymaya = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "❌ Invalid number. Ulitin ang `/addcar`.")
        return
    user_states[f"addcar_paymaya_{user_id}"] = paymaya
    prompt_for_photo(message, user_id)

def prompt_for_photo(message, user_id):
    msg = bot.send_message(message.chat.id, "📸 Last you need to send a picture of the car, **send ang LARAWAN/PICTURE** of the car:")
    bot.register_next_step_handler(msg, process_car_photo)

def process_car_photo(message):
    user_id = message.from_user.id
    if message.content_type != 'photo':
        bot.reply_to(message, "❌ You need to send a picture, bro. Cancelled. Try again using `/addcar`.")
        return
        
    photo_file_id = message.photo[-1].file_id
    brand = user_states.get(f"addcar_brand_{user_id}")
    owner = user_states.get(f"addcar_owner_{user_id}")
    stars = user_states.get(f"addcar_stars_{user_id}")
    paypal = user_states.get(f"addcar_paypal_{user_id}")
    paymaya = user_states.get(f"addcar_paymaya_{user_id}", 0.0)

    now = datetime.now()
    d_str = now.strftime("%m/%d/%Y")
    t_str = now.strftime("%I:%M %p")

    # Isasalpak na natin ang bagong kotse sa database pipeline
    conn = sqlite3.connect('tnnr_shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO garage_cars (brand, owner, price_stars, price_paypal, price_paymaya, photo_file_id, date_added, time_added)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (brand, owner, stars, paypal, paymaya, photo_file_id, d_str, t_str))
    cursor.execute("INSERT OR REPLACE INTO stock_metadata (product_type, last_restock_date, last_restock_time) VALUES ('GARAGE', ?, ?)", (d_str, t_str))
    conn.commit()
    conn.close()

    # Clear na natin ang temporary state keys
    for k in [f"addcar_brand_{user_id}", f"addcar_owner_{user_id}", f"addcar_stars_{user_id}", f"addcar_paypal_{user_id}", f"addcar_paymaya_{user_id}"]:
        user_states.pop(k, None)

    bot.reply_to(message, f"✅ **[DB Engine Sync Complete]** Matagumpay na naidagdag ang {brand} sa TNNR Garage mo, bro!")


# ---------------------------------------------------------------------------
# 10. SYSTEM APPLICATION EXECUTION POINT
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    bot.infinity_polling(skip_pending=True)
