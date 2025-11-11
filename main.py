import sqlite3
import json
from telebot import TeleBot, types

bot = TeleBot('8273843209:AAGhlZI8WbEYsMGmulBnxxtH6qJ_eFyMKs8')


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            age INTEGER,
            city TEXT,
            photo TEXT,
            bio TEXT,
            latitude REAL,
            longitude REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liker_id INTEGER,
            liked_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()


init_db()

user_data = {}


# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👤 Создать анкету')
    btn2 = types.KeyboardButton('💕 Найти анкету')
    btn3 = types.KeyboardButton('❤️ Мои лайки')
    btn4 = types.KeyboardButton('🚫 Удалить анкету')
    markup.add(btn1, btn2, btn3, btn4)

    bot.send_message(message.chat.id, "Привет! Я бот для знакомств.", reply_markup=markup)


# Создание анкеты
@bot.message_handler(func=lambda message: message.text == '👤 Создать анкету')
def create_profile(message):
    user_id = message.from_user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "❌ У вас уже есть анкета!")
        conn.close()
        return
    conn.close()

    user_data[user_id] = {}
    bot.send_message(message.chat.id, "Как тебя зовут?")
    bot.register_next_step_handler(message, process_name)


def process_name(message):
    user_id = message.from_user.id
    user_data[user_id]['name'] = message.text
    bot.send_message(message.chat.id, "Сколько тебе лет?")
    bot.register_next_step_handler(message, process_age)


def process_age(message):
    user_id = message.from_user.id
    try:
        age = int(message.text)
        user_data[user_id]['age'] = age
        bot.send_message(message.chat.id, "Из какого ты города?")
        bot.register_next_step_handler(message, process_city)
    except:
        bot.send_message(message.chat.id, "Введите число!")
        bot.register_next_step_handler(message, process_age)


def process_city(message):
    user_id = message.from_user.id
    user_data[user_id]['city'] = message.text

    # Предлагаем отправить геолокацию
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    location_btn = types.KeyboardButton("📍 Отправить геолокацию", request_location=True)
    skip_btn = types.KeyboardButton("⏭ Пропустить")
    markup.add(location_btn, skip_btn)

    bot.send_message(message.chat.id,
                     "📍 Хочешь отправить свою геолокацию? Это поможет находить анкеты рядом с тобой!",
                     reply_markup=markup)
    bot.register_next_step_handler(message, process_location)


def process_location(message):
    user_id = message.from_user.id

    if message.location:
        # Сохраняем координаты
        user_data[user_id]['latitude'] = message.location.latitude
        user_data[user_id]['longitude'] = message.location.longitude
        bot.send_message(message.chat.id, "📍 Геолокация сохранена!")
    elif message.text == "⏭ Пропустить":
        user_data[user_id]['latitude'] = None
        user_data[user_id]['longitude'] = None
        bot.send_message(message.chat.id, "📍 Геолокация не указана")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, используй кнопки ниже")
        bot.register_next_step_handler(message, process_location)
        return

    # Убираем специальную клавиатуру
    remove_markup = types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "Расскажи о себе", reply_markup=remove_markup)
    bot.register_next_step_handler(message, process_bio)


def process_bio(message):
    user_id = message.from_user.id
    user_data[user_id]['bio'] = message.text
    bot.send_message(message.chat.id, "Отправь свое фото")
    bot.register_next_step_handler(message, process_photo)


