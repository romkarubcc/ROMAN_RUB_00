# ============================================
# БОТ ДЛЯ АНОНИМНЫХ ЗАПИСКОК В TELEGRAM
# Версия: 2.2 (Полностью исправленная)
# ============================================

import asyncio
import sqlite3
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

# ============================================
# НАСТРОЙКИ БОТА
# ============================================

# ВАШ ТОКЕН БОТА (получите у @BotFather в Telegram)
BOT_TOKEN = "8167791580:AAFzge3YFOXmATUc2CNGji5u9IOQywO2q0Q"  # ← ЗАМЕНИТЕ ЭТО НА СВОЙ ТОКЕН!

# ============================================
# ИНИЦИАЛИЗАЦИЯ БОТА
# ============================================

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================================
# БАЗА ДАННЫХ
# ============================================

def init_database():
    """Инициализация базы данных SQLite"""
    conn = sqlite3.connect('anon_notes.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT NOT NULL,
        last_name TEXT,
        is_active BOOLEAN DEFAULT 1,
        is_searchable BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица записок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        is_anonymous BOOLEAN DEFAULT 1,
        is_read BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users (id),
        FOREIGN KEY (receiver_id) REFERENCES users (id)
    )
    ''')
    
    # Таблица черного списка
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        blocked_user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (blocked_user_id) REFERENCES users (id),
        UNIQUE(user_id, blocked_user_id)
    )
    ''')
    
    conn.commit()
    return conn

# Инициализируем БД
db_conn = init_database()

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_user_by_telegram_id(telegram_id):
    """Получить пользователя по Telegram ID"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    if result:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, result))
    return None

def register_user(telegram_id, username, first_name, last_name=None):
    """Зарегистрировать нового пользователя"""
    cursor = db_conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (telegram_id, username, first_name, last_name))
        db_conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка регистрации: {e}")
        return False

def save_note(sender_id, receiver_id, message, is_anonymous=True):
    """Сохранить записку в БД"""
    cursor = db_conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO notes (sender_id, receiver_id, message, is_anonymous)
            VALUES (?, ?, ?, ?)
        ''', (sender_id, receiver_id, message, 1 if is_anonymous else 0))
        db_conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Ошибка сохранения записки: {e}")
        return None

# ============================================
# СОСТОЯНИЯ (FSM)
# ============================================

class SendNote(StatesGroup):
    waiting_for_username = State()
    waiting_for_message = State()

# ============================================
# КЛАВИАТУРЫ
# ============================================

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💬 Мои записки")],
            [KeyboardButton(text="🔍 Найти по username"), KeyboardButton(text="🎲 Случайный чат")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_cancel_keyboard():
    """Клавиатура отмены"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )

def get_yes_no_keyboard(yes_callback="yes", no_callback="no"):
    """Клавиатура Да/Нет"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=yes_callback),
                InlineKeyboardButton(text="❌ Нет", callback_data=no_callback)
            ]
        ]
    )

# ============================================
# ОСНОВНЫЕ КОМАНДЫ
# ============================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    user = get_user_by_telegram_id(message.from_user.id)
    
    if user:
        # Пользователь уже зарегистрирован
        await message.answer(
            f"👋 С возвращением, {message.from_user.first_name}!\n"
            f"Используйте меню ниже для навигации.",
            reply_markup=get_main_keyboard()
        )
    else:
        # Регистрируем нового пользователя
        success = register_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        if success:
            await message.answer(
                f"✅ Регистрация успешна!\n"
                f"Добро пожаловать, {message.from_user.first_name}!\n\n"
                f"Теперь вы можете отправлять анонимные записки другим пользователям.",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "❌ Ошибка регистрации. Попробуйте еще раз командой /start"
            )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
📚 *Помощь по использованию бота:*

*Основные команды:*
/start - Начать работу с ботом
/help - Показать эту справку

*Как отправить записку:*
1. Нажмите "🔍 Найти по username"
2. Введите username получателя
3. Напишите сообщение

*Все сообщения отправляются анонимно!*
"""
    
    await message.answer(help_text, parse_mode="Markdown")

# ============================================
# ОБРАБОТЧИКИ КНОПОК ГЛАВНОГО МЕНЮ
# ============================================

