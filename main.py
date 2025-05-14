import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = '7828065577:AAGOfwVgzCsJwYPKc7K32pZZPyG6ZBVOB_g'

bot = Bot(token=TOKEN)
dp = Dispatcher()

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
                        "/list - показать все напоминания\n"
                        "/delete [№] - удалить напоминание\n\n"
                        "📝 Примеры:\n"
                        "/remind_time 30м Позвонить маме\n"
                        "/remind_time 2ч15м Сделать ДЗ\n")

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





async def create_reminder(user_id, text, reminder_time):
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

@dp.message(Command(commands=['list']))
async def list_reminders(message: Message):
    try:
        user_id = message.from_user.id

        if user_id not in user_reminders or not user_reminders[user_id]:
            await message.reply(" У вас нет активных напоминаний.")
            return

        active_reminders = []
        expired_reminders = []
        current_time = datetime.now()

        for reminder_id in list(user_reminders[user_id]):
            if reminder_id in reminders:
                reminder = reminders[reminder_id]
                time_left = reminder['time'] - current_time

                reminder_info = f" №{reminder_id}: {reminder['text']}\n" \
                                f"    {reminder['time'].strftime('%d.%m.%Y в %H:%M')}\n" \
                                f"    Осталось: {format_timedelta(time_left)}"

                if time_left.total_seconds() > 0:
                    active_reminders.append(reminder_info)
                else:
                    expired_reminders.append(reminder_info)
                    del reminders[reminder_id]
                    user_reminders[user_id].remove(reminder_id)

        reply_text = ""
        if active_reminders:
            reply_text += " Активные напоминания:\n\n" + "\n\n".join(active_reminders)
        if expired_reminders:
            if reply_text:
                reply_text += "\n\n"
            reply_text += " Просроченные напоминания:\n\n" + "\n\n".join(expired_reminders)

        if len(reply_text) > 4000:
            parts = [reply_text[i:i + 4000] for i in range(0, len(reply_text), 4000)]
            for part in parts:
                await message.reply(part)
                await asyncio.sleep(0.5)
        else:
            await message.reply(reply_text if reply_text else " Не удалось загрузить напоминания")

    except Exception as e:
        await message.reply(f" Произошла ошибка при получении списка: {str(e)}")


def format_timedelta(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} дн")
    if hours > 0:
        parts.append(f"{hours} ч")
    if minutes > 0:
        parts.append(f"{minutes} мин")
    if seconds > 0 and not (days or hours):
        parts.append(f"{seconds} сек")

    return " ".join(parts) if parts else "менее минуты"


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