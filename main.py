import asyncio
import logging
import pandas as pd
import os
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config

# Настройка логирования
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.TOKEN)
dp = Dispatcher()
router = Router()


class RegStates(StatesGroup):
    fio = State()
    dob = State()
    phone = State()
    needs_release = State()
    uni_name = State()
    english = State()
    has_allergies = State()
    allergies_info = State()
    is_vegan = State()
    vegan_info = State()
    expectations = State()
    wants_merch = State()
    merch_info = State()
    waiting_photo = State()
    plan_date = State()
    waiting_payment = State()


# --- Helpers ---
def get_yes_no_kb():
    return ReplyKeyboardBuilder().button(text="Да").button(text="Нет").as_markup(resize_keyboard=True,
                                                                                 one_time_keyboard=True)


def save_user_to_db(data, tg_id, username):
    df = pd.read_csv(config.DB_FILE) if os.path.exists(config.DB_FILE) else pd.DataFrame()
    new_data = {
        'tg_id': tg_id,
        'username': f"@{username}" if username else "N/A",
        'status': 'Awaiting Payment',
        'reg_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
        **data
    }
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_csv(config.DB_FILE, index=False)


# --- Handlers ---
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(config.WELCOME_MSG)
    await message.answer("Введите ваше ФИО (как в паспорте):")
    await state.set_state(RegStates.fio)


@router.message(RegStates.fio)
async def p_fio(m: types.Message, state: FSMContext):
    await state.update_data(fio=m.text)
    await m.answer("Дата рождения (ДД.ММ.ГГГГ):")
    await state.set_state(RegStates.dob)


@router.message(RegStates.dob)
async def p_dob(m: types.Message, state: FSMContext):
    await state.update_data(dob=m.text)
    await m.answer("Номер телефона:")
    await state.set_state(RegStates.phone)


@router.message(RegStates.phone)
async def p_phone(m: types.Message, state: FSMContext):
    await state.update_data(phone=m.text)
    await m.answer("Нужна ли справка для ВУЗа?", reply_markup=get_yes_no_kb())
    await state.set_state(RegStates.needs_release)