@dp.message(F.text == "🔍 Найти по username")
async def btn_find_by_username(message: types.Message, state: FSMContext):
    """Кнопка Найти по username"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    await state.set_state(SendNote.waiting_for_username)
    await message.answer(
        "👤 *Введите username пользователя:*\n"
        "(например: @username или просто username)\n\n"
        "Нажмите ❌ Отмена для выхода",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

# ============================================
# ОБРАБОТЧИКИ СОСТОЯНИЙ
# ============================================

@dp.message(SendNote.waiting_for_username)
async def process_username_input(message: types.Message, state: FSMContext):
    """Обработка ввода username"""
    # Если пользователь нажал отмену
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено", reply_markup=get_main_keyboard())
        return
    
    username = message.text.strip().lstrip('@')
    
    if not username:
        await message.answer("❌ Username не может быть пустым. Попробуйте еще раз:")
        return
    
    # Ищем пользователя
    cursor = db_conn.cursor()
    cursor.execute(
        'SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND is_searchable = 1',
        (username,)
    )
    
    receiver_data = cursor.fetchone()
    
    if not receiver_data:
        await message.answer(
            f"❌ Пользователь @{username} не найден.\n"
            f"Возможно:\n"
            f"1. Он не зарегистрирован\n"
            f"2. Он скрыл свой профиль\n"
            f"3. Вы ошиблись в написании\n\n"
            f"Попробуйте другой username:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Получаем данные получателя
    columns = [description[0] for description in cursor.description]
    receiver = dict(zip(columns, receiver_data))
    
    # Проверяем, не заблокировал ли нас пользователь
    sender = get_user_by_telegram_id(message.from_user.id)
    
    cursor.execute(
        'SELECT 1 FROM blacklist WHERE user_id = ? AND blocked_user_id = ?',
        (receiver['id'], sender['id'])
    )
    
    if cursor.fetchone():
        await message.answer(
            "❌ Этот пользователь добавил вас в черный список.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    # Сохраняем данные получателя
    await state.update_data(
        receiver_id=receiver['id'],
        receiver_username=receiver['username'],
        receiver_first_name=receiver['first_name']
    )
    
    # Переходим к вводу сообщения
    await state.set_state(SendNote.waiting_for_message)
    
    await message.answer(
        f"✅ *Пользователь найден!*\n\n"
        f"👤 *Получатель:* {receiver['first_name']}\n"
        f"🔗 *Username:* @{receiver['username']}\n\n"
        f"✏️ *Теперь введите текст записки:*\n"
        f"(максимум 4000 символов)\n\n"
        f"Нажмите ❌ Отмена для выхода",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(SendNote.waiting_for_message)
async def process_message_input(message: types.Message, state: FSMContext):
    """Обработка ввода сообщения"""
    # Если пользователь нажал отмену
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено", reply_markup=get_main_keyboard())
        return
    
    # Проверяем длину сообщения
    if len(message.text) > 4000:
        await message.answer(
            "❌ Сообщение слишком длинное!\n"
            "Максимум 4000 символов.\n"
            "Введите более короткое сообщение:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    if len(message.text.strip()) < 1:
        await message.answer(
            "❌ Сообщение не может быть пустым!\n"
            "Введите текст сообщения:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    receiver_id = data['receiver_id']
    receiver_username = data['receiver_username']
    receiver_first_name = data['receiver_first_name']
    
    # Получаем отправителя
    sender = get_user_by_telegram_id(message.from_user.id)
    
    # Сохраняем записку (всегда анонимно)
    note_id = save_note(sender['id'], receiver_id, message.text, is_anonymous=True)
    
    if not note_id:
        await message.answer(
            "❌ Ошибка при сохранении записки.\n"
            "Попробуйте еще раз.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    # Получаем информацию о получателе для отправки
    cursor = db_conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE id = ?', (receiver_id,))
    receiver_telegram_id = cursor.fetchone()[0]
    
    # Отправляем уведомление получателю
    try:
        await bot.send_message(
            receiver_telegram_id,
            f"📩 *У вас новая анонимная записка!*\n\n"
            f"💬 *Сообщение:*\n{message.text}\n\n"
            f"👤 *Отправитель:* Аноним",
            parse_mode="Markdown"
        )
        
        # Помечаем как прочитанное
        cursor.execute('UPDATE notes SET is_read = 1 WHERE id = ?', (note_id,))
        db_conn.commit()
        
        await message.answer(
            f"✅ *Записка успешно отправлена!*\n\n"
            f"👤 *Получатель:* {receiver_first_name}\n"
            f"🔗 *Username:* @{receiver_username}\n\n"
            f"💬 Сообщение доставлено анонимно.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")
        await message.answer(
            f"⚠️ *Записка сохранена, но не отправлена*\n\n"
            f"Получатель: @{receiver_username}\n"
            f"Возможно, пользователь заблокировал бота.",
            reply_markup=get_main_keyboard()
        )
    
    # Очищаем состояние
    await state.clear()

# ============================================
# ОБРАБОТЧИКИ CALLBACK-ЗАПРОСОВ
# ============================================

@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()

# ============================================
# ОБРАБОТЧИКИ ОСТАЛЬНЫХ КНОПОК
# ============================================

@dp.message(F.text == "👤 Профиль")
async def btn_profile(message: types.Message):
    """Кнопка Профиль"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    # Считаем статистику
    cursor = db_conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM notes WHERE sender_id = ?', (user['id'],))
    sent_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM notes WHERE receiver_id = ?', (user['id'],))
    received_count = cursor.fetchone()[0]
    
    profile_text = f"""
👤 *Ваш профиль:*

*Основная информация:*
• ID: {user['id']}
• Имя: {user['first_name']} {user['last_name'] or ''}
• Username: @{user['username'] or 'не установлен'}
• Регистрация: {user['created_at'][:10]}

*Статистика:*
• 📤 Отправлено записок: {sent_count}
• 📥 Получено записок: {received_count}

*Настройки:*
• 🔍 Видимость в поиске: {'✅ Включена' if user['is_searchable'] else '❌ Выключена'}
"""
    
    await message.answer(profile_text, parse_mode="Markdown")

