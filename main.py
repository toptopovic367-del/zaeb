import sqlite3
import logging
from telebot import TeleBot, types

# Настройка бота
bot = TeleBot('YOUR_BOT_TOKEN')


# База данных
def init_db():
    conn = sqlite3.connect('database.db')
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
            likes_sent TEXT DEFAULT '',
            likes_received TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()


init_db()

# Хранилище для временных данных
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

    bot.send_message(
        message.chat.id,
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я бот для знакомств. Вот что я умею:\n"
        "• Создать анкету 👤\n"
        "• Найти анкету 💕\n"
        "• Посмотреть мои лайки ❤️\n"
        "• Удалить анкету 🚫",
        reply_markup=markup
    )


# Создание анкеты
@bot.message_handler(func=lambda message: message.text == '👤 Создать анкету')
def create_profile(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Проверяем, есть ли уже анкета
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    existing_profile = cursor.fetchone()

    if existing_profile:
        bot.send_message(message.chat.id, "❌ У вас уже есть анкета!")
        conn.close()
        return

    user_data[user_id] = {}
    bot.send_message(message.chat.id, "Как тебя зовут?")
    bot.register_next_step_handler(message, process_name)

    conn.close()


def process_name(message):
    user_id = message.from_user.id
    user_data[user_id]['name'] = message.text
    bot.send_message(message.chat.id, "Сколько тебе лет?")
    bot.register_next_step_handler(message, process_age)


def process_age(message):
    try:
        user_id = message.from_user.id
        age = int(message.text)
        if age < 12 or age > 100:
            bot.send_message(message.chat.id, "❌ Введите реальный возраст (12-100)")
            bot.register_next_step_handler(message, process_age)
            return
        user_data[user_id]['age'] = age
        bot.send_message(message.chat.id, "Из какого ты города?")
        bot.register_next_step_handler(message, process_city)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число!")
        bot.register_next_step_handler(message, process_age)


def process_city(message):
    user_id = message.from_user.id
    user_data[user_id]['city'] = message.text
    bot.send_message(message.chat.id, "Расскажи о себе (хобби, интересы и т.д.)")
    bot.register_next_step_handler(message, process_bio)


def process_bio(message):
    user_id = message.from_user.id
    user_data[user_id]['bio'] = message.text
    bot.send_message(message.chat.id, "Отправь свое фото")
    bot.register_next_step_handler(message, process_photo)


def process_photo(message):
    user_id = message.from_user.id
    username = message.from_user.username

    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте фото!")
        bot.register_next_step_handler(message, process_photo)
        return

    # Сохраняем фото
    file_id = message.photo[-1].file_id
    user_data[user_id]['photo'] = file_id
    user_data[user_id]['username'] = username

    # Сохраняем в базу
    save_profile(user_id)

    # Показываем анкету
    show_profile(message.chat.id, user_id, is_own=True)


def save_profile(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    data = user_data[user_id]
    cursor.execute('''
        INSERT INTO users (user_id, username, name, age, city, photo, bio)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data['username'], data['name'], data['age'],
          data['city'], data['photo'], data['bio']))

    conn.commit()
    conn.close()

    # Очищаем временные данные
    if user_id in user_data:
        del user_data[user_id]

    bot.send_message(user_id, "✅ Анкета создана!")


# Поиск анкет
@bot.message_handler(func=lambda message: message.text == '💕 Найти анкету')
def find_profile(message):
    user_id = message.from_user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Ищем анкету, которую пользователь еще не лайкал
    cursor.execute('''
        SELECT * FROM users 
        WHERE user_id != ? 
        AND user_id NOT IN (
            SELECT value FROM json_each(
                (SELECT likes_sent FROM users WHERE user_id = ?)
            )
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
    user_id, username, name, age, city, photo, bio, likes_sent, likes_received = profile

    caption = (
        f"👤 {name}, {age}\n"
        f"🏙 {city}\n"
        f"📝 {bio}\n"
        f"👤 @{username if username else 'нет_username'}"
    )

    markup = types.InlineKeyboardMarkup()
    like_btn = types.InlineKeyboardButton('❤️ Лайк', callback_data=f'like_{user_id}')
    next_btn = types.InlineKeyboardButton('➡️ Дальше', callback_data='next_profile')
    markup.add(like_btn, next_btn)

    bot.send_photo(chat_id, photo, caption=caption, reply_markup=markup)


# Обработка лайков
@bot.callback_query_handler(func=lambda call: call.data.startswith('like_'))
def handle_like(call):
    liker_id = call.from_user.id
    liked_user_id = int(call.data.split('_')[1])

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Добавляем лайк в sent для лайкнувшего
    cursor.execute('SELECT likes_sent FROM users WHERE user_id = ?', (liker_id,))
    result = cursor.fetchone()
    current_likes_sent = result[0] if result[0] else '[]'

    import json
    likes_sent_list = json.loads(current_likes_sent)
    if liked_user_id not in likes_sent_list:
        likes_sent_list.append(liked_user_id)

    cursor.execute('UPDATE users SET likes_sent = ? WHERE user_id = ?',
                   (json.dumps(likes_sent_list), liker_id))

    # Добавляем лайк в received для лайкнутого
    cursor.execute('SELECT likes_received FROM users WHERE user_id = ?', (liked_user_id,))
    result = cursor.fetchone()
    current_likes_received = result[0] if result[0] else '[]'

    likes_received_list = json.loads(current_likes_received)
    if liker_id not in likes_received_list:
        likes_received_list.append(liker_id)

    cursor.execute('UPDATE users SET likes_received = ? WHERE user_id = ?',
                   (json.dumps(likes_received_list), liked_user_id))

    conn.commit()

    # Получаем username лайкнувшего
    cursor.execute('SELECT username FROM users WHERE user_id = ?', (liker_id,))
    liker_username = cursor.fetchone()[0]

    conn.close()

    # Отправляем уведомление лайкнутому пользователю ТОЛЬКО ЕСЛИ ЕСТЬ ВЗАИМНОСТЬ
    cursor.execute('SELECT likes_sent FROM users WHERE user_id = ?', (liked_user_id,))
    result = cursor.fetchone()
    liked_user_sent_likes = json.loads(result[0]) if result[0] else []

    if liker_id in liked_user_sent_likes:
        # ВЗАИМНЫЙ ЛАЙК - отправляем уведомление обоим
        bot.send_message(
            liked_user_id,
            f"💞 Взаимный лайк!\n"
            f"Вы понравились {call.from_user.first_name}! Напишите ему: @{liker_username}"
        )
        bot.send_message(
            liker_id,
            f"💞 Взаимный лайк!\n"
            f"Вы понравились пользователю! Напишите ему: @{username}"
        )
    else:
        # Обычный лайк - уведомление не отправляем
        bot.answer_callback_query(call.id, "❤️ Лайк отправлен!")

    # Показываем следующую анкету
    find_profile(call.message)


@bot.callback_query_handler(func=lambda call: call.data == 'next_profile')
def next_profile(call):
    find_profile(call.message)


# Показ анкеты
def show_profile(chat_id, user_id, is_own=False):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    conn.close()

    if not profile:
        bot.send_message(chat_id, "❌ Анкета не найдена!")
        return

    user_id, username, name, age, city, photo, bio, likes_sent, likes_received = profile

    caption = (
        f"👤 {name}, {age}\n"
        f"🏙 {city}\n"
        f"📝 {bio}"
    )

    if is_own:
        caption += f"\n\n❤️ Получено лайков: {len(likes_received) if likes_received else 0}"

    bot.send_photo(chat_id, photo, caption=caption)


# Мои лайки
@bot.message_handler(func=lambda message: message.text == '❤️ Мои лайки')
def show_my_likes(message):
    user_id = message.from_user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT likes_received FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        bot.send_message(message.chat.id, "❌ У вас еще нет лайков!")
        conn.close()
        return

    import json
    likes_received = json.loads(result[0])

    if not likes_received:
        bot.send_message(message.chat.id, "❌ У вас еще нет лайков!")
        conn.close()
        return

    # Показываем первую анкету из лайков
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (likes_received[0],))
    profile = cursor.fetchone()
    conn.close()

    if profile:
        show_liked_profile(message.chat.id, profile, likes_received, 0)
    else:
        bot.send_message(message.chat.id, "❌ Анкета не найдена!")


def show_liked_profile(chat_id, profile, likes_list, index):
    user_id, username, name, age, city, photo, bio, likes_sent, likes_received = profile

    caption = (
        f"❤️ Вас лайкнул:\n"
        f"👤 {name}, {age}\n"
        f"🏙 {city}\n"
        f"📝 {bio}\n"
        f"👤 @{username if username else 'нет_username'}"
    )

    markup = types.InlineKeyboardMarkup()

    if index > 0:
        prev_btn = types.InlineKeyboardButton('⬅️ Назад', callback_data=f'prev_like_{index - 1}')
        markup.add(prev_btn)

    if index < len(likes_list) - 1:
        next_btn = types.InlineKeyboardButton('➡️ Дальше', callback_data=f'next_like_{index + 1}')
        if markup.keyboard:
            markup.keyboard[0].append(next_btn)
        else:
            markup.add(next_btn)

    bot.send_photo(chat_id, photo, caption=caption, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith(('prev_like_', 'next_like_')))
def navigate_likes(call):
    action, index = call.data.split('_')[-2], int(call.data.split('_')[-1])

    user_id = call.from_user.id
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT likes_received FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        bot.answer_callback_query(call.id, "❌ Лайки не найдены!")
        return

    import json
    likes_list = json.loads(result[0])

    cursor.execute('SELECT * FROM users WHERE user_id = ?', (likes_list[index],))
    profile = cursor.fetchone()
    conn.close()

    if profile:
        show_liked_profile(call.message.chat.id, profile, likes_list, index)
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id, "❌ Анкета не найдена!")


# Удаление анкеты
@bot.message_handler(func=lambda message: message.text == '🚫 Удалить анкету')
def delete_profile(message):
    user_id = message.from_user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    conn.close()

    if not profile:
        bot.send_message(message.chat.id, "❌ У вас нет анкеты!")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Да, удалить')
    btn2 = types.KeyboardButton('❌ Отмена')
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        "⚠️ *Точно удалить анкету?*\n\nЭто действие нельзя отменить!",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text == 'Да, удалить')
def confirm_delete(message):
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE user_id = ?', (message.from_user.id,))
        conn.commit()
        conn.close()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('👤 Создать анкету')
        markup.add(btn1)

        bot.send_message(
            message.chat.id,
            "✅ Анкета удалена!",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка при удалении анкеты!")


@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def cancel_delete(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👤 Создать анкету')
    btn2 = types.KeyboardButton('💕 Найти анкету')
    btn3 = types.KeyboardButton('❤️ Мои лайки')
    btn4 = types.KeyboardButton('🚫 Удалить анкету')
    markup.add(btn1, btn2, btn3, btn4)

    bot.send_message(
        message.chat.id,
        "❌ Удаление отменено",
        reply_markup=markup
    )


# Запуск бота
if __name__ == '__main__':
    print("Бот запущен!")
    bot.polling(none_stop=True)or: {e}")