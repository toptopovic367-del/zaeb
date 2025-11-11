import telebot
from telebot import types
import sqlite3
import time
import os
import logging
from flask import Flask, request

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8273843209:AAGhlZI8WbEYsMGmulBnxxtH6qJ_eFyMKs8')

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Временное хранилище данных
user_data = {}
user_search_data = {}
user_filters = {}  # Для хранения фильтров поиска


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            gender TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            about TEXT,
            telegram TEXT,
            photo TEXT,
            likes_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS views (
            viewer_id INTEGER,
            viewed_id INTEGER,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (viewer_id, viewed_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            liker_id INTEGER,
            liked_id INTEGER,
            liked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (liker_id, liked_id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")


# Вебхук маршрут для Render
@app.route('/')
def home():
    return "🤖 Бот знакомств работает! 🚀"


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid content type', 400


# Команда /start
@bot.message_handler(commands=['start'])
def main(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')

        conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (message.from_user.id,))
        profile = cursor.fetchone()
        conn.close()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        if profile:
            btn1 = types.KeyboardButton('📝 Моя анкета')
            btn2 = types.KeyboardButton('👀 Найти анкеты')
            btn3 = types.KeyboardButton('⚙️ Фильтры поиска')
            btn4 = types.KeyboardButton('✏️ Изменить анкету')
            markup.add(btn1, btn2, btn3, btn4)
            welcome_text = 'С возвращением! Что хочешь сделать?'
        else:
            btn1 = types.KeyboardButton('📝 Создать анкету')
            markup.add(btn1)
            welcome_text = 'Привет! Я бот для знакомств 💕\nДля начала создай свою анкету!'

        bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
        logger.info(f"👤 Пользователь {message.from_user.id} запустил бота")
    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}")
        bot.send_message(message.chat.id, 'Привет! Я бот для знакомств 💕')


# Фильтры поиска
@bot.message_handler(func=lambda message: message.text == '⚙️ Фильтры поиска')
def search_filters(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👨 Искать парней')
    btn2 = types.KeyboardButton('👩 Искать девушек')
    btn3 = types.KeyboardButton('👥 Искать всех')
    btn4 = types.KeyboardButton('📍 Поиск по геолокации')
    btn5 = types.KeyboardButton('🔙 Назад')
    markup.add(btn1, btn2, btn3, btn4, btn5)

    # Получаем текущие настройки фильтра
    current_filter = user_filters.get(message.from_user.id, {}).get('gender', 'all')
    filter_text = {
        'male': '👨 Парни',
        'female': '👩 Девушки',
        'all': '👥 Все'
    }.get(current_filter, '👥 Все')

    bot.send_message(
        message.chat.id,
        f'⚙️ *Текущий фильтр:* {filter_text}\n\nВыбери кого хочешь искать:',
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text in ['👨 Искать парней', '👩 Искать девушек', '👥 Искать всех'])
def set_search_filter(message):
    filter_map = {
        '👨 Искать парней': 'male',
        '👩 Искать девушек': 'female',
        '👥 Искать всех': 'all'
    }

    if message.from_user.id not in user_filters:
        user_filters[message.from_user.id] = {}

    user_filters[message.from_user.id]['gender'] = filter_map[message.text]

    filter_text = {
        'male': '👨 парней',
        'female': '👩 девушек',
        'all': '👥 всех'
    }.get(filter_map[message.text])

    bot.send_message(
        message.chat.id,
        f'✅ Теперь будешь искать *{filter_text}*',
        parse_mode='Markdown'
    )
    main(message)


# Поиск по геолокации
@bot.message_handler(func=lambda message: message.text == '📍 Поиск по геолокации')
def request_location(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_location = types.KeyboardButton('📍 Отправить геолокацию', request_location=True)
    btn_back = types.KeyboardButton('🔙 Назад')
    markup.add(btn_location, btn_back)

    bot.send_message(
        message.chat.id,
        '📍 *Поиск по геолокации*\n\nНажми кнопку ниже чтобы отправить свою геолокацию. Я найду анкеты рядом с тобой!',
        parse_mode='Markdown',
        reply_markup=markup
    )


# Обработка геолокации
@bot.message_handler(content_types=['location'])
def handle_location(message):
    try:
        latitude = message.location.latitude
        longitude = message.location.longitude

        # Сохраняем геолокацию пользователя
        conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE profiles SET latitude = ?, longitude = ? WHERE user_id = ?',
            (latitude, longitude, message.from_user.id)
        )
        conn.commit()
        conn.close()

        # Устанавливаем фильтр по геолокации
        if message.from_user.id not in user_filters:
            user_filters[message.from_user.id] = {}
        user_filters[message.from_user.id]['location'] = True
        user_filters[message.from_user.id]['user_lat'] = latitude
        user_filters[message.from_user.id]['user_lon'] = longitude

        bot.send_message(
            message.chat.id,
            f'📍 *Геолокация сохранена!*\n\nШирота: {latitude:.4f}\nДолгота: {longitude:.4f}\n\nТеперь буду искать анкеты рядом с тобой!',
            parse_mode='Markdown'
        )

        # Запускаем поиск с геолокацией
        find_profiles_with_location(message)

    except Exception as e:
        logger.error(f"Ошибка обработки геолокации: {e}")
        bot.send_message(message.chat.id, '❌ Ошибка при обработке геолокации')


# Функция расчета расстояния между точками (упрощенная формула)
def calculate_distance(lat1, lon1, lat2, lon2):
    # Упрощенный расчет расстояния (в км)
    import math
    R = 6371  # Радиус Земли в км

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def find_profiles_with_location(message):
    """Поиск анкет с учетом геолокации"""
    try:
        conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
        cursor = conn.cursor()

        # Получаем текущие настройки фильтра
        user_filter = user_filters.get(message.from_user.id, {})
        user_lat = user_filter.get('user_lat')
        user_lon = user_filter.get('user_lon')

        if not user_lat or not user_lon:
            bot.send_message(message.chat.id, '❌ Сначала отправь свою геолокацию')
            return

        # Базовый запрос
        query = '''
            SELECT *, 
                   (6371 * acos(cos(radians(?)) * cos(radians(latitude)) * 
                   cos(radians(longitude) - radians(?)) + 
                   sin(radians(?)) * sin(radians(latitude)))) as distance
            FROM profiles 
            WHERE user_id != ? AND is_active = 1 
            AND latitude IS NOT NULL AND longitude IS NOT NULL
        '''
        params = [user_lat, user_lon, user_lat, message.from_user.id]

        # Добавляем фильтр по полу если выбран
        gender_filter = user_filter.get('gender', 'all')
        if gender_filter == 'male':
            query += ' AND gender = ?'
            params.append('👨 Мужской')
        elif gender_filter == 'female':
            query += ' AND gender = ?'
            params.append('👩 Женский')

        # Исключаем уже просмотренные анкеты
        query += '''
            AND user_id NOT IN (
                SELECT viewed_id FROM views 
                WHERE viewer_id = ?
            )
        '''
        params.append(message.from_user.id)

        # Фильтр по расстоянию (до 50 км)
        query += ' HAVING distance < 50 ORDER BY distance ASC LIMIT 10'

        cursor.execute(query, params)
        profiles = cursor.fetchall()
        conn.close()

        if not profiles:
            bot.send_message(
                message.chat.id,
                '😔 Пока нет анкет поблизости!\n\nПопробуй:\n• Изменить фильтры поиска\n• Подождать пока появятся новые анкеты\n• Расширить радиус поиска'
            )
            return

        # Сохраняем список анкет для пользователя
        user_search_data[message.from_user.id] = {
            'profiles': profiles,
            'current_index': 0
        }

        # Показываем первую анкету
        show_next_profile(message)

    except Exception as e:
        logger.error(f"Ошибка поиска по геолокации: {e}")
        bot.send_message(message.chat.id, '❌ Ошибка при поиске анкет')


# Создание анкеты - шаг 1: имя
@bot.message_handler(func=lambda message: message.text == '📝 Создать анкету')
def create_profile(message):
    bot.send_chat_action(message.chat.id, 'typing')
    markup = types.ReplyKeyboardRemove()
    msg = bot.send_message(
        message.chat.id,
        'Отлично! Давай создадим твою анкету.\n\n*Как тебя зовут?*',
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, process_name)


def process_name(message):
    try:
        name = message.text.strip()
        if len(name) < 2:
            msg = bot.send_message(message.chat.id, '❌ Имя должно быть не короче 2 символов!\nПопробуй еще раз:')
            bot.register_next_step_handler(msg, process_name)
            return

        user_data[message.from_user.id] = {'name': name}

        msg = bot.send_message(
            message.chat.id,
            f'👋 Приятно познакомиться, *{name}*!\n\n*Сколько тебе лет?*',
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_age)
    except Exception as e:
        logger.error(f"Ошибка в process_name: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 2: возраст
def process_age(message):
    try:
        if not message.text.isdigit():
            msg = bot.send_message(message.chat.id, '❌ Пожалуйста, введи возраст *цифрами*:\n\n_Например: 18_',
                                   parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_age)
            return

        age = int(message.text)
        if age < 16 or age > 100:
            msg = bot.send_message(message.chat.id, '❌ Возраст должен быть *от 16 до 100 лет*:\n\n_Попробуй еще раз:_',
                                   parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_age)
            return

        user_data[message.from_user.id]['age'] = age

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('👨 Мужской')
        btn2 = types.KeyboardButton('👩 Женский')
        markup.add(btn1, btn2)

        msg = bot.send_message(
            message.chat.id,
            f'🎂 Отлично, *{age} лет*!\n\n*Выбери свой пол:*',
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_gender)
    except Exception as e:
        logger.error(f"Ошибка в process_age: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 3: пол
def process_gender(message):
    try:
        gender = message.text
        if gender not in ['👨 Мужской', '👩 Женский']:
            msg = bot.send_message(message.chat.id, '❌ Пожалуйста, выбери пол *из кнопок ниже*:')
            bot.register_next_step_handler(msg, process_gender)
            return

        user_data[message.from_user.id]['gender'] = gender

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('📍 Отправить геолокацию', request_location=True)
        btn2 = types.KeyboardButton('🚀 Пропустить геолокацию')
        markup.add(btn1, btn2)

        msg = bot.send_message(
            message.chat.id,
            f'✅ Пол выбран: *{gender}*\n\n*Теперь укажи свой город или отправь геолокацию:*\n\n_Геолокация поможет находить анкеты рядом с тобой_',
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_location_or_city)
    except Exception as e:
        logger.error(f"Ошибка в process_gender: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


def process_location_or_city(message):
    try:
        if message.content_type == 'location':
            # Обрабатываем геолокацию
            latitude = message.location.latitude
            longitude = message.location.longitude

            # Получаем город по координатам (упрощенно)
            city = "📍 Рядом с тобой"

            user_data[message.from_user.id]['city'] = city
            user_data[message.from_user.id]['latitude'] = latitude
            user_data[message.from_user.id]['longitude'] = longitude

            msg = bot.send_message(
                message.chat.id,
                f'📍 *Геолокация сохранена!*\n\nТеперь расскажи о себе:',
                parse_mode='Markdown',
                reply_markup=types.ReplyKeyboardRemove()
            )
            bot.register_next_step_handler(msg, process_about)

        elif message.text == '🚀 Пропустить геолокацию':
            msg = bot.send_message(
                message.chat.id,
                '🏙️ *Из какого ты города?*',
                parse_mode='Markdown',
                reply_markup=types.ReplyKeyboardRemove()
            )
            bot.register_next_step_handler(msg, process_city)
        else:
            # Пользователь ввел город вручную
            city = message.text.strip()
            if len(city) < 2:
                msg = bot.send_message(message.chat.id,
                                       '❌ Название города должно быть не короче 2 символов!\nПопробуй еще раз:')
                bot.register_next_step_handler(msg, process_location_or_city)
                return

            user_data[message.from_user.id]['city'] = city
            user_data[message.from_user.id]['latitude'] = None
            user_data[message.from_user.id]['longitude'] = None

            msg = bot.send_message(
                message.chat.id,
                f'🏙️ *Город: {city}*\n\nТеперь расскажи о себе:',
                parse_mode='Markdown'
            )
            bot.register_next_step_handler(msg, process_about)

    except Exception as e:
        logger.error(f"Ошибка в process_location_or_city: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 4: город (если не отправлена геолокация)
def process_city(message):
    try:
        city = message.text.strip()
        if len(city) < 2:
            msg = bot.send_message(message.chat.id,
                                   '❌ Название города должно быть не короче 2 символов!\nПопробуй еще раз:')
            bot.register_next_step_handler(msg, process_city)
            return

        user_data[message.from_user.id]['city'] = city
        user_data[message.from_user.id]['latitude'] = None
        user_data[message.from_user.id]['longitude'] = None

        example_about = """*Пример заполнения:*
🎯 Ищу: новые знакомства, общение
💼 Делаю: учусь в школе, занимаюсь спортом
🎮 Интересы: игры, музыка, путешествия

*Теперь расскажи о себе:*"""

        msg = bot.send_message(
            message.chat.id,
            f'🏙️ Город: *{city}*\n\n{example_about}',
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_about)
    except Exception as e:
        logger.error(f"Ошибка в process_city: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 5: о себе
def process_about(message):
    try:
        about = message.text.strip()
        if len(about) < 20:
            msg = bot.send_message(
                message.chat.id,
                '❌ Расскажи о себе *подробнее* (минимум 20 символов):\n\n_Опиши свои интересы, чем занимаешься, что ищешь_',
                parse_mode='Markdown'
            )
            bot.register_next_step_handler(msg, process_about)
            return

        user_data[message.from_user.id]['about'] = about

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('📸 Добавить фото')
        btn2 = types.KeyboardButton('🚀 Без фото')
        markup.add(btn1, btn2)

        msg = bot.send_message(
            message.chat.id,
            '📝 Отлично! *Хочешь добавить фото к анкете?*\n\n_Фото поможет привлечь больше внимания_',
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_photo_choice)

    except Exception as e:
        print(f"Ошибка в process_about: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 6: выбор - добавлять фото или нет
def process_photo_choice(message):
    try:
        if message.text == '📸 Добавить фото':
            msg = bot.send_message(message.chat.id, '📷 Отлично! Пришли свое *фото*:', parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_photo)
        elif message.text == '🚀 Без фото':
            user_data[message.from_user.id]['photo'] = None
            save_complete_profile(message)
        else:
            msg = bot.send_message(message.chat.id, '❌ Пожалуйста, выбери вариант *из кнопок*:')
            bot.register_next_step_handler(msg, process_photo_choice)
    except Exception as e:
        logger.error(f"Ошибка в process_photo_choice: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 7: обработка фото
def process_photo(message):
    try:
        if message.content_type == 'photo':
            photo = message.photo[-1].file_id
            user_data[message.from_user.id]['photo'] = photo
            save_complete_profile(message)
        else:
            msg = bot.send_message(message.chat.id, '❌ Пожалуйста, пришли *фото*:')
            bot.register_next_step_handler(msg, process_photo)
    except Exception as e:
        logger.error(f"Ошибка в process_photo: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Финальное сохранение анкеты
def save_complete_profile(message):
    try:
        user_id = message.from_user.id
        data = user_data.get(user_id)

        if not data:
            bot.send_message(message.chat.id, '❌ Данные потеряны. Начни заново: /start')
            return

        conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO profiles 
            (user_id, name, age, gender, city, latitude, longitude, about, telegram, photo, likes_count, is_active) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
        ''', (
            user_id, data['name'], data['age'], data['gender'],
            data.get('city'), data.get('latitude'), data.get('longitude'),
            data['about'], '', data.get('photo')
        ))
        conn.commit()
        conn.close()

        if user_id in user_data:
            del user_data[user_id]

        show_profile(message.chat.id, user_id, is_new=True)
        time.sleep(2)
        main_menu(message)

    except Exception as e:
        logger.error(f"Ошибка в save_complete_profile: {e}")
        bot.send_message(message.chat.id, '❌ Ошибка сохранения. Начни заново: /start')


# Главное меню после создания анкеты
def main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('📝 Моя анкета')
    btn2 = types.KeyboardButton('👀 Найти анкеты')
    btn3 = types.KeyboardButton('⚙️ Фильтры поиска')
    btn4 = types.KeyboardButton('✏️ Изменить анкету')
    markup.add(btn1, btn2, btn3, btn4)

    bot.send_message(
        message.chat.id,
        '🎉 *Анкета создана!* Теперь ты можешь:\n\n• 📝 Посмотреть свою анкету\n• 👀 Найти другие анкеты\n• ⚙️ Настроить фильтры\n• ✏️ Изменить свою анкету',
        parse_mode='Markdown',
        reply_markup=markup
    )


# Показать анкету
def show_profile(chat_id, user_id, is_new=False):
    conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    conn.close()

    if profile:
        (user_id, name, age, gender, city, latitude, longitude,
         about, telegram, photo, likes_count, is_active, created_at) = profile

        profile_text = f"""
📝 *{'НОВАЯ АНКЕТА' if is_new else 'ТВОЯ АНКЕТА'}*

👤 *Имя:* {name}
🎂 *Возраст:* {age}
🚻 *Пол:* {gender}
🏙️ *Город:* {city}
❤️ *Лайков:* {likes_count}

📖 *О себе:*
{about}

{'✅ *Анкета успешно создана!*' if is_new else '📊 *Вот твоя анкета:*'}
        """

        try:
            if photo:
                bot.send_photo(chat_id, photo, caption=profile_text, parse_mode='Markdown')
            else:
                bot.send_message(chat_id, profile_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка отправки анкеты: {e}")
            bot.send_message(chat_id, profile_text, parse_mode='Markdown')


# Показать мою анкету
@bot.message_handler(func=lambda message: message.text == '📝 Моя анкета')
def my_profile(message):
    conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (message.from_user.id,))
    profile = cursor.fetchone()
    conn.close()

    if profile:
        show_profile(message.chat.id, message.from_user.id)
    else:
        bot.send_message(message.chat.id, '❌ У тебя еще нет анкеты! Нажми "📝 Создать анкету"')


# Поиск анкет
@bot.message_handler(func=lambda message: message.text == '👀 Найти анкеты')
def find_profiles(message):
    # Проверяем есть ли анкета у пользователя
    conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (message.from_user.id,))
    user_profile = cursor.fetchone()

    if not user_profile:
        bot.send_message(message.chat.id, '❌ Сначала создай свою анкету!')
        conn.close()
        return

    # Проверяем включен ли поиск по геолокации
    user_filter = user_filters.get(message.from_user.id, {})
    if user_filter.get('location'):
        find_profiles_with_location(message)
        return

    # Обычный поиск без геолокации
    gender_filter = user_filter.get('gender', 'all')

    # Базовый запрос
    query = '''
        SELECT * FROM profiles 
        WHERE user_id != ? AND is_active = 1 
    '''
    params = [message.from_user.id]

    # Добавляем фильтр по полу если выбран
    if gender_filter == 'male':
        query += ' AND gender = ?'
        params.append('👨 Мужской')
    elif gender_filter == 'female':
        query += ' AND gender = ?'
        params.append('👩 Женский')

    # Исключаем уже просмотренные анкеты
    query += '''
        AND user_id NOT IN (
            SELECT viewed_id FROM views 
            WHERE viewer_id = ?
        )
    '''
    params.append(message.from_user.id)

    query += ' ORDER BY RANDOM() LIMIT 10'

    cursor.execute(query, params)
    profiles = cursor.fetchall()
    conn.close()

    if not profiles:
        bot.send_message(message.chat.id,
                         '😔 Пока нет новых анкет по твоему фильтру!\n\nПопробуй:\n• Изменить фильтры поиска\n• Подождать пока появятся новые анкеты')
        return

    # Сохраняем список анкет для пользователя
    user_search_data[message.from_user.id] = {
        'profiles': profiles,
        'current_index': 0
    }

    # Показываем первую анкету
    show_next_profile(message)


def show_next_profile(message):
    user_id = message.from_user.id
    if user_id not in user_search_data:
        find_profiles(message)
        return

    data = user_search_data[user_id]
    profiles = data['profiles']
    index = data['current_index']

    if index >= len(profiles):
        bot.send_message(message.chat.id, '🔚 Это все анкеты на данный момент!\nПопробуй позже ⏳')
        if user_id in user_search_data:
            del user_search_data[user_id]
        return

    profile = profiles[index]
    (viewed_user_id, name, age, gender, city, latitude, longitude,
     about, telegram, photo, likes_count, is_active, created_at) = profile

    # Сохраняем просмотр
    conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO views (viewer_id, viewed_id) 
        VALUES (?, ?)
    ''', (message.from_user.id, viewed_user_id))
    conn.commit()
    conn.close()

    # Показываем расстояние если есть геолокация
    distance_text = ""
    user_filter = user_filters.get(message.from_user.id, {})
    if user_filter.get('location') and user_filter.get('user_lat') and user_filter.get(
            'user_lon') and latitude and longitude:
        distance = calculate_distance(
            user_filter['user_lat'], user_filter['user_lon'],
            latitude, longitude
        )
        distance_text = f"📍 *Расстояние:* {distance:.1f} км\n"

    profile_text = f"""
👤 *Анкета {index + 1}/{len(profiles)}*

*Имя:* {name}
*Возраст:* {age}
*Пол:* {gender}
*🏙️ Город:* {city}
{distance_text}❤️ *Лайков:* {likes_count}

*О себе:*
{about}
    """

    markup = types.InlineKeyboardMarkup()
    btn_like = types.InlineKeyboardButton('❤️ Лайк', callback_data=f'like_{viewed_user_id}_{message.from_user.id}')
    btn_next = types.InlineKeyboardButton('➡️ Дальше', callback_data='next')
    btn_report = types.InlineKeyboardButton('🚫 Пожаловаться', callback_data=f'report_{viewed_user_id}')
    markup.add(btn_like, btn_next)
    markup.add(btn_report)

    try:
        if photo:
            bot.send_photo(
                message.chat.id,
                photo,
                caption=profile_text,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        else:
            bot.send_message(
                message.chat.id,
                profile_text,
                reply_markup=markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Ошибка отправки анкеты: {e}")


# ========== УПРАВЛЕНИЕ АНКЕТОЙ ==========

# Изменение анкеты
@bot.message_handler(func=lambda message: message.text == '✏️ Изменить анкету')
def edit_profile(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👤 Изменить имя')
    btn2 = types.KeyboardButton('🎂 Изменить возраст')
    btn3 = types.KeyboardButton('🏙️ Изменить город')
    btn4 = types.KeyboardButton('📍 Обновить геолокацию')
    btn5 = types.KeyboardButton('📖 Изменить описание')
    btn6 = types.KeyboardButton('📷 Изменить фото')
    btn7 = types.KeyboardButton('🗑️ Удалить анкету')
    btn8 = types.KeyboardButton('🔙 Назад')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)

    bot.send_message(
        message.chat.id,
        '✏️ *Управление анкетой*\n\nЧто хочешь сделать?',
        parse_mode='Markdown',
        reply_markup=markup
    )


# Назад в главное меню
@bot.message_handler(func=lambda message: message.text == '🔙 Назад')
def back_to_main(message):
    main(message)


# Обновление геолокации
@bot.message_handler(func=lambda message: message.text == '📍 Обновить геолокацию')
def update_location(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_location = types.KeyboardButton('📍 Отправить геолокацию', request_location=True)
    btn_back = types.KeyboardButton('🔙 Назад')
    markup.add(btn_location, btn_back)

    bot.send_message(
        message.chat.id,
        '📍 *Обновление геолокации*\n\nНажми кнопку ниже чтобы отправить новую геолокацию:',
        parse_mode='Markdown',
        reply_markup=markup
    )


# Удаление анкеты
@bot.message_handler(func=lambda message: message.text == '🗑️ Удалить анкету')
def delete_profile(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('✅ Да, удалить')
    btn2 = types.KeyboardButton('❌ Нет, отмена')
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        '⚠️ *Точно удалить анкету?*\n\nЭто действие нельзя отменить!',
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text == '✅ Да, удалить')
def confirm_delete(message):
    try:
        conn = sqlite3