@dp.message(F.text == "💬 Мои записки")
async def btn_my_notes(message: types.Message):
    """Кнопка Мои записки"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    # Получаем записки пользователя
    cursor = db_conn.cursor()
    cursor.execute('''
        SELECT n.*, u.username as sender_username, u.first_name as sender_first_name
        FROM notes n
        LEFT JOIN users u ON n.sender_id = u.id
        WHERE n.receiver_id = ?
        ORDER BY n.created_at DESC
        LIMIT 20
    ''', (user['id'],))
    
    notes = cursor.fetchall()
    
    if not notes:
        await message.answer("📭 У вас пока нет записок.")
        return
    
    notes_text = "📂 *Ваши последние записки:*\n\n"
    
    for note in notes:
        columns = [description[0] for description in cursor.description]
        note_dict = dict(zip(columns, note))
        
        # Форматируем дату
        created_at = datetime.strptime(note_dict['created_at'], '%Y-%m-%d %H:%M:%S')
        date_str = created_at.strftime('%d.%m %H:%M')
        
        # Обрезаем текст если слишком длинный
        message_text = note_dict['message']
        if len(message_text) > 50:
            message_text = message_text[:50] + "..."
        
        notes_text += f"📄 *{date_str}*\n"
        notes_text += f"{message_text}\n"
        notes_text += f"{'═' * 30}\n"
    
    await message.answer(notes_text, parse_mode="Markdown")

@dp.message(F.text == "🎲 Случайный чат")
async def btn_random_chat(message: types.Message):
    """Кнопка Случайный чат"""
    await message.answer(
        "🎲 *Случайный чат*\n\n"
        "Эта функция в разработке.\n"
        "Скоро будет доступна!",
        parse_mode="Markdown"
    )

@dp.message(F.text == "⚙️ Настройки")
async def btn_settings(message: types.Message):
    """Кнопка Настройки"""
    user = get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Видимость в поиске: " + ("✅ Вкл" if user['is_searchable'] else "❌ Выкл"),
                    callback_data="toggle_visibility"
                )
            ],
            [InlineKeyboardButton(text="🚫 Черный список", callback_data="blacklist")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
        ]
    )
    
    await message.answer(
        "⚙️ *Настройки:*\n\n"
        "Выберите опцию:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message(F.text == "❓ Помощь")
async def btn_help(message: types.Message):
    """Кнопка Помощь"""
    await cmd_help(message)

# ============================================
# ЗАПУСК БОТА
# ============================================

async def main():
    """Основная функция запуска бота"""
    print("=" * 50)
    print("БОТ ДЛЯ АНОНИМНЫХ ЗАПИСОК")
    print("=" * 50)
    
    if BOT_TOKEN == "ВАШ_ТОКЕН_ЗДЕСЬ":
        print("❌ ОШИБКА: Вы не установили токен бота!")
        print("\nКак получить токен:")
        print("1. Откройте Telegram")
        print("2. Найдите @BotFather")
        print("3. Отправьте /newbot")
        print("4. Следуйте инструкциям")
        print("5. Получите токен (выглядит так: 6103456789:AAHrqRlQjZ_NhZy3qLp-aB_cDqLpXyzAbc)")
        print("6. Вставьте токен в строку BOT_TOKEN в начале файла")
        print("=" * 50)
        return
    
    print(f"✅ Токен установлен: {BOT_TOKEN[:10]}...")
    print("✅ База данных подключена")
    print("✅ Бот запускается...")
    print("\n📱 Откройте Telegram и найдите своего бота")
    print("👉 Отправьте команду /start для начала работы")
    print("=" * 50)
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n⚠️ Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()
        db_conn.close()
        print("✅ Ресурсы освобождены")

if __name__ == "__main__":
    asyncio.run(main())
