import asyncio
from datetime import datetime, timedelta
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Настройки - ВСТАВЬТЕ ВАШ ТОКЕН!!!
API_TOKEN = '8668270061:AAH2N1GTirjjYq5dkNKVV0uTofx6dtQJDQg'  # Замените на ваш токен от @BotFather

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота с хранилищем состояний
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# Определяем состояния для пошагового добавления подписки
class AddSubscription(StatesGroup):
    name = State()
    cost = State()
    period = State()
    date = State()
    category = State()

# База данных - ИСПРАВЛЕННАЯ ВЕРСИЯ
class SimpleDB:
    def __init__(self):
        self.conn = sqlite3.connect('subscriptions.db', check_same_thread=False)
        self.init_db()
    
    def init_db(self):
        cursor = self.conn.cursor()
        # Удаляем старую таблицу, если она есть с неправильной структурой
        cursor.execute('DROP TABLE IF EXISTS subs')
        # Создаем новую таблицу с правильными колонками
        cursor.execute('''
            CREATE TABLE subs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                cost REAL,
                period TEXT,
                next_date TEXT,
                category TEXT
            )
        ''')
        self.conn.commit()
        logger.info("База данных успешно создана с правильной структурой")
    
    def add_sub(self, user_id, name, cost, period, next_date, category):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO subs (user_id, name, cost, period, next_date, category) VALUES (?,?,?,?,?,?)',
            (user_id, name, cost, period, next_date, category)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_all(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM subs WHERE user_id = ? ORDER BY next_date', (user_id,))
        return cursor.fetchall()
    
    def get_one(self, sub_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM subs WHERE id = ? AND user_id = ?', (sub_id, user_id))
        return cursor.fetchone()
    
    def delete(self, sub_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM subs WHERE id = ? AND user_id = ?', (sub_id, user_id))
        self.conn.commit()
    
    def update_next_date(self, sub_id, new_date):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE subs SET next_date = ? WHERE id = ?', (new_date, sub_id))
        self.conn.commit()
    
    def get_upcoming(self, user_id, days=7):
        cursor = self.conn.cursor()
        today = datetime.now().date()
        future = (today + timedelta(days=days)).strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')
        cursor.execute(
            'SELECT * FROM subs WHERE user_id = ? AND next_date BETWEEN ? AND ? ORDER BY next_date',
            (user_id, today_str, future)
        )
        return cursor.fetchall()

# Создаем экземпляр базы данных
db = SimpleDB()

# Категории подписок
CATEGORIES = {
    "🎬 Кино": "Кино",
    "🎵 Музыка": "Музыка", 
    "🎮 Игры": "Игры",
    "🛠️ Сервисы": "Сервисы",
    "📚 Образование": "Образование",
    "🏋️ Спорт": "Спорт",
    "☁️ Облако": "Облачные сервисы",
    "📰 Новости": "Новости"
}

# Периоды подписок
PERIODS = {
    "📅 Неделя": "неделя",
    "📅 Месяц": "месяц", 
    "📅 Год": "год"
}

def main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои подписки", callback_data="list")
    builder.button(text="➕ Добавить", callback_data="add_start")
    builder.button(text="💰 Ближайшие", callback_data="upcoming")
    builder.button(text="❓ Помощь", callback_data="help")
    builder.adjust(2)
    return builder.as_markup()

def get_categories_keyboard():
    builder = InlineKeyboardBuilder()
    for cat_display, cat_value in CATEGORIES.items():
        builder.button(text=cat_display, callback_data=f"cat_{cat_value}")
    builder.adjust(2)
    return builder.as_markup()

def get_periods_keyboard():
    builder = InlineKeyboardBuilder()
    for period_display, period_value in PERIODS.items():
        builder.button(text=period_display, callback_data=f"period_{period_value}")
    builder.adjust(2)
    return builder.as_markup()

def subscription_keyboard(sub_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Оплачено", callback_data=f"pay_{sub_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_{sub_id}")
    builder.button(text="◀️ Назад", callback_data="list")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 Привет! Я бот для управления подписками\n\n"
        "Я помогу тебе отслеживать все твои подписки и не пропускать платежи!\n\n"
        "Выбери действие:",
        reply_markup=main_keyboard()
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "❓ **Как пользоваться ботом**\n\n"
        "📋 **Мои подписки** - просмотр всех подписок\n"
        "➕ **Добавить** - добавить новую подписку (пошагово)\n"
        "💰 **Ближайшие** - платежи на ближайшие 7 дней\n\n"
        "После добавления подписки ты можешь:\n"
        "• Нажать **Оплачено** - автоматически обновится дата\n"
        "• Нажать **Удалить** - убрать подписку\n\n"
        "Все данные сохраняются в базе данных!",
        parse_mode='Markdown'
    )

# НАЧАЛО ПОШАГОВОГО ДОБАВЛЕНИЯ
@dp.callback_query(F.data == "add_start")
async def add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 **Шаг 1 из 5**\n\nВведите название сервиса (например: Netflix, Spotify):")
    await state.set_state(AddSubscription.name)
    await callback.answer()

@dp.message(AddSubscription.name)
async def add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "💰 **Шаг 2 из 5**\n\n"
        "Введите сумму списания в рублях (только число, например: 10, 5.5, 12.99):"
    )
    await state.set_state(AddSubscription.cost)

@dp.message(AddSubscription.cost)
async def add_cost(message: Message, state: FSMContext):
    try:
        cost = float(message.text.replace(',', '.'))
        await state.update_data(cost=cost)
        await message.answer(
            "📅 **Шаг 3 из 5**\n\n"
            "Выберите период подписки:",
            reply_markup=get_periods_keyboard()
        )
        await state.set_state(AddSubscription.period)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 10, 5.5, 12.99)")

@dp.callback_query(AddSubscription.period, F.data.startswith("period_"))
async def add_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split('_')[1]
    await state.update_data(period=period)
    await callback.message.edit_text(
        "📅 **Шаг 4 из 5**\n\n"
        "📌 Введите дату оформления подписки в формате **ДД.ММ.ГГГГ**\n"
        "Например: **18.02.2026**\n\n"
        "Или нажми /today для сегодняшней даты"
    )
    await state.set_state(AddSubscription.date)
    await callback.answer()

@dp.message(AddSubscription.date)
async def add_date(message: Message, state: FSMContext):
    try:
        if message.text == "/today":
            # Сегодняшняя дата в формате ДД.ММ.ГГГГ
            date = datetime.now()
            date_str = date.strftime('%d.%m.%Y')
            date_for_db = date.strftime('%Y-%m-%d')
        else:
            # Проверяем формат ДД.ММ.ГГГГ
            date = datetime.strptime(message.text, '%d.%m.%Y')
            date_str = message.text
            date_for_db = date.strftime('%Y-%m-%d')
        
        # Сохраняем дату для базы данных в формате ГГГГ-ММ-ДД
        await state.update_data(date=date_for_db)
        # Сохраняем также для отображения
        await state.update_data(date_display=date_str)
        
        await message.answer(
            "🏷️ **Шаг 5 из 5**\n\n"
            "Выберите категорию подписки:",
            reply_markup=get_categories_keyboard()
        )
        await state.set_state(AddSubscription.category)
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты.\n"
            "Используйте **ДД.ММ.ГГГГ** (например: **18.02.2026**)\n"
            "Или нажми /today"
        )

@dp.callback_query(AddSubscription.category, F.data.startswith("cat_"))
async def add_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split('_')[1]
    data = await state.get_data()
    
    # Рассчитываем следующую дату платежа
    start_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    
    if data['period'] == 'месяц':
        next_date = start_date + timedelta(days=30)
    elif data['period'] == 'год':
        next_date = start_date + timedelta(days=365)
    elif data['period'] == 'неделя':
        next_date = start_date + timedelta(weeks=1)
    else:
        next_date = start_date + timedelta(days=30)
    
    # Сохраняем в базу
    sub_id = db.add_sub(
        callback.from_user.id,
        data['name'],
        data['cost'],
        data['period'],
        next_date.strftime('%Y-%m-%d'),
        category
    )
    
    # Показываем подтверждение
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 К списку подписок", callback_data="list")
    builder.button(text="➕ Добавить еще", callback_data="add_start")
    builder.adjust(1)
    
    # Форматируем даты для отображения
    start_date_display = data.get('date_display', datetime.strptime(data['date'], '%Y-%m-%d').strftime('%d.%m.%Y'))
    next_date_display = next_date.strftime('%d.%m.%Y')
    
    await callback.message.edit_text(
        f"✅ **Подписка успешно добавлена!**\n\n"
        f"📌 **Название:** {data['name']}\n"
        f"💰 **Сумма:** {data['cost']} ₽/{data['period']}\n"
        f"📅 **Дата оформления:** {start_date_display}\n"
        f"🏷️ **Категория:** {category}\n"
        f"📅 **Следующий платеж:** {next_date_display}\n\n"
        f"ID: {sub_id}",
        parse_mode='Markdown',
        reply_markup=builder.as_markup()
    )
    
    await state.clear()
    await callback.answer()

# ПРОСМОТР ПОДПИСОК
@dp.callback_query(F.data == "list")
async def show_list(callback: CallbackQuery):
    subs = db.get_all(callback.from_user.id)
    
    if not subs:
        await callback.answer("У вас пока нет подписок")
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить первую", callback_data="add_start")
        builder.button(text="◀️ В меню", callback_data="menu")
        await callback.message.edit_text(
            "📭 **У вас пока нет подписок**\n\nНажмите кнопку ниже, чтобы добавить первую подписку!",
            parse_mode='Markdown',
            reply_markup=builder.as_markup()
        )
        return
    
    builder = InlineKeyboardBuilder()
    for sub in subs:
        next_date = datetime.strptime(sub[5], '%Y-%m-%d')
        days = (next_date.date() - datetime.now().date()).days
        emoji = "🔴" if days <= 3 else "🟡" if days <= 7 else "🟢"
        builder.button(
            text=f"{emoji} {sub[2]} - {sub[3]}₽ (через {days} дн.)",
            callback_data=f"view_{sub[0]}"
        )
    builder.button(text="◀️ В меню", callback_data="menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📋 **Ваши подписки:**\n_(нажмите для просмотра деталей)_",
        parse_mode='Markdown',
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("view_"))
async def view_sub(callback: CallbackQuery):
    sub_id = int(callback.data.split('_')[1])
    sub = db.get_one(sub_id, callback.from_user.id)
    
    if not sub:
        await callback.answer("Подписка не найдена")
        return
    
    next_date = datetime.strptime(sub[5], '%Y-%m-%d')
    days = (next_date.date() - datetime.now().date()).days
    next_date_display = next_date.strftime('%d.%m.%Y')
    
    text = f"""
📌 **{sub[2]}**

💰 **Стоимость:** {sub[3]} ₽/{sub[4]}
📅 **Следующий платеж:** {next_date_display} (через {days} дн.)
🏷️ **Категория:** {sub[6] or 'Не указана'}

{'🔴 **СКОРО! Осталось меньше 3 дней!**' if days <= 3 else ''}
    """
    
    await callback.message.edit_text(
        text,
        parse_mode='Markdown',
        reply_markup=subscription_keyboard(sub_id)
    )
    await callback.answer()

# ОПЛАЧЕНО
@dp.callback_query(F.data.startswith("pay_"))
async def mark_paid(callback: CallbackQuery):
    sub_id = int(callback.data.split('_')[1])
    sub = db.get_one(sub_id, callback.from_user.id)
    
    if sub:
        next_date = datetime.strptime(sub[5], '%Y-%m-%d')
        
        if sub[4] == 'месяц':
            new_date = next_date + timedelta(days=30)
        elif sub[4] == 'год':
            new_date = next_date + timedelta(days=365)
        elif sub[4] == 'неделя':
            new_date = next_date + timedelta(weeks=1)
        else:
            new_date = next_date + timedelta(days=30)
        
        db.update_next_date(sub_id, new_date.strftime('%Y-%m-%d'))
        await callback.answer("✅ Платеж отмечен! Дата обновлена")
        await view_sub(callback)

# УДАЛЕНИЕ
@dp.callback_query(F.data.startswith("delete_"))
async def delete_sub(callback: CallbackQuery):
    sub_id = int(callback.data.split('_')[1])
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"confirm_delete_{sub_id}")
    builder.button(text="❌ Нет, оставить", callback_data=f"view_{sub_id}")
    builder.adjust(2)
    
    await callback.message.edit_text(
        "🗑️ **Вы уверены, что хотите удалить эту подписку?**",
        parse_mode='Markdown',
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: CallbackQuery):
    sub_id = int(callback.data.split('_')[2])
    db.delete(sub_id, callback.from_user.id)
    await callback.answer("✅ Подписка удалена")
    await show_list(callback)

