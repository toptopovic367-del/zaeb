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
            about TEXT,
            telegram TEXT,
            photo TEXT,
            is_active INTEGER DEFAULT 1
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
        conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (message.from_user.id,))
        profile = cursor.fetchone()
        conn.close()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        if profile:
            btn1 = types.KeyboardButton('📝 Моя анкета')
            btn2 = types.KeyboardButton('👀 Найти анкеты')
            btn3 = types.KeyboardButton('✏️ Изменить анкету')
            markup.add(btn1, btn2, btn3)
            welcome_text = 'С возвращением! Что хочешь сделать?'
        else:
            btn1 = types.KeyboardButton('📝 Создать анкету')
            markup.add(btn1)
            welcome_text = 'Привет! Я бот для знакомств 💕\nДля начала создай свою анкету!'

        bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
        logger.info(f"👤 Пользователь {message.from_user.id} запустил бота")
    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}")


# Создание анкеты - шаг 1: имя
@bot.message_handler(func=lambda message: message.text == '📝 Создать анкету')
def create_profile(message):
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

        markup = types.ReplyKeyboardRemove()
        msg = bot.send_message(
            message.chat.id,
            f'✅ Пол выбран: *{gender}*\n\n*Из какого ты города?*',
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_city)
    except Exception as e:
        logger.error(f"Ошибка в process_gender: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 4: город
def process_city(message):
    try:
        city = message.text.strip()
        if len(city) < 2:
            msg = bot.send_message(message.chat.id,
                                   '❌ Название города должно быть не короче 2 символов!\nПопробуй еще раз:')
            bot.register_next_step_handler(msg, process_city)
            return

        user_data[message.from_user.id]['city'] = city

        example_about = """*Пример заполнения:*
🎯 Ищу: новые знакомства, общение
💼 Делаю: учусь в школе, занимаюсь спортом
🎮 Интересы: игры, музыка, путешествия
📱 Telegram: @username

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


# Шаг 5: о себе и Telegram
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

        tg_uname = message.from_user.username
        if tg_uname:
            user_data[message.from_user.id]['telegram'] = f"@{tg_uname}"
        else:
            user_data[message.from_user.id]['telegram'] = "⚠️Не указан"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('📸 Добавить фото')
        btn2 = types.KeyboardButton('🚀 Без фото')
        markup.add(btn1, btn2)

        username_display = user_data[message.from_user.id]['telegram']
        msg = bot.send_message(
            message.chat.id,
            f'📱 *Telegram username автоматически сохранен:* {username_display}\n\n*Хочешь добавить фото к анкете?*',
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_photo_choice)

        # msg = bot.send_message(
        #     message.chat.id,
        #     '📝 Отлично! Теперь укажи свой *Telegram username*:\n\n_Например: @username_\n_Если нет username, напиши "нет"_',
        #     parse_mode='Markdown'
        # )
        # bot.register_next_step_handler(msg, process_telegram)

    except Exception as e:
        print(f"Ошибка в process_about: {e}")
        bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# # Шаг 6: Telegram username
# def process_telegram(message):
#     try:
#         telegram = message.text.strip()
#         user_data[message.from_user.id]['telegram'] = telegram
#
#         markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
#         btn1 = types.KeyboardButton('📸 Добавить фото')
#         btn2 = types.KeyboardButton('🚀 Без фото')
#         markup.add(btn1, btn2)
#
#         msg = bot.send_message(
#             message.chat.id,
#             f'📱 Telegram: *{telegram}*\n\n*Хочешь добавить фото к анкете?*',
#             parse_mode='Markdown',
#             reply_markup=markup
#         )
#         bot.register_next_step_handler(msg, process_photo_choice)
#     except Exception as e:
#         print(f"Ошибка в process_telegram: {e}")
#         bot.send_message(message.chat.id, '❌ Произошла ошибка. Начни заново: /start')


# Шаг 7: выбор - добавлять фото или нет
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


# Шаг 8: обработка фото
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
            (user_id, name, age, gender, city, about, telegram, photo, is_active) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            user_id, data['name'], data['age'], data['gender'],
            data['city'], data['about'], data['telegram'], data.get('photo')
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
    btn3 = types.KeyboardButton('✏️ Изменить анкету')
    markup.add(btn1, btn2, btn3)

    bot.send_message(
        message.chat.id,
        '🎉 *Анкета создана!* Теперь ты можешь:\n\n• 📝 Посмотреть свою анкету\n• 👀 Найти другие анкеты\n• ✏️ Изменить свою анкету',
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
        user_id, name, age, gender, city, about, telegram, photo, is_active = profile

        profile_text = f"""
📝 *{'НОВАЯ АНКЕТА' if is_new else 'ТВОЯ АНКЕТА'}*

👤 *Имя:* {name}
🎂 *Возраст:* {age}
🚻 *Пол:* {gender}
🏙️ *Город:* {city}
📱 *Telegram:* {telegram}

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
    conn = sqlite3.connect('dating_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (message.from_user.id,))
    user_profile = cursor.fetchone()

    if not user_profile:
        bot.send_message(message.chat.id, '❌ Сначала создай свою анкету!')
        conn.close()
        return

    cursor.execute('''
        SELECT * FROM profiles 
        WHERE user_id != ? AND is_active = 1 
        ORDER BY RANDOM() LIMIT 10
    ''', (message.from_user.id,))
    profiles = cursor.fetchall()
    conn.close()

    if not profiles:
        bot.send_message(message.chat.id, '😔 Пока нет других анкет\nБудь первым, кто найдет пару!')
        return

    user_search_data[message.from_user.id] = {
        'profiles': profiles,
        'current_index': 0
    }

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
        del user_search_data[user_id]
        return

    profile = profiles[index]
    user_id, name, age, gender, city, about, telegram, photo, is_active = profile

    profile_text = f"""
👤 *Анкета {index + 1}/{len(profiles)}*

*Имя:* {name}
*Возраст:* {age}
*Пол:* {gender}
*Город:* {city}
*Telegram:* {telegram}

*О себе:*
{about}
    """

    markup = types.InlineKeyboardMarkup()
    btn_like = types.InlineKeyboardButton('❤️ Лайк', callback_data=f'like_{user_id}')
    btn_next = types.InlineKeyboardButton('➡️ Дальше', callback_data='next')
    btn_report = types.InlineKeyboardButton('🚫 Пожаловаться', callback_data=f'report_{user_id}')
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


# Обработка callback-ов
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data.startswith('like_'):
        user_id = int(call.data.split('_')[1])
        bot.answer_callback_query(call.id, '❤️ Лайк отправлен!')

    elif call.data == 'next':
        user_id = call.from_user.id
        if user_id in user_search_data:
            user_search_data[user_id]['current_index'] += 1
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_next_profile(call.message)

    elif call.data.startswith('report_'):
        bot.answer_callback_query(call.id, '🚫 Жалоба отправлена модератору')


# Запуск бота
if __name__ == '__main__':
    logger.info("🔄 Инициализация бота...")
    init_db()

    # Если на Render - используем вебхуки
    if os.environ.get('RENDER'):
        logger.info("🌐 Режим Render - настройка вебхуков...")

        time.sleep(3)

        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            webhook_url = f"{render_url}/webhook"
            try:
                bot.remove_webhook()
                time.sleep(1)
                bot.set_webhook(url=webhook_url)
                logger.info(f"✅ Вебхук установлен: {webhook_url}")
            except Exception as e:
                logger.error(f"❌ Ошибка вебхука: {e}")

        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🚀 Запуск Flask на порту {port}")
        app.run(host='0.0.0.0', port=port)

    else:
        # Локальный запуск с поллингом
        logger.info("🖥️ Локальный запуск (поллинг)...")
        while True:
            try:
                bot.polling(none_stop=True, timeout=60)
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
                time.sleep(10)