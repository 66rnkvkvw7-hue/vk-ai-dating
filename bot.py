import os
import sqlite3
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType


# =========================
# НАСТРОЙКИ
# =========================

VK_TOKEN = os.getenv("VK_TOKEN")

if not VK_TOKEN:
    raise RuntimeError("Не найден VK_TOKEN. Добавь токен в переменные окружения.")


# =========================
# БАЗА ДАННЫХ
# =========================

DB_NAME = "dating.db"

db = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    city TEXT,
    gender TEXT,
    about TEXT
)
""")

db.commit()


# =========================
# VK
# =========================

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)


def send(user_id, message):
    vk.messages.send(
        user_id=user_id,
        random_id=random.randint(1, 2147483647),
        message=message
    )


# =========================
# ПРОФИЛЬ
# =========================

def get_profile(user_id):
    cursor.execute(
        "SELECT name, age, city, gender, about FROM users WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()


def save_profile(user_id, name, age, city, gender, about):
    cursor.execute("""
        INSERT OR REPLACE INTO users
        (user_id, name, age, city, gender, about)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, name, age, city, gender, about))

    db.commit()


def find_profiles(user_id):
    profile = get_profile(user_id)

    if not profile:
        return []

    name, age, city, gender, about = profile

    cursor.execute("""
        SELECT user_id, name, age, city, gender, about
        FROM users
        WHERE user_id != ?
        AND city = ?
        AND age BETWEEN ? AND ?
        LIMIT 10
    """, (
        user_id,
        city,
        age - 5,
        age + 5
    ))

    return cursor.fetchall()


# =========================
# КОМАНДЫ
# =========================

def show_help(user_id):
    send(
        user_id,
        """💘 БОТ ЗНАКОМСТВ

Доступные команды:

❤️ Начать
👤 Моя анкета
✏️ Создать анкету
🔎 Найти пару
📖 Помощь

Пример:
Напиши «Создать анкету», чтобы начать знакомство."""
    )


def start(user_id):
    profile = get_profile(user_id)

    if profile:
        send(
            user_id,
            "❤️ С возвращением!\n\n"
            "Твоя анкета уже создана.\n\n"
            "🔎 Напиши «Найти пару», чтобы посмотреть анкеты."
        )
    else:
        send(
            user_id,
            "💘 Добро пожаловать в бот знакомств!\n\n"
            "Давай создадим твою анкету.\n\n"
            "Напиши:\n"
            "Создать анкету"
        )


def show_my_profile(user_id):
    profile = get_profile(user_id)

    if not profile:
        send(
            user_id,
            "У тебя пока нет анкеты 😔\n\n"
            "Напиши «Создать анкету»."
        )
        return

    name, age, city, gender, about = profile

    send(
        user_id,
        f"""👤 ТВОЯ АНКЕТА

Имя: {name}
Возраст: {age}
Город: {city}
Пол: {gender}

О себе:
{about}

❤️ Чтобы найти пару — напиши «Найти пару»."""
    )


# =========================
# СОЗДАНИЕ АНКЕТЫ
# =========================

registration_step = {}


def create_profile(user_id):
    registration_step[user_id] = {
        "step": "name"
    }

    send(
        user_id,
        "👤 Давай создадим анкету!\n\n"
        "Как тебя зовут?"
    )


def registration(user_id, text):
    data = registration_step[user_id]
    step = data["step"]

    if step == "name":
        data["name"] = text
        data["step"] = "age"

        send(
            user_id,
            "🎂 Сколько тебе лет?"
        )

    elif step == "age":
        try:
            age = int(text)

            if age < 18 or age > 100:
                send(
                    user_id,
                    "Возраст должен быть от 18 до 100 лет."
                )
                return

            data["age"] = age
            data["step"] = "city"

            send(
                user_id,
                "📍 Из какого ты города?"
            )

        except ValueError:
            send(
                user_id,
                "Напиши возраст цифрами. Например: 25"
            )

    elif step == "city":
        data["city"] = text
        data["step"] = "gender"

        send(
            user_id,
            "👫 Укажи свой пол:\n\n"
            "Мужчина\n"
            "Женщина"
        )

    elif step == "gender":
        if text.lower() not in ["мужчина", "женщина"]:
            send(
                user_id,
                "Напиши «Мужчина» или «Женщина»."
            )
            return

        data["gender"] = text
        data["step"] = "about"

        send(
            user_id,
            "📝 Расскажи немного о себе.\n\n"
            "Например:\n"
            "«Люблю путешествия, спорт и хорошую музыку»"
        )

    elif step == "about":
        data["about"] = text

        save_profile(
            user_id,
            data["name"],
            data["age"],
            data["city"],
            data["gender"],
            data["about"]
        )

        del registration_step[user_id]

        send(
            user_id,
            f"""❤️ АНКЕТА СОЗДАНА!

Имя: {data["name"]}
Возраст: {data["age"]}
Город: {data["city"]}

Теперь можешь искать знакомства 🔎

Напиши «Найти пару»."""
        )


# =========================
# ПОИСК ПАРЫ
# =========================

def find_match(user_id):
    profile = get_profile(user_id)

    if not profile:
        send(
            user_id,
            "Сначала создай анкету ❤️\n\n"
            "Напиши «Создать анкету»."
        )
        return

    matches = find_profiles(user_id)

    if not matches:
        send(
            user_id,
            "😔 Пока подходящих анкет не найдено.\n\n"
            "Попробуй позже — новые пользователи появляются постоянно."
        )
        return

    for match in matches:
        match_id, name, age, city, gender, about = match

        send(
            user_id,
            f"""❤️ ВОТ КОГО МЫ НАШЛИ

{name}, {age}

📍 {city}

📝 {about}

Если человек понравился — напиши:
«Хочу познакомиться»

ID анкеты: {match_id}"""
        )


# =========================
# ОБРАБОТКА СООБЩЕНИЙ
# =========================

def handle_message(user_id, text):
    text = text.strip()

    if user_id in registration_step:
        registration(user_id, text)
        return

    command = text.lower()

    if command in [
        "начать",
        "старт",
        "start",
        "привет"
    ]:
        start(user_id)

    elif command in [
        "помощь",
        "помоги",
        "help",
        "меню"
    ]:
        show_help(user_id)

    elif command in [
        "создать анкету",
        "создать",
        "анкета"
    ]:
        create_profile(user_id)

    elif command in [
        "моя анкета",
        "мой профиль",
        "профиль"
    ]:
        show_my_profile(user_id)

    elif command in [
        "найти пару",
        "найти",
        "знакомства",
        "поиск"
    ]:
        find_match(user_id)

    else:
        send(
            user_id,
            "🤔 Я пока не понял команду.\n\n"
            "Напиши «Помощь», чтобы посмотреть доступные команды."
        )


# =========================
# ЗАПУСК БОТА
# =========================

print("💘 VK Dating Bot запущен!")

for event in longpoll.listen():

    if event.type == VkEventType.MESSAGE_NEW and event.to_me:

        try:
            user_id = event.user_id
            text = event.text

            print(f"[{user_id}] {text}")

            handle_message(user_id, text)

        except Exception as error:
            print("Ошибка:", error)
