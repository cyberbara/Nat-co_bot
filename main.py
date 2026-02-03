import asyncio
import logging
import pandas as pd
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config

logging.basicConfig(level=logging.INFO)
router = Router()


class ConfReg(StatesGroup):
    fio = State()
    dob = State()
    phone = State()
    needs_release = State()
    uni_name = State()
    english = State()
    has_allergies = State()
    allergies_detail = State()
    is_vegan = State()
    diet_detail = State()
    expectations = State()
    wants_merch = State()
    merch_detail = State()
    plan_pay_date = State()
    waiting_for_payment = State()


# --- Инструменты ---

def get_yes_no_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да");
    builder.button(text="Нет")
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def save_to_db(data, tg_id, username):
    df = pd.read_csv(config.DB_FILE) if os.path.exists(config.DB_FILE) else pd.DataFrame()
    new_row = {
        'tg_id': tg_id,
        'username': f"@{username}" if username else "N/A",
        'status': 'Awaiting Payment',
        'reg_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
        **data
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(config.DB_FILE, index=False)


# --- Хендлеры регистрации ---

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(f"{config.WELCOME_MSG}\n\n**Введи свое ФИО:**", parse_mode="Markdown")
    await state.set_state(ConfReg.fio)


@router.message(ConfReg.fio)
async def proc_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text)
    await message.answer("Дата рождения (ДД.ММ.ГГГГ):")
    await state.set_state(ConfReg.dob)


@router.message(ConfReg.dob)
async def proc_dob(message: types.Message, state: FSMContext):
    await state.update_data(dob=message.text)
    await message.answer("Твой номер телефона:")
    await state.set_state(ConfReg.phone)


@router.message(ConfReg.phone)
async def proc_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Нужна ли тебе справка для университета?", reply_markup=get_yes_no_kb())
    await state.set_state(ConfReg.needs_release)


