import telebot
from telebot import types
from flask import Flask, request, jsonify, send_from_directory
import json
import os
import logging

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
ADMIN_FILE = "admin.json"
ORDERS_FILE = "orders.json"
PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__, static_folder="static")

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

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    if get_admin_id() is None:
        set_admin_id(uid)
        bot.send_message(uid,
            "👑 <b>Siz admin sifatida ro'yxatdan o'tdingiz!</b>\n"
            "/orders — buyurtmalarni ko'rish"
        )
        return
    name = message.from_user.first_name or "Foydalanuvchi"
    webapp = types.WebAppInfo(url=f"{WEBHOOK_URL}/app?user_id={uid}")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🎬 Video reklama buyurtma qilish", web_app=webapp))
    bot.send_message(uid,
        f"👋 <b>Salom, {name}!</b>\n\n"
        "🎬 <b>AI Market Media</b>\n"
        "AI yordamida professional video reklama!\n\n"
        "✅ Studiyasiz | ✅ Modelsiz | ✅ Montajchisiz\n\n"
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
    for o in orders[-10:]:
        status_emoji = {"yangi": "🆕", "jarayonda": "⏳", "tayyor": "✅", "bekor": "❌"}.get(o["status"], "📦")
        text = (
            f"{status_emoji} <b>Buyurtma #{o['id']}</b>\n"
            f"👤 {o.get('user_name', '-')} (ID: {o.get('user_id')})\n"
            f"🤖 {o.get('model', '-')}\n"
            f"📦 {o.get('package', '-')}\n"
            f"📝 {o.get('text', '-')}\n"
        )
        keyboard = types.InlineKeyboardMarkup(row_width=3)
        keyboard.add(
            types.InlineKeyboardButton("⏳", callback_data=f"status_{o['id']}_jarayonda"),
            types.InlineKeyboardButton("✅", callback_data=f"status_{o['id']}_tayyor"),
            types.InlineKeyboardButton("❌", callback_data=f"status_{o['id']}_bekor"),
        )
        bot.send_message(message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda c: c.data.startswith("status_"))
def handle_status(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Admin emassiz.")
        return
    parts = call.data.split("_")
    order_id = int(parts[1])
    new_status = parts[2]
    update_order_status(order_id, new_status)
    orders = get_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if order and order.get("user_id"):
        status_text = {
            "jarayonda": "⏳ Buyurtmangiz jarayonda!",
            "tayyor": "✅ Buyurtmangiz tayyor!",
            "bekor": "❌ Buyurtmangiz bekor qilindi.",
        }.get(new_status, "")
        if status_text:
            try:
                bot.send_message(order["user_id"], f"📦 <b>Buyurtma #{order_id}</b>\n{status_text}")
            except Exception:
                pass
    bot.answer_callback_query(call.id, f"✅ {new_status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

@app.route("/")
def index():
    return "AI Market Media Bot ishlayapti! ✅"

@app.route("/app")
def mini_app():
    return send_from_directory("static", "index.html")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_str = request.data.decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        log.info("Update qabul qilindi")
    except Exception as e:
        log.error(f"Webhook xato: {e}")
    return "OK", 200

@app.route("/set_webhook")
def set_webhook():
    try:
        bot.remove_webhook()
        result = bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        return f"Webhook o'rnatildi: {result}"
    except Exception as e:
        return f"Xato: {e}", 500

@app.route("/api/order", methods=["POST"])
def create_order():
    try:
        data = request.json
        user_id = int(data.get("user_id", 0))
        user_name = data.get("user_name", "Noma'lum")
        model = data.get("model", "-")
        package = data.get("package", "-")
        text = data.get("text", "-")
        order = {"user_id": user_id, "user_name": user_name, "model": model, "package": package, "text": text}
        order_id = save_order(order)
        admin_id = get_admin_id()
        if admin_id:
            msg = (
                f"🆕 <b>Yangi buyurtma #{order_id}!</b>\n\n"
                f"👤 {user_name} (ID: {user_id})\n"
                f"🤖 {model}\n📦 {package}\n📝 {text}\n"
            )
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            keyboard.add(
                types.InlineKeyboardButton("⏳", callback_data=f"status_{order_id}_jarayonda"),
                types.InlineKeyboardButton("✅", callback_data=f"status_{order_id}_tayyor"),
                types.InlineKeyboardButton("❌", callback_data=f"status_{order_id}_bekor"),
            )
            try:
                bot.send_message(admin_id, msg, reply_markup=keyboard)
            except Exception as e:
                log.error(f"Admin: {e}")
        try:
            bot.send_message(user_id,
                f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n\n"
                f"🤖 {model}\n📦 {package}\n📝 {text}\n\n"
                "⏳ Admin tez orada ko'rib chiqadi!"
            )
        except Exception as e:
            log.error(f"User: {e}")
        return jsonify({"success": True, "order_id": order_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
