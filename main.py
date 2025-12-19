import asyncio
import logging
import pandas as pd
from datetime import datetime
import os

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError

# --- 1. КОНСТАНТЫ ---
TOKEN = "8504650336:AAH-ZqQeR4W66t7pL7jhT04nRwpryI-gEV4"
ADMIN_IDS = [1661192784]
DB_FILE = "participants.csv"
BAR_FEE = 500
REQUISITES = "КАРТА СБЕРБАНКА: 2202 2069 1078 1926\nБАНК: ТИНЬКОФФ, ПО НОМЕРУ ТЕЛЕФОНА: +7 937 619 82-22"

logging.basicConfig(level=logging.INFO)
router = Router()


class Registration(StatesGroup):
    waiting_for_fio = State()
    waiting_for_age = State()
    waiting_for_allergies = State()
    waiting_for_preference = State()
    waiting_for_bar_type = State()
    waiting_for_payment_confirmation = State()


# --- 2. РАБОТА С БД (Без ЛК) ---
def load_db():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=[
        'telegram_id', 'username', 'fio', 'age', 'allergies',
        'preference', 'bar_type', 'status', 'reg_date'
    ])


def save_participant(data, tg_id, username):
    df = load_db()
    new_entry = {
        'telegram_id': tg_id,
        'username': f"@{username}" if username else "N/A",
        'fio': data.get('fio'),
        'age': data.get('age'),
        'allergies': data.get('allergies'),
        'preference': data.get('preference'),
        'bar_type': data.get('bar_type'),
        'status': 'Registered',
        'reg_date': datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    df = df[df['telegram_id'] != tg_id]
    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)


def update_status(tg_id, new_status):
    df = load_db()
    if tg_id in df['telegram_id'].values:
        df.loc[df['telegram_id'] == tg_id, 'status'] = new_status
        df.to_csv(DB_FILE, index=False)
        return True
    return False


# --- 3. КЛАВИАТУРЫ ---
def get_bar_type_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Алко-бар 🍷")
    builder.button(text="Б/А-бар 🥤")
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


# --- 4. ХЕНДЛЕРЫ РЕГИСТРАЦИИ (Твой текст) ---

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(f"""Привет, дорогой делегат! Если ты планируешь пользоваться безлимитным баром на вечеринке 12 января (как алкогольным, так и безалкогольным), то необходимо оставить заявку в этом боте!

Взнос за безлимитный бар составляет {BAR_FEE} руб.

В баре будет полноценное меню различных коктейлей, каждый найдет что-то на свой вкус!

А теперь приступим к реггистрации, напиши свое ФИО:""")
    await state.set_state(Registration.waiting_for_fio)


@router.message(Registration.waiting_for_fio)
async def process_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text)
    await message.answer("Сколько вам лет?")
    await state.set_state(Registration.waiting_for_age)


@router.message(Registration.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введите возраст числом:")
    await state.update_data(age=message.text)
    await message.answer("Есть ли у вас аллергии? (Если нет — напишите 'нет')")
    await state.set_state(Registration.waiting_for_allergies)


@router.message(Registration.waiting_for_allergies)
async def process_allergies(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    await message.answer("Какие напитки предпочитаете?")
    await state.set_state(Registration.waiting_for_preference)


@router.message(Registration.waiting_for_preference)
async def process_pref(message: types.Message, state: FSMContext):
    await state.update_data(preference=message.text)
    await message.answer("Какой тип бара выбираете?", reply_markup=get_bar_type_kb())
    await state.set_state(Registration.waiting_for_bar_type)


@router.message(Registration.waiting_for_bar_type)
async def process_bar_selection(message: types.Message, state: FSMContext):
    await state.update_data(bar_type=message.text)
    data = await state.get_data()

    # Сохраняем в БД сразу после выбора бара
    save_participant(data, message.from_user.id, message.from_user.username)

    kb = ReplyKeyboardBuilder()
    kb.button(text="✅ Я оплатил(а)")

    await message.answer(
        f"""Оплата взноса — {BAR_FEE}р

Пожалуйста, осуществи перевод на следующие реквизиты:.\n\n{REQUISITES}

ОБЯЗАТЕЛЬНО укажи в комментарии перевода:
ФИО (как в регистрации) + БАР

После перевода нажми кнопку ниже, чтобы сообщить нам об оплате""",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )
    await state.set_state(Registration.waiting_for_payment_confirmation)


@router.message(Registration.waiting_for_payment_confirmation, F.text == "✅ Я оплатил(а)")
async def payment_sent(message: types.Message):
    await message.answer("Спасибо! Теперь перешлите чек об оплате в чат (фото или файл)",
                         reply_markup=types.ReplyKeyboardRemove())


# Пересылка чека админу
@router.message(Registration.waiting_for_payment_confirmation, F.photo | F.document)
async def forward_receipt(message: types.Message, bot: Bot, state: FSMContext):
    update_status(message.from_user.id, "Pending Confirmation")

    user_info = (
        f"📩 **Новый чек от пользователя!**\n"
        f"ФИО: {message.from_user.full_name}\n"
        f"ID: `{message.from_user.id}`\n"
        f"Юзернейм: @{message.from_user.username or 'скрыт'}\n"
        f"Подтвердить: `/confirm {message.from_user.id}`"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, user_info, parse_mode="Markdown")
            await message.send_copy(chat_id=admin_id)
        except Exception:
            logging.error(f"Не удалось переслать файл админу")

    await message.reply("✅ Файл получен и передан администраторам для проверки.")
    await state.clear()


# --- 5. АДМИН-ПАНЕЛЬ ---

@router.message(Command("admin"))
async def admin_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Список всех", callback_data="view_all")
    kb.button(text="📢 Напомнить должникам", callback_data="remind_unpaid")
    kb.button(text="📂 Выгрузить CSV", callback_data="export_csv")
    kb.adjust(1)
    await message.answer("Админ-панель:", reply_markup=kb.as_markup())


@router.callback_query(F.data == "view_all")
async def view_all(callback: types.CallbackQuery):
    df = load_db()
    if df.empty: return await callback.answer("База пуста")
    text = "📝 **Участники:**\n\n"
    for _, row in df.iterrows():
        status = "✅" if row['status'] == 'Confirmed' else "⏳"
        text += f"{status} {row['fio']} ({row['bar_type']})\n"
    await callback.message.answer(text[:4000], parse_mode="Markdown")
    await callback.answer()


@router.message(Command("confirm"))
async def confirm_pay(message: types.Message, bot: Bot):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        uid = int(message.text.split()[1])
        if update_status(uid, "Confirmed"):
            await bot.send_message(uid, "✨ Ваша оплата подтверждена! До встречи в баре!")
            await message.answer(f"✅ Успешно для {uid}")
    except:
        await message.answer("Ошибка. Формат: `/confirm ID`", parse_mode="Markdown")


@router.callback_query(F.data == "export_csv")
async def export_csv(callback: types.CallbackQuery):
    if os.path.exists(DB_FILE):
        await callback.message.answer_document(types.FSInputFile(DB_FILE))
    await callback.answer()


@router.callback_query(F.data == "remind_unpaid")
async def remind_unpaid(callback: types.CallbackQuery, bot: Bot):
    df = load_db()
    unpaid = df[df['status'] == 'Registered']
    count = 0
    for tid in unpaid['telegram_id']:
        try:
            await bot.send_message(tid,
                                   "⚠️ Напоминаем, что вы не завершили регистрацию в бар. Пожалуйста, оплатите взнос и пришлите чек!")
            count += 1
        except:
            pass
    await callback.answer(f"Отправлено: {count}", show_alert=True)


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())