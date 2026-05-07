"""
AI Market Media Bot — Demo versiya
Telegram Mini App + Bot
"""

import telebot
from telebot import types
from flask import Flask, request, jsonify, send_from_directory
import json
import os
import logging
import threading

# ─── SOZLAMALAR ───────────────────────────────────────────────────────────────
BOT_TOKEN = "BU_YERGA_BOT_TOKENINGIZNI_YOZING"
ADMIN_FILE = "admin.json"
ORDERS_FILE = "orders.json"
PORT = int(os.environ.get("PORT", 5000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # Railway dan avtomatik
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__, static_folder="static")

# ─── ADMIN ────────────────────────────────────────────────────────────────────

def get_admin_id():
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE) as f:
            return json.load(f).get("admin_id")
    return None

def set_admin_id(uid):
    with open(ADMIN_FILE, "w") as f:
        json.dump({"admin_id": uid}, f)

def is_admin(uid):
    return get_admin_id() == uid

# ─── BUYURTMALAR ──────────────────────────────────────────────────────────────

def save_order(order):
    orders = []
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE) as f:
            orders = json.load(f)
    order["id"] = len(orders) + 1
    order["status"] = "yangi"
    orders.append(order)
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)
    return order["id"]

def get_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE) as f:
            return json.load(f)
    return []

def update_order_status(order_id, status):
    orders = get_orders()
    for o in orders:
        if o["id"] == order_id:
            o["status"] = status
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

# ─── BOT HANDLERLAR ───────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id

    # Birinchi kirgan odam admin bo'ladi
    if get_admin_id() is None:
        set_admin_id(uid)
        bot.send_message(uid,
            "👑 <b>Siz admin sifatida ro'yxatdan o'tdingiz!</b>\n"
            "Buyurtmalar sizga yuboriladi.\n\n"
            "/orders — barcha buyurtmalarni ko'rish"
        )
        return

    name = message.from_user.first_name or "Foydalanuvchi"

    # Mini App tugmasi
    webapp = types.WebAppInfo(url=f"{WEBHOOK_URL}/app?user_id={uid}")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🎬 Video reklama buyurtma qilish", web_app=webapp))

    bot.send_message(
        uid,
        f"👋 <b>Salom, {name}!</b>\n\n"
        "🎬 <b>AI Market Media</b> — marketpleys sotuvchilari uchun\n"
        "AI yordamida professional video reklama xizmati.\n\n"
        "✅ Studiyasiz\n"
        "✅ Modelsiz\n"
        "✅ Montajchisiz\n\n"
        "Tugmani bosib buyurtma bering! 👇",
        reply_markup=keyboard
    )


@bot.message_handler(commands=["orders"])
def cmd_orders(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Siz admin emassiz.")
        return

    orders = get_orders()
    if not orders:
        bot.reply_to(message, "📭 Hali buyurtmalar yo'q.")
        return

    for o in orders[-10:]:  # Oxirgi 10 ta
        status_emoji = {"yangi": "🆕", "jarayonda": "⏳", "tayyor": "✅", "bekor": "❌"}.get(o["status"], "📦")
        text = (
            f"{status_emoji} <b>Buyurtma #{o['id']}</b>\n"
            f"👤 Foydalanuvchi: {o.get('user_name', 'Noma\'lum')} (ID: {o.get('user_id')})\n"
            f"🤖 Model: {o.get('model', '-')}\n"
            f"📦 Paket: {o.get('package', '-')}\n"
            f"📝 Matn: {o.get('text', '-')}\n"
            f"📊 Holat: {o['status']}\n"
        )
        keyboard = types.InlineKeyboardMarkup(row_width=3)
        keyboard.add(
            types.InlineKeyboardButton("⏳ Jarayonda", callback_data=f"status_{o['id']}_jarayonda"),
            types.InlineKeyboardButton("✅ Tayyor", callback_data=f"status_{o['id']}_tayyor"),
            types.InlineKeyboardButton("❌ Bekor", callback_data=f"status_{o['id']}_bekor"),
        )
        if o.get("photo_id"):
            bot.send_photo(message.chat.id, o["photo_id"], caption=text, reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data.startswith("status_"))
def handle_status(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Siz admin emassiz.")
        return

    parts = call.data.split("_")
    order_id = int(parts[1])
    new_status = parts[2]
    update_order_status(order_id, new_status)

    # Foydalanuvchiga xabar yuborish
    orders = get_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if order and order.get("user_id"):
        status_text = {
            "jarayonda": "⏳ Buyurtmangiz <b>jarayonda</b>! Tez orada tayyor bo'ladi.",
            "tayyor": "✅ Buyurtmangiz <b>tayyor</b>! Video tez orada yuboriladi.",
            "bekor": "❌ Buyurtmangiz <b>bekor qilindi</b>. Muammo bo'lsa admin bilan bog'laning.",
        }.get(new_status, "")
        if status_text:
            try:
                bot.send_message(order["user_id"], f"📦 <b>Buyurtma #{order_id}</b>\n{status_text}")
            except Exception:
                pass

    bot.answer_callback_query(call.id, f"✅ Status yangilandi: {new_status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)


# ─── WEB API ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return "AI Market Media Bot ishlayapti! ✅"


@app.route("/app")
def mini_app():
    return send_from_directory("static", "index.html")


@app.route("/api/order", methods=["POST"])
def create_order():
    try:
        data = request.json
        user_id = int(data.get("user_id", 0))
        user_name = data.get("user_name", "Noma'lum")
        model = data.get("model", "-")
        package = data.get("package", "-")
        text = data.get("text", "-")
        photo_id = data.get("photo_id", None)

        order = {
            "user_id": user_id,
            "user_name": user_name,
            "model": model,
            "package": package,
            "text": text,
            "photo_id": photo_id,
        }
        order_id = save_order(order)

        # Adminga xabar
        admin_id = get_admin_id()
        if admin_id:
            status_emoji = "🆕"
            msg = (
                f"{status_emoji} <b>Yangi buyurtma #{order_id}!</b>\n\n"
                f"👤 Foydalanuvchi: {user_name} (ID: {user_id})\n"
                f"🤖 Model: {model}\n"
                f"📦 Paket: {package}\n"
                f"📝 Matn: {text}\n"
            )
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            keyboard.add(
                types.InlineKeyboardButton("⏳ Jarayonda", callback_data=f"status_{order_id}_jarayonda"),
                types.InlineKeyboardButton("✅ Tayyor", callback_data=f"status_{order_id}_tayyor"),
                types.InlineKeyboardButton("❌ Bekor", callback_data=f"status_{order_id}_bekor"),
            )
            try:
                bot.send_message(admin_id, msg, reply_markup=keyboard)
            except Exception as e:
                log.error(f"Admin xabar yuborishda xato: {e}")

        # Foydalanuvchiga tasdiqlash
        try:
            bot.send_message(
                user_id,
                f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n\n"
                f"🤖 Model: {model}\n"
                f"📦 Paket: {package}\n"
                f"📝 Matn: {text}\n\n"
                "⏳ Tez orada admin ko'rib chiqadi va siz bilan bog'lanadi!"
            )
        except Exception as e:
            log.error(f"Foydalanuvchiga xabar yuborishda xato: {e}")

        return jsonify({"success": True, "order_id": order_id})
    except Exception as e:
        log.error(f"Buyurtma yaratishda xato: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


# ─── ISHGA TUSHIRISH ──────────────────────────────────────────────────────────

def start_bot():
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}")
        log.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")
    else:
        # Local test uchun polling
        threading.Thread(target=bot.infinity_polling, daemon=True).start()

if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=PORT)