def process_photo(message):
    user_id = message.from_user.id

    if not message.photo:
        bot.send_message(message.chat.id, "Отправьте фото!")
        bot.register_next_step_handler(message, process_photo)
        return

    user_data[user_id]['photo'] = message.photo[-1].file_id
    user_data[user_id]['username'] = message.from_user.username

    # Сохраняем в базу
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    data = user_data[user_id]
    cursor.execute('''
        INSERT INTO users (user_id, username, name, age, city, photo, bio, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data['username'], data['name'], data['age'],
          data['city'], data['photo'], data['bio'],
          data.get('latitude'), data.get('longitude')))
    conn.commit()
    conn.close()

    del user_data[user_id]
    bot.send_message(message.chat.id, "✅ Анкета создана!")


# Поиск анкет
@bot.message_handler(func=lambda message: message.text == '💕 Найти анкету')
def find_profile(message):
    user_id = message.from_user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Ищем анкеты, которые пользователь еще не лайкал
    cursor.execute('''
        SELECT * FROM users 
        WHERE user_id != ? 
        AND user_id NOT IN (
            SELECT liked_id FROM likes WHERE liker_id = ?
        )
        LIMIT 1
    ''', (user_id, user_id))

    profile = cursor.fetchone()
    conn.close()

    if profile:
        show_profile_to_like(message.chat.id, profile, user_id)
    else:
        bot.send_message(message.chat.id, "❌ Анкет больше нет!")


def show_profile_to_like(chat_id, profile, viewer_id):
    user_id, username, name, age, city, photo, bio, latitude, longitude = profile

    caption = f"👤 {name}, {age}\n🏙 {city}\n📝 {bio}"

    # Добавляем информацию о геолокации если есть
    if latitude and longitude:
        caption += f"\n📍 Есть геолокация"

    markup = types.InlineKeyboardMarkup()
    like_btn = types.InlineKeyboardButton('❤️ Лайк', callback_data=f'like_{user_id}')
    next_btn = types.InlineKeyboardButton('➡️ Дальше', callback_data='next')

    # Добавляем кнопку для просмотра геолокации
    if latitude and longitude:
        location_btn = types.InlineKeyboardButton('📍 Посмотреть на карте', callback_data=f'location_{user_id}')
        markup.add(like_btn, location_btn)
        markup.add(next_btn)
    else:
        markup.add(like_btn, next_btn)

    bot.send_photo(chat_id, photo, caption=caption, reply_markup=markup)


# Обработка просмотра геолокации
@bot.callback_query_handler(func=lambda call: call.data.startswith('location_'))
def show_location(call):
    user_id = int(call.data.split('_')[1])

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT latitude, longitude, name FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result[0] and result[1]:
        latitude, longitude, name = result
        bot.send_location(call.message.chat.id, latitude, longitude)
        bot.answer_callback_query(call.id, f"📍 Местоположение {name}")
    else:
        bot.answer_callback_query(call.id, "❌ Геолокация недоступна")


# Обработка лайков
@bot.callback_query_handler(func=lambda call: call.data.startswith('like_'))
def handle_like(call):
    liker_id = call.from_user.id
    liked_id = int(call.data.split('_')[1])

    # Сохраняем лайк
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO likes (liker_id, liked_id) VALUES (?, ?)', (liker_id, liked_id))

    # Получаем информацию о том, кто лайкнул
    cursor.execute('SELECT username, name FROM users WHERE user_id = ?', (liker_id,))
    liker_info = cursor.fetchone()

    if liker_info:
        liker_username, liker_name = liker_info
        display_username = f"@{liker_username}" if liker_username else "пользователь"

        # Отправляем уведомление тому, кого лайкнули
        gender_text = "ей" if liker_name and liker_name.endswith(('а', 'я')) else "ему"

        notification_markup = types.InlineKeyboardMarkup()
        write_btn = types.InlineKeyboardButton(
            f"💌 Написать {gender_text}",
            url=f"https://t.me/{liker_username}" if liker_username else None
        )
        notification_markup.add(write_btn)

        try:
            bot.send_message(
                liked_id,
                f"💖 Тебя лайкнул(а) *{liker_name}*!\n\n"
                f"Напиши {gender_text}: {display_username}",
                parse_mode='Markdown',
                reply_markup=notification_markup
            )
        except:
            pass  # Если пользователь заблокировал бота

    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "❤️ Лайк отправлен!")
    find_profile(call.message)


@bot.callback_query_handler(func=lambda call: call.data == 'next')
def next_profile(call):
    find_profile(call.message)


# Мои лайки
@bot.message_handler(func=lambda message: message.text == '❤️ Мои лайки')
def show_my_likes(message):
    user_id = message.from_user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Кто лайкнул меня
    cursor.execute('''
        SELECT u.* FROM users u 
        JOIN likes l ON u.user_id = l.liker_id 
        WHERE l.liked_id = ?
    ''', (user_id,))

    my_likers = cursor.fetchall()
    conn.close()

    if not my_likers:
        bot.send_message(message.chat.id, "❌ У вас еще нет лайков!")
        return

    for liker in my_likers:
        user_id, username, name, age, city, photo, bio, latitude, longitude = liker
        caption = f"❤️ Вас лайкнул:\n👤 {name}, {age}\n🏙 {city}\n📝 {bio}"

        if username:
            gender_text = "ей" if name and name.endswith(('а', 'я')) else "ему"
            caption += f"\n\n💌 Напиши {gender_text}: @{username}"

        bot.send_photo(message.chat.id, photo, caption=caption)


# Удаление анкеты
@bot.message_handler(func=lambda message: message.text == '🚫 Удалить анкету')
def delete_profile(message):
    user_id = message.from_user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))

    if not cursor.fetchone():
        bot.send_message(message.chat.id, "❌ У вас нет анкеты!")
        conn.close()
        return
    conn.close()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Да, удалить')
    btn2 = types.KeyboardButton('❌ Отмена')
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "Точно удалить анкету?", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == 'Да, удалить')
def confirm_delete(message):
    try:
        user_id = message.from_user.id
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM likes WHERE liker_id = ? OR liked_id = ?', (user_id, user_id))
        conn.commit()
        conn.close()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn = types.KeyboardButton('👤 Создать анкету')
        markup.add(btn)

        bot.send_message(message.chat.id, "✅ Анкета удалена!", reply_markup=markup)
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка!")


@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def cancel_delete(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👤 Создать анкету')
    btn2 = types.KeyboardButton('💕 Найти анкету')
    btn3 = types.KeyboardButton('❤️ Мои лайки')
    btn4 = types.KeyboardButton('🚫 Удалить анкету')
    markup.add(btn1, btn2, btn3, btn4)
    bot.send_message(message.chat.id, "Удаление отменено", reply_markup=markup)


# Запуск бота
if __name__ == '__main__':
    print("Бот запущен!")
    bot.polling(none_stop=True)