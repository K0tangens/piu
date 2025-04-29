import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# Токен вашего бота (замените на свой)
TOKEN = '7828065577:AAGOfwVgzCsJwYPKc7K32pZZPyG6ZBVOB_g'

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранение напоминаний
reminders = {}
user_reminders = {}


@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я бот для напоминаний.\n"
                        "Отправь /help для просмотра доступных команд")

@dp.message(Command(commands=[ 'help']))
async def send_welcome(message: Message):
    await message.reply("📌 Доступные команды:\n"
                        "/remind_time [время] [текст] - напомнить через время (например: 30м, 2ч15м, 1д)\n"
                        "/remind_date [дата] [время] [текст] - напомнить в конкретное время (например: 25.12 15:30, 15:30)\n"
                        "/list - показать все напоминания\n"
                        "/delete [№] - удалить напоминание\n\n"
                        "📝 Примеры:\n"
                        "/remind_time 30м Позвонить маме\n"
                        "/remind_time 2ч15м Сделать ДЗ\n"
                        "/remind_date 25.12 15:30 Купить подарки\n"
                        "/remind_date 15:30 Пообедать")

@dp.message(Command(commands=['remind_time']))
async def set_timed_reminder(message: Message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError("Ой! Кажется, вы неправильно ввели данные! Попробуйте еще раз")

        _, time_str, reminder_text = parts
        time_delta = parse_time(time_str)
        reminder_time = datetime.now() + time_delta

        await create_reminder(message.from_user.id, reminder_text, reminder_time)
        await message.reply(f"Напоминание создано!\n"
                            f"Через {time_str} я напомню {reminder_text}")

    except Exception as e:
        await message.reply(f"Ошибка {e}\nФормат: /remind_time 30м Напоминание")


@dp.message(Command(commands=['remind_date']))
async def set_dated_reminder(message: Message):
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 3:
            raise ValueError("Ой! Кажется, вы неправильно ввели данные! Попробуйте еще раз")

        _, date_str, time_str, *text_parts = parts
        reminder_text = " ".join(text_parts) if text_parts else "Напоминание"

        reminder_time = parse_datetime(date_str, time_str)
        if reminder_time < datetime.now():
            raise ValueError("Указанное время уже прошло")

        await create_reminder(message.from_user.id, reminder_text, reminder_time)

        await message.reply(f"Напоминание создано!\n"
                            f"{reminder_time.strftime('%д.%м в %Ч:%М')} я напомню"
                            f"{reminder_text}")

    except Exception as e:
        await message.reply(f"Ошибка: {e}\nФормат: /remind_date 25.12 15:30 Текст\n"
                            "Или: /remind_date 15:30 Текст")


async def create_reminder(user_id, text, reminder_time):
    """Создает напоминание и запускает таймер"""
    reminder_id = str(len(reminders) + 1)
    time_left = (reminder_time - datetime.now()).total_seconds()

    reminders[reminder_id] = {
        'user_id': user_id,
        'text': text,
        'time': reminder_time,
        'timer': None
    }

    if user_id not in user_reminders:
        user_reminders[user_id] = []
    user_reminders[user_id].append(reminder_id)

    timer_task = asyncio.create_task(send_reminder(reminder_id, time_left))
    reminders[reminder_id]['timer'] = timer_task


def parse_time(time_str):
    """Парсит строку времени в формате 1h30m в timedelta"""
    time_delta = timedelta()
    num = 0

    for ch in time_str:
        if ch.isdigit():
            num = num * 10 + int(ch)
        else:
            if ch == 'д':
                time_delta += timedelta(days=num)
            elif ch == 'ч':
                time_delta += timedelta(hours=num)
            elif ch == 'м':
                time_delta += timedelta(minutes=num)
            else:
                raise ValueError(f"Ой! Вы ввели неправильную меру времени {ch}")
            num = 0

    if time_delta.total_seconds() <= 0:
        raise ValueError("Время должно быть больше нуля")

    return time_delta


def parse_datetime(date_str, time_str):
    """Парсит дату и время в datetime"""
    now = datetime.now()

    # Пытаемся разобрать время (может быть указано только время)
    try:
        if ':' in time_str:
            time_part = datetime.strptime(time_str, "%H:%M").time()
        else:
            raise ValueError("Неверный формат времени. Пожалуйста, используйте ЧЧ:ММ")

        # Если указана дата (день и месяц)
        if '.' in date_str:
            date_part = datetime.strptime(date_str, "%д.%м").date()
            return datetime.combine(date_part, time_part)
        else:
            # Только время - используем сегодня/завтра
            proposed_time = datetime.combine(now.date(), time_part)
            if proposed_time > now:
                return proposed_time
            else:
                return proposed_time + timedelta(days=1)

    except ValueError:
        # Если первый аргумент не дата, а время (когда дата не указана)
        if ':' in date_str:
            time_part = datetime.strptime(date_str, "%Ч:%М").time()
            proposed_time = datetime.combine(now.date(), time_part)
            if proposed_time > now:
                return proposed_time
            else:
                return proposed_time + timedelta(days=1)
        raise ValueError("Неверный формат даты/времени")


@dp.message(Command(commands=['list']))
async def list_reminders(message: Message):
    user_id = message.from_user.id
    if user_id not in user_reminders or not user_reminders[user_id]:
        await message.reply("Ой! Вы ничего сюда не добавили")
        return

    reply_text = "Ваши напоминания:\n\n"
    for reminder_id in user_reminders[user_id]:
        if reminder_id in reminders:
            rem = reminders[reminder_id]
            time_left = rem['time'] - datetime.now()

            if time_left.total_seconds() > 0:
                hours, remainder = divmod(time_left.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                reply_text += f"№{reminder_id}: {rem['text']}\n"
                reply_text += f"{rem['time'].strftime('%д.%м в %Ч:%М')} "
                reply_text += f"(Тик-Так! Осталось: {int(hours)}ч {int(minutes)}м)\n\n"
            else:
                reply_text += f"№{reminder_id}: {rem['text']}\n"
                reply_text += f"Должно было сработать: {rem['time'].strftime('%д.%м в %Ч:%М')}\n\n"

    await message.reply(reply_text)


@dp.message(Command(commands=['delete']))
async def delete_reminder(message: Message):
    try:
        user_id = message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            raise ValueError("Укажите № напоминания")

        reminder_id = parts[1].strip()

        if reminder_id not in reminders:
            raise ValueError("Напоминание с таким номером не найдено")

        if reminders[reminder_id]['user_id'] != user_id:
            raise ValueError("Это не ваше напоминание. Оставьте его другим пользователям!")

        if reminders[reminder_id]['timer']:
            reminders[reminder_id]['timer'].cancel()

        del reminders[reminder_id]
        user_reminders[user_id].remove(reminder_id)

        await message.reply(f"Напоминание №{reminder_id} удалено!")

    except Exception as e:
        await message.reply(f"Ошибка: {e}\nИспользуйте: /delete [№]")


async def send_reminder(reminder_id, delay):
    """Отправляет напоминание через указанное время"""
    try:
        await asyncio.sleep(delay)

        reminder = reminders.get(reminder_id)
        if reminder:
            await bot.send_message(
                chat_id=reminder['user_id'],
                text=f" Напоминаю {reminder['text']}"
            )

            user_id = reminder['user_id']
            if reminder_id in reminders:
                del reminders[reminder_id]
            if user_id in user_reminders and reminder_id in user_reminders[user_id]:
                user_reminders[user_id].remove(reminder_id)

    except Exception as e:
        print(f"Ошибка при отправке напоминания: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    print("Бот запущен...")
    asyncio.run(main())