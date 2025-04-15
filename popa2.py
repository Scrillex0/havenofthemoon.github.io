from flask import Flask, render_template, jsonify, request
import sqlite3
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
import asyncio
import threading
from typing import Optional
from datetime import datetime

# ===== НАСТРОЙКИ =====
TOKEN = "7789596063:AAFuaIEVgj60J4VNHOnvn2xKIDGWcdUrfu0"
ADMIN_IDS = {6367910366, 930359492}
GROUP_ID = -1002606287455
DB_FILE = "popa.sqlite"
HOST = '0.0.0.0'
PORT = 5000

# ===== ИНИЦИАЛИЗАЦИЯ =====
app = Flask(__name__)
bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        username TEXT,
                        candies INTEGER DEFAULT 0
                      )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS purchases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        item_id INTEGER,
                        item_name TEXT,
                        item_price INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                      )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS items (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        description TEXT,
                        price INTEGER
                      )''')
    
    # Добавляем тестовые товары если таблица пуста
    cursor.execute("SELECT COUNT(*) FROM items")
    if cursor.fetchone()[0] == 0:
        default_items = [
            (1, 'Товар 1', 'Описание товара 1', 50),
            (2, 'Товар 2', 'Описание товара 2', 100),
            (3, 'Товар 3', 'Описание товара 3', 150)
        ]
        cursor.executemany("INSERT INTO items VALUES (?, ?, ?, ?)", default_items)
    
    conn.commit()
    conn.close()

init_db()

# ===== ОСНОВНЫЕ ФУНКЦИИ =====
def get_balance(user_id: str) -> Optional[int]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT candies FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        return None
    finally:
        conn.close()

def update_balance(user_id: str, username: Optional[str], amount: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION")
        
        cursor.execute("SELECT candies FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            if username:
                cursor.execute(
                    "INSERT INTO users (user_id, username, candies) VALUES (?, ?, ?)",
                    (user_id, username, max(amount, 0)))
            else:
                return False
        
        cursor.execute(
            "UPDATE users SET candies = candies + ? WHERE user_id = ?",
            (amount, user_id))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка обновления баланса: {e}")
        return False
    finally:
        conn.close()

def add_purchase(user_id: str, item_id: int, item_name: str, item_price: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO purchases (user_id, item_id, item_name, item_price)
            VALUES (?, ?, ?, ?)
        """, (user_id, item_id, item_name, item_price))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка записи покупки: {e}")
    finally:
        conn.close()

def get_items() -> list:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, description, price FROM items")
        return [{
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'price': row[3]
        } for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return []
    finally:
        conn.close()

def get_user_id_by_username(username: str) -> Optional[str]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка поиска пользователя: {e}")
        return None
    finally:
        conn.close()

async def get_username(user_id: str) -> str:
    try:
        user = await bot.get_chat(user_id)
        return f"@{user.username}" if user.username else f"ID:{user_id}"
    except Exception as e:
        logger.error(f"Ошибка получения username: {e}")
        return f"ID:{user_id}"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def safe_send_message(chat_id: int, text: str):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML"
        )
        logger.info(f"Сообщение отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения в {chat_id}: {e}")
        return False

# ===== TELEGRAM HANDLERS =====
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or user_id
    update_balance(user_id, username, 0)
    await message.answer(
        "Добро пожаловать в магазин!\n\n"
        "Команды:\n"
        "/balance - ваш баланс\n"
        "/my_id - получить ID для сайта"
    )

@dp.message(Command("balance"))
async def balance_command(message: Message):
    user_id = str(message.from_user.id)
    balance = get_balance(user_id)
    if balance is None:
        await message.answer("Ваш аккаунт не найден. Используйте /start")
    else:
        await message.answer(f"Ваш баланс: {balance} конфет")

@dp.message(Command("my_id"))
async def get_my_id(message: Message):
    await message.answer(f"Ваш ID для сайта: `{message.from_user.id}`", parse_mode="Markdown")

@dp.message(Command("add_candies"))
async def add_candies_command(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ У вас нет прав на эту команду")
    
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("ℹ️ Использование: /add_candies @username количество")
    
    try:
        target_username = args[1].lstrip('@')
        amount = int(args[2])
        
        target_id = get_user_id_by_username(target_username)
        if not target_id:
            return await message.answer("❌ Пользователь не найден")
        
        if not update_balance(target_id, target_username, amount):
            return await message.answer("❌ Ошибка обновления баланса")
        
        await message.answer(f"✅ Начислено {amount} конфет пользователю @{target_username}")
        
        await safe_send_message(
            target_id,
            f"🎉 Вам начислено {amount} конфет!\n"
            f"📊 Новый баланс: {get_balance(target_id)}"
        )
            
    except ValueError:
        await message.answer("❌ Неверное количество. Укажите число")
    except Exception as e:
        logger.error(f"Ошибка в add_candies: {e}")
        await message.answer("❌ Произошла ошибка")

@dp.message(Command("remove_candies"))
async def remove_candies_command(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ У вас нет прав на эту команду")
    
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("ℹ️ Использование: /remove_candies @username количество")
    
    try:
        target_username = args[1].lstrip('@')
        amount = int(args[2])
        
        target_id = get_user_id_by_username(target_username)
        if not target_id:
            return await message.answer("❌ Пользователь не найден")
        
        current_balance = get_balance(target_id)
        if current_balance is None or current_balance < amount:
            return await message.answer(f"❌ Недостаточно конфет. Баланс: {current_balance or 0}")
        
        if not update_balance(target_id, None, -amount):
            return await message.answer("❌ Ошибка обновления баланса")
        
        await message.answer(f"✅ Списано {amount} конфет у @{target_username}")
        
        await safe_send_message(
            target_id,
            f"⚠️ У вас списано {amount} конфет\n"
            f"📊 Новый баланс: {current_balance - amount}"
        )
            
    except ValueError:
        await message.answer("❌ Неверное количество. Укажите число")
    except Exception as e:
        logger.error(f"Ошибка в remove_candies: {e}")
        await message.answer("❌ Произошла ошибка")

@dp.message(Command("admin_check"))
async def admin_check_command(message: Message):
    if is_admin(message.from_user.id):
        await message.answer("✅ Вы администратор!")
    else:
        await message.answer("❌ У вас нет прав администратора")

@dp.message(Command("purchases_list"))
async def purchases_list_command(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Только для администраторов")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT p.user_id, p.item_name, p.item_price, p.timestamp, u.username 
            FROM purchases p
            LEFT JOIN users u ON p.user_id = u.user_id
            ORDER BY p.timestamp DESC
            LIMIT 20
        """)
        purchases = cursor.fetchall()
        
        if not purchases:
            return await message.answer("📭 Список покупок пуст")
        
        response = ["📋 Последние 20 покупок:", ""]
        for purchase in purchases:
            user_id, item_name, item_price, timestamp, username = purchase
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").strftime("%d.%m %H:%M")
            user = username or f"ID:{user_id}"
            response.append(f"🛒 {user} → {item_name} ({item_price}🍬) [{dt}]")
        
        await message.answer("\n".join(response))
        
    except Exception as e:
        logger.error(f"Ошибка получения списка покупок: {e}")
        await message.answer("❌ Ошибка при получении списка покупок")
    finally:
        conn.close()

# ===== WEB API =====
@app.route('/')
def index():
    return render_template('index.html', items=get_items())

@app.route('/get_balance/<user_id>')
def api_get_balance(user_id):
    balance = get_balance(user_id)
    if balance is None:
        return jsonify({"status": "error", "message": "Пользователь не найден"})
    return jsonify({"status": "success", "balance": balance})

@app.route('/buy', methods=['POST'])
def api_buy_item():
    try:
        data = request.json
        user_id = str(data['user_id'])
        item_id = int(data['item_id'])
        
        # Получаем товар из БД
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        item = cursor.fetchone()
        conn.close()
        
        if not item:
            return jsonify({"status": "error", "message": "Товар не найден"}), 400
        
        item_data = {
            'id': item[0],
            'name': item[1],
            'description': item[2],
            'price': item[3]
        }
        
        # Проверяем баланс
        balance = get_balance(user_id)
        if balance is None:
            return jsonify({"status": "error", "message": "Пользователь не найден"}), 404
        
        if balance < item_data['price']:
            return jsonify({
                "status": "error",
                "message": "Недостаточно конфет",
                "required": item_data['price'],
                "current": balance
            }), 400
        
        # Обновляем баланс
        if not update_balance(user_id, None, -item_data['price']):
            return jsonify({"status": "error", "message": "Ошибка обновления баланса"}), 500
        
        # Записываем покупку
        add_purchase(user_id, item_data['id'], item_data['name'], item_data['price'])
        
        # Отправляем уведомление в группу (асинхронно)
        async def send_notification():
            try:
                username = await get_username(user_id)
                message = (
                    f"🛒 <b>Новая покупка!</b>\n"
                    f"├ Пользователь: {username}\n"
                    f"├ Товар: {item_data['name']}\n"
                    f"├ Цена: {item_data['price']}🍬\n"
                    f"└ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                await safe_send_message(GROUP_ID, message)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")
        
        asyncio.run_coroutine_threadsafe(send_notification(), asyncio.get_event_loop())
        
        return jsonify({
            "status": "success",
            "message": "Покупка успешна!",
            "new_balance": balance - item_data['price']
        })
    
    except Exception as e:
        logger.error(f"Ошибка обработки покупки: {e}")
        return jsonify({"status": "error", "message": "Ошибка сервера"}), 500

@app.route('/test_notify')
def test_notify():
    try:
        message = "🔔 Тестовое уведомление от бота"
        asyncio.run_coroutine_threadsafe(
            safe_send_message(GROUP_ID, message),
            asyncio.get_event_loop()
        )
        return jsonify({"status": "success", "message": "Тестовое уведомление отправлено"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== ЗАПУСК =====
async def run_bot():
    await dp.start_polling(bot)

def run_flask():
    app.run(host=HOST, port=PORT)

if __name__ == "__main__":
    # Создаем отдельный поток для Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем бота в основном потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()