@router.message(RegStates.needs_release)
async def p_release(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Название вашего ВУЗа:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.uni_name)
    else:
        await state.update_data(uni_name="Не требуется")
        await m.answer("Уровень английского:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.english)


@router.message(RegStates.uni_name)
async def p_uni(m: types.Message, state: FSMContext):
    await state.update_data(uni_name=m.text)
    await m.answer("Ваш уровень английского:")
    await state.set_state(RegStates.english)


@router.message(RegStates.english)
async def p_eng(m: types.Message, state: FSMContext):
    await state.update_data(english=m.text)
    await m.answer("Есть ли у вас аллергии?", reply_markup=get_yes_no_kb())
    await state.set_state(RegStates.has_allergies)


@router.message(RegStates.has_allergies)
async def p_alg(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Опишите их:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.allergies_info)
    else:
        await state.update_data(allergies="Нет")
        await m.answer("Вы вегетарианец или веган?", reply_markup=get_yes_no_kb())
        await state.set_state(RegStates.is_vegan)


@router.message(RegStates.allergies_info)
async def p_alg_info(m: types.Message, state: FSMContext):
    await state.update_data(allergies=m.text)
    await m.answer("Вы вегетарианец или веган?", reply_markup=get_yes_no_kb())
    await state.set_state(RegStates.is_vegan)


@router.message(RegStates.is_vegan)
async def p_vegan(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Что вы не едите?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.vegan_info)
    else:
        await state.update_data(diet="Обычное")
        await m.answer("Ваши ожидания от конференции?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.expectations)


@router.message(RegStates.vegan_info)
async def p_vegan_info(m: types.Message, state: FSMContext):
    await state.update_data(diet=m.text)
    await m.answer("Ваши ожидания от конференции?")
    await state.set_state(RegStates.expectations)


@router.message(RegStates.expectations)
async def p_exp(m: types.Message, state: FSMContext):
    await state.update_data(expectations=m.text)
    await m.answer("Интересует ли мерч (CC Shop)?", reply_markup=get_yes_no_kb())
    await state.set_state(RegStates.wants_merch)


@router.message(RegStates.wants_merch)
async def p_merch(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Что бы вы хотели видеть в магазине?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.merch_info)
    else:
        await state.update_data(merch="Нет")
        await ask_photo(m, state)


@router.message(RegStates.merch_info)
async def p_merch_info(m: types.Message, state: FSMContext):
    await state.update_data(merch=m.text)
    await ask_photo(m, state)


# --- Фото ---
async def ask_photo(m, state):
    await m.answer("📸 Пришли своё фото для пропуска (как изображение).", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegStates.waiting_photo)


@router.message(RegStates.waiting_photo, F.photo)
async def p_photo(m: types.Message, state: FSMContext):
    data = await state.get_data()
    fio = data.get("fio", f"id_{m.from_user.id}")
    safe_fio = re.sub(r'[^\w\s-]', '', fio).strip().replace(' ', '_')

    file_info = await bot.get_file(m.photo[-1].file_id)
    file_path = os.path.join(config.PHOTOS_DIR, f"{safe_fio}.jpg")
    await bot.download_file(file_info.file_path, file_path)

    await state.update_data(photo_saved=file_path)

    ddl_str = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").strftime("%d.%m.%Y")
    await m.answer(
        f"✅ Фото сохранено.\n\nКогда планируешь оплатить? (Дедлайн: {ddl_str})\nНапиши в формате: ДД.ММ.ГГГГ")
    await state.set_state(RegStates.plan_date)


# --- Валидация Даты (Исправлено) ---
@router.message(RegStates.plan_date)
async def p_date(m: types.Message, state: FSMContext):
    input_text = m.text.strip()

    # 1. Проверка формата
    try:
        plan_dt = datetime.strptime(input_text, "%d.%m.%Y")
    except ValueError:
        return await m.answer("❌ Неверный формат! Напиши дату как: 20.12.2025")

    # 2. Проверка на дедлайн
    ddl_dt = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d")
    if plan_dt > ddl_dt:
        return await m.answer(f"❌ Позже дедлайна нельзя! Введи дату до {ddl_dt.strftime('%d.%m.%Y')}:")

    # 3. Сохранение, если всё ОК
    await state.update_data(plan_pay_date=input_text)
    data = await state.get_data()
    save_user_to_db(data, m.from_user.id, m.from_user.username)

    # Уведомление админам
    for aid in config.ADMIN_IDS:
        await bot.send_message(aid,
                               f"⚡️ **НОВАЯ ЗАЯВКА**\n👤 {data['fio']}\n📅 План оплаты: {input_text}\n🆔 `{m.from_user.id}`")

    kb = ReplyKeyboardBuilder().button(text="✅ Я оплатил(а)").as_markup(resize_keyboard=True)
    await m.answer(
        f"Данные сохранены! Взнос: {config.REG_FEE}₽\n\n{config.REQUISITES}\n\nКак оплатишь — жми кнопку и кидай чек сюда!",
        reply_markup=kb)
    await state.set_state(RegStates.waiting_payment)


@router.message(RegStates.waiting_payment, F.photo | F.document)
async def p_receipt(m: types.Message, state: FSMContext):
    for aid in config.ADMIN_IDS:
        await bot.send_message(aid, f"🧾 **ЧЕК** от {m.from_user.id}\n/confirm {m.from_user.id}")
        await m.send_copy(chat_id=aid)
    await m.answer(f"Принято! Поддержка: {config.SUPPORT_LINK}", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()


# --- Остальное (Админка и Планировщик) ---
@router.message(Command("confirm"))
async def adm_confirm(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return
    try:
        uid = int(m.text.split()[1])
        df = pd.read_csv(config.DB_FILE)
        df.loc[df['tg_id'] == uid, 'status'] = 'Confirmed'
        df.to_csv(config.DB_FILE, index=False)
        await bot.send_message(uid, f"✨ Ваше участие в {config.CONF_NAME} подтверждено!")
        await m.answer("Готово!")
    except:
        await m.answer("ID?")


async def send_reminders():
    if not os.path.exists(config.DB_FILE): return
    df = pd.read_csv(config.DB_FILE)
    today = datetime.now().date()
    ddl = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").date()
    diff = (ddl - today).days

    msg = ""
    if diff == 7:
        msg = config.REMIND_7D
    elif diff == 3:
        msg = config.REMIND_3D
    elif diff == 0:
        msg = config.REMIND_0D

    if msg:
        unpaid = df[df['status'] == 'Awaiting Payment']['tg_id']
        for tid in unpaid:
            try:
                await bot.send_message(tid, msg)
            except:
                pass


async def main():
    dp.include_router(router)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_reminders, 'cron', hour=10, minute=0)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())