# Логика ветвления (Справка)
@router.message(ConfReg.needs_release)
async def proc_release(message: types.Message, state: FSMContext):
    if message.text.lower() == "да":
        await message.answer("Название твоего учебного заведения:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(ConfReg.uni_name)
    else:
        await state.update_data(uni_name="Не требуется")
        await message.answer("Твой уровень английского:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(ConfReg.english)


@router.message(ConfReg.uni_name)
async def proc_uni(message: types.Message, state: FSMContext):
    await state.update_data(uni_name=message.text)
    await message.answer("Твой уровень английского:")
    await state.set_state(ConfReg.english)


@router.message(ConfReg.english)
async def proc_eng(message: types.Message, state: FSMContext):
    await state.update_data(english=message.text)
    await message.answer("Есть ли у тебя аллергии?", reply_markup=get_yes_no_kb())
    await state.set_state(ConfReg.has_allergies)


# Логика ветвления (Аллергии)
@router.message(ConfReg.has_allergies)
async def proc_has_alg(message: types.Message, state: FSMContext):
    if message.text.lower() == "да":
        await message.answer("Опиши аллергии:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(ConfReg.allergies_detail)
    else:
        await state.update_data(allergies="Нет")
        await message.answer("Ты вегетарианец или веган?", reply_markup=get_yes_no_kb())
        await state.set_state(ConfReg.is_vegan)


@router.message(ConfReg.allergies_detail)
async def proc_alg_det(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    await message.answer("Ты вегетарианец или веган?", reply_markup=get_yes_no_kb())
    await state.set_state(ConfReg.is_vegan)


# Логика ветвления (Диета)
@router.message(ConfReg.is_vegan)
async def proc_vegan(message: types.Message, state: FSMContext):
    if message.text.lower() == "да":
        await message.answer("Примеры блюд, которые ты ешь:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(ConfReg.diet_detail)
    else:
        await state.update_data(diet="Обычное")
        await message.answer("Ожидания от конференции?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(ConfReg.expectations)


@router.message(ConfReg.diet_detail)
async def proc_diet_det(message: types.Message, state: FSMContext):
    await state.update_data(diet=message.text)
    await message.answer("Ожидания от конференции?")
    await state.set_state(ConfReg.expectations)


@router.message(ConfReg.expectations)
async def proc_exp(message: types.Message, state: FSMContext):
    await state.update_data(expectations=message.text)
    await message.answer("Интересует ли тебя мерч (CC Shop)?", reply_markup=get_yes_no_kb())
    await state.set_state(ConfReg.wants_merch)


# Логика ветвления (Мерч)
@router.message(ConfReg.wants_merch)
async def proc_merch(message: types.Message, state: FSMContext):
    if message.text.lower() == "да":
        await message.answer("Что бы ты хотел видеть в CC Shop?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(ConfReg.merch_detail)
    else:
        await state.update_data(merch="Нет")
        await ask_payment_date(message, state)


@router.message(ConfReg.merch_detail)
async def proc_merch_det(message: types.Message, state: FSMContext):
    await state.update_data(merch=message.text)
    await ask_payment_date(message, state)


# Валидация даты оплаты
async def ask_payment_date(message: types.Message, state: FSMContext):
    ddl = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").strftime("%d.%m.%Y")
    await message.answer(f"Когда ты планируешь оплатить участие?\n(Не позже дедлайна: {ddl})",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(ConfReg.plan_pay_date)


@router.message(ConfReg.plan_pay_date)
async def proc_pay_date(message: types.Message, bot: Bot, state: FSMContext):
    try:
        plan_dt = datetime.strptime(message.text, "%d.%m.%Y")
        ddl_dt = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d")
        if plan_dt > ddl_dt:
            return await message.answer(
                f"❌ Нельзя выбрать дату позже дедлайна ({ddl_dt.strftime('%d.%m.%Y')}). Попробуй еще раз:")

        await state.update_data(plan_pay_date=message.text)
        await finish_registration(message, bot, state)
    except:
        await message.answer("❌ Используй формат ДД.ММ.ГГГГ")


async def finish_registration(message: types.Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    save_to_db(data, message.from_user.id, message.from_user.username)

    # Оповещение админам
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                                   f"⚡️ **НОВАЯ ЗАЯВКА**\n👤 {data['fio']}\n📅 План оплаты: {data['plan_pay_date']}\n🆔 `{message.from_user.id}`",
                                   parse_mode="Markdown")
        except:
            pass

    kb = ReplyKeyboardBuilder()
    kb.button(text="✅ Я оплатил(а)")
    await message.answer(
        f"Данные сохранены! Взнос: {config.REG_FEE}₽\n\n{config.REQUISITES}\n\n"
        f"Если возникнут вопросы, пиши в поддержку: {config.SUPPORT_CONTACT}",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )
    await state.set_state(ConfReg.waiting_for_payment)


# Обработка чека
@router.message(ConfReg.waiting_for_payment, F.photo | F.document)
async def handle_receipt(message: types.Message, bot: Bot, state: FSMContext):
    for admin_id in config.ADMIN_IDS:
        await bot.send_message(admin_id,
                               f"🧾 **ЧЕК НА ПРОВЕРКУ** от {message.from_user.id}\n/confirm {message.from_user.id}")
        await message.send_copy(chat_id=admin_id)
    await message.answer("Принято! Мы проверим оплату и подтвердим участие.", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()


# --- Планировщик напоминаний ---

async def send_reminders(bot: Bot):
    if not os.path.exists(config.DB_FILE): return
    df = pd.read_csv(config.DB_FILE)
    today = datetime.now().date()
    ddl = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").date()
    days_left = (ddl - today).days

    msg = ""
    if days_left == 7:
        msg = config.REMINDER_7D
    elif days_left == 3:
        msg = config.REMINDER_3D
    elif days_left == 0:
        msg = config.REMINDER_0D

    if msg:
        unpaid = df[df['status'] == 'Awaiting Payment']
        for tid in unpaid['tg_id']:
            try:
                await bot.send_message(tid, msg)
            except:
                pass


async def main():
    bot = Bot(token=config.TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_reminders, 'cron', hour=10, minute=0, args=[bot])
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())