# БЛИЖАЙШИЕ ПЛАТЕЖИ
@dp.callback_query(F.data == "upcoming")
async def show_upcoming(callback: CallbackQuery):
    subs = db.get_upcoming(callback.from_user.id)
    
    if not subs:
        await callback.answer("Нет ближайших платежей")
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ В меню", callback_data="menu")
        await callback.message.edit_text(
            "💰 **Ближайшие платежи**\n\n"
            "В ближайшие 7 дней платежей нет.",
            parse_mode='Markdown',
            reply_markup=builder.as_markup()
        )
        return
    
    text = "💰 **Ближайшие платежи (7 дней):**\n\n"
    total = 0
    
    for sub in subs:
        next_date = datetime.strptime(sub[5], '%Y-%m-%d')
        days = (next_date.date() - datetime.now().date()).days
        next_date_display = next_date.strftime('%d.%m.%Y')
        text += f"• **{sub[2]}** - {sub[3]}₽\n"
        text += f"  📅 {next_date_display} (через {days} дн.)\n"
        total += sub[3]
    
    text += f"\n💵 **Итого к оплате: {total} ₽**"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В меню", callback_data="menu")
    
    await callback.message.edit_text(
        text,
        parse_mode='Markdown',
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# МЕНЮ И ПОМОЩЬ
@dp.callback_query(F.data == "menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    await help_cmd(callback.message)
    await callback.answer()

async def main():
    print("✅ Бот запущен! Нажми Ctrl+C для остановки")
    print("📱 Имя бота: @My_subs1_bot")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())