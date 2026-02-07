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
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

import config

# Настройка логирования
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.TOKEN)
dp = Dispatcher()
router = Router()


# --- Состояния ---
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

    # --- НОВЫЕ СОСТОЯНИЯ ---
    consent_data = State()  # Согласие на обработку данных
    consent_photo = State()  # Согласие на съемку
    # -----------------------

    expectations = State()
    waiting_photo = State()
    plan_date = State()
    waiting_payment = State()
    waiting_post = State()


# --- Вспомогательные функции ---
def get_db():
    if os.path.exists(config.DB_FILE) and os.path.getsize(config.DB_FILE) > 0:
        return pd.read_csv(config.DB_FILE)
    return pd.DataFrame()


def save_user(data, tg_id, username):
    df = get_db()
    # Удаляем лишние технические поля, если они есть
    clean_data = {k: v for k, v in data.items() if k not in ['photo_saved']}

    new_row = {
        'tg_id': tg_id,
        'username': f"@{username}" if username else "N/A",
        'status': 'Awaiting Payment',
        'reg_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
        **clean_data
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(config.DB_FILE, index=False)


def get_yes_no_kb():
    return ReplyKeyboardBuilder().button(text="Да").button(text="Нет").as_markup(resize_keyboard=True,
                                                                                 one_time_keyboard=True)


# --- РЕГИСТРАЦИЯ (ПОЛНЫЙ ЦИКЛ) ---

@router.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer(config.WELCOME_MSG)
    await m.answer("Введи свое ФИО (как в паспорте):")
    await state.set_state(RegStates.fio)


@router.message(RegStates.fio)
async def p_fio(m: types.Message, state: FSMContext):
    await state.update_data(fio=m.text)
    await m.answer("Твоя дата рождения (ДД.ММ.ГГГГ):")
    await state.set_state(RegStates.dob)


@router.message(RegStates.dob)
async def p_dob(m: types.Message, state: FSMContext):
    await state.update_data(dob=m.text)
    await m.answer("Твой номер телефона:")
    await state.set_state(RegStates.phone)


@router.message(RegStates.phone)
async def p_phone(m: types.Message, state: FSMContext):
    await state.update_data(phone=m.text)
    await m.answer("Нужна справка для ВУЗа?", reply_markup=get_yes_no_kb())
    await state.set_state(RegStates.needs_release)


@router.message(RegStates.needs_release)
async def p_release(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Напиши название ВУЗа:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.uni_name)
    else:
        await state.update_data(uni_name="Не требуется")
        await m.answer("Твой уровень английского:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.english)


@router.message(RegStates.uni_name)
async def p_uni(m: types.Message, state: FSMContext):
    await state.update_data(uni_name=m.text)
    await m.answer("Твой уровень английского:")
    await state.set_state(RegStates.english)


@router.message(RegStates.english)
async def p_eng(m: types.Message, state: FSMContext):
    await state.update_data(english=m.text)
    await m.answer("Есть ли у тебя аллергии?", reply_markup=get_yes_no_kb())
    await state.set_state(RegStates.has_allergies)


@router.message(RegStates.has_allergies)
async def p_alg(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Опиши их:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.allergies_info)
    else:
        await state.update_data(allergies="Нет")
        await m.answer("Ты вегетарианец/веган?", reply_markup=get_yes_no_kb())
        await state.set_state(RegStates.is_vegan)


@router.message(RegStates.allergies_info)
async def p_alg_info(m: types.Message, state: FSMContext):
    await state.update_data(allergies=m.text)
    await m.answer("Ты вегетарианец/веган?", reply_markup=get_yes_no_kb())
    await state.set_state(RegStates.is_vegan)


@router.message(RegStates.is_vegan)
async def p_vegan(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Напиши примеры блюд, которые ты ешь:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.vegan_info)
    else:
        await state.update_data(diet="Обычное")
        # ПЕРЕХОД К СОГЛАСИЯМ ВМЕСТО ОЖИДАНИЙ
        await ask_consent_data(m, state)


@router.message(RegStates.vegan_info)
async def p_vegan_info(m: types.Message, state: FSMContext):
    await state.update_data(diet=m.text)
    # ПЕРЕХОД К СОГЛАСИЯМ ВМЕСТО ОЖИДАНИЙ
    await ask_consent_data(m, state)


# --- НОВЫЙ БЛОК: СОГЛАСИЯ ---

async def ask_consent_data(m: types.Message, state: FSMContext):
    msg = (
        "📜 **Обработка данных**\n"
        "Даешь ли ты согласие на обработку персональных данных для организации конференции?"
    )
    await m.answer(msg, reply_markup=get_yes_no_kb(), parse_mode="Markdown")
    await state.set_state(RegStates.consent_data)


@router.message(RegStates.consent_data)
async def p_consent_data(m: types.Message, state: FSMContext):
    if m.text.lower() != "да":
        await m.answer("❌ К сожалению, без согласия на обработку данных мы не можем зарегистрировать тебя.",
                       reply_markup=types.ReplyKeyboardRemove())
        return await state.clear()

    await state.update_data(consent_personal_data="Да")

    msg = (
        "📸 **Фото и видео**\n"
        "Согласен(на) ли ты на фото- и видеосъемку во время мероприятия и публикацию материалов в соцсетях?"
    )
    await m.answer(msg, reply_markup=get_yes_no_kb(), parse_mode="Markdown")
    await state.set_state(RegStates.consent_photo)


@router.message(RegStates.consent_photo)
async def p_consent_photo(m: types.Message, state: FSMContext):
    consent = "Да" if m.text.lower() == "да" else "Нет"
    await state.update_data(consent_media=consent)

    # Возвращаемся к стандартному флоу
    await m.answer("Твои ожидания от конференции?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegStates.expectations)


# ----------------------------


@router.message(RegStates.expectations)
async def p_exp(m: types.Message, state: FSMContext):
    await state.update_data(expectations=m.text)
    await m.answer("📸 Пришли своё фото для пропуска (картинкой):")
    await state.set_state(RegStates.waiting_photo)


@router.message(RegStates.waiting_photo, F.photo)
async def p_photo(m: types.Message, state: FSMContext):
    data = await state.get_data()
    safe_fio = re.sub(r'[^\w\s-]', '', data['fio']).strip().replace(' ', '_')
    file_info = await bot.get_file(m.photo[-1].file_id)
    dest = os.path.join(config.PHOTOS_DIR, f"{safe_fio}.jpg")
    await bot.download_file(file_info.file_path, dest)
    await state.update_data(photo_saved=dest)

    ddl = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").strftime("%d.%m.%Y")
    await m.answer(f"✅ Фото сохранено.\n\nКогда оплатишь? (Дедлайн: {ddl})\nНапиши дату как: 20.12.2025")
    await state.set_state(RegStates.plan_date)


@router.message(RegStates.plan_date)
async def p_date(m: types.Message, state: FSMContext):
    try:
        plan_dt = datetime.strptime(m.text, "%d.%m.%Y")
        ddl_dt = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d")
        if plan_dt > ddl_dt:
            return await m.answer(f"❌ Позже дедлайна ({ddl_dt.strftime('%d.%m.%Y')}) нельзя! Введи другую дату:")

        await state.update_data(plan_pay_date=m.text)
        data = await state.get_data()

        # Сохраняем в БД
        save_user(data, m.from_user.id, m.from_user.username)

        # --- НОВОЕ: УВЕДОМЛЕНИЕ АДМИНУ О РЕГИСТРАЦИИ ---
        admin_msg = (
            f"🆕 **НОВАЯ АНКЕТА**\n"
            f"👤 {data['fio']}\n"
            f"📱 {data['phone']}\n"
            f"📅 Оплатит: {m.text}\n"
            f"📷 Согласие на съемку: {data.get('consent_media', 'Нет')}"
        )
        for aid in config.ADMIN_IDS:
            try:
                await bot.send_message(aid, admin_msg, parse_mode="Markdown")
            except:
                pass
        # ---------------------------------------------

        kb = ReplyKeyboardBuilder().button(text="✅ Я оплатил(а)").as_markup(resize_keyboard=True)
        await m.answer(f"Записал! Взнос: {config.REG_FEE}₽\n\n{config.REQUISITES}\n\nКидай чек сюда!", reply_markup=kb,
                       parse_mode="Markdown")
        await state.set_state(RegStates.waiting_payment)
    except Exception as e:
        logging.error(e)
        await m.answer("❌ Ошибка формата. Напиши дату как: 20.12.2025")


@router.message(RegStates.waiting_payment, F.photo | F.document)
async def p_receipt(m: types.Message):
    for aid in config.ADMIN_IDS:
        await bot.send_message(aid,
                               f"🧾 **НОВЫЙ ЧЕК**\nОт ID: `{m.from_user.id}`\nПодтвердить: `/confirm {m.from_user.id}`",
                               parse_mode="Markdown")
        await m.send_copy(chat_id=aid)
    await m.answer("Чек принят! Проверим и подтвердим в ближайшее время.")


# --- FAQ ---
@router.message(Command("faq"))
async def cmd_faq(m: types.Message):
    kb = InlineKeyboardBuilder()
    for q in config.FAQ_DATA.keys():
        kb.button(text=q, callback_data=f"faq_{list(config.FAQ_DATA.keys()).index(q)}")
    await m.answer("Выбери вопрос 👇", reply_markup=kb.adjust(1).as_markup())


@router.callback_query(F.data.startswith("faq_"))
async def faq_ans(call: types.CallbackQuery):
    idx = int(call.data.split("_")[1])
    q = list(config.FAQ_DATA.keys())[idx]
    await call.message.answer(f"❓ **{q}**\n\n{config.FAQ_DATA[q]}", parse_mode="Markdown")
    await call.answer()


# --- АДМИНКА ---
@router.message(Command("admin"))
async def adm_panel(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return

    msg = (
        "🛠 **АДМИН-ПАНЕЛЬ**\n\n"
        "• `/post` — создать пост для рассылки\n"
        "• `/confirm ID` — подтвердить оплату\n"
        "• `/delete ID` — удалить запись\n"
        "• `/stats` — мини-отчет"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="adm_stats")
    kb.button(text="📥 База (CSV)", callback_data="adm_export")
    kb.button(text="📸 Выгрузить все ФОТО", callback_data="adm_photos")
    await m.answer(msg, reply_markup=kb.adjust(1).as_markup(), parse_mode="Markdown")


@router.callback_query(F.data == "adm_stats")
async def call_stats(c: types.CallbackQuery):
    df = get_db()
    total = len(df)
    paid = len(df[df['status'] == 'Confirmed']) if not df.empty else 0
    await c.message.answer(f"📊 **Статистика:**\nВсего заявок: {total}\nПодтверждено: {paid}")
    await c.answer()


@router.callback_query(F.data == "adm_export")
async def call_export(c: types.CallbackQuery):
    if os.path.exists(config.DB_FILE):
        file = types.FSInputFile(config.DB_FILE)
        await c.message.answer_document(file, caption="Актуальная база участников 📁")
    else:
        await c.answer("База пока пуста!", show_alert=True)
    await c.answer()


@router.callback_query(F.data == "adm_photos")
async def call_photos(c: types.CallbackQuery):
    files = [f for f in os.listdir(config.PHOTOS_DIR) if f.endswith('.jpg')]
    if not files: return await c.answer("Фотографий нет.")

    await c.message.answer(f"📤 Выгружаю {len(files)} фото...")
    for f in files:
        photo = types.FSInputFile(os.path.join(config.PHOTOS_DIR, f))
        await bot.send_photo(c.from_user.id, photo, caption=f"👤 {f}")
        await asyncio.sleep(0.05)
    await c.answer()


# --- РАССЫЛКА ПОСТОВ ---
@router.message(Command("post"))
async def adm_post_start(m: types.Message, state: FSMContext):
    if m.from_user.id not in config.ADMIN_IDS: return
    await m.answer("Пришли пост (текст, фото, видео), который надо разослать. Я покажу превью.")
    await state.set_state(RegStates.waiting_post)


@router.message(RegStates.waiting_post)
async def adm_post_preview(m: types.Message, state: FSMContext):
    await state.update_data(p_id=m.message_id, p_chat=m.chat.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 РАЗОСЛАТЬ", callback_data="b_go")
    kb.button(text="❌ ОТМЕНА", callback_data="b_cancel")
    await m.answer("ТАК БУДЕТ ВЫГЛЯДЕТЬ ПОСТ:")
    await m.copy_to(chat_id=m.chat.id)
    await m.answer("Запускаем рассылку?", reply_markup=kb.adjust(1).as_markup())


@router.callback_query(F.data == "b_go")
async def broadcast_go(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    df = get_db()
    if df.empty: return await c.answer("Некому слать.")

    uids = df['tg_id'].unique()
    await c.message.edit_text(f"🚀 Рассылаю на {len(uids)} чел...")
    for uid in uids:
        try:
            await bot.copy_message(uid, data['p_chat'], data['p_id'])
            await asyncio.sleep(0.05)
        except:
            pass
    await c.message.answer("✅ Рассылка завершена!")
    await state.clear()


@router.callback_query(F.data == "b_cancel")
async def broadcast_cancel(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("❌ Рассылка отменена.")


# --- УТИЛИТЫ ---
@router.message(Command("confirm"))
async def adm_confirm(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return
    try:
        uid = int(m.text.split()[1])
        df = get_db()
        df.loc[df['tg_id'] == uid, 'status'] = 'Confirmed'
        df.to_csv(config.DB_FILE, index=False)
        await bot.send_message(uid, "✨ **Твоя оплата подтверждена!** Ждем тебя на конференции!")
        await m.answer(f"✅ Участник {uid} подтвержден.")
    except:
        await m.answer("Пример: `/confirm 123456`", parse_mode="Markdown")


@router.message(Command("delete"))
async def adm_delete(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return
    try:
        uid = int(m.text.split()[1])
        df = get_db()
        df = df[df['tg_id'] != uid]
        df.to_csv(config.DB_FILE, index=False)
        await m.answer(f"💀 Запись {uid} удалена.")
    except:
        await m.answer("Пример: `/delete 123456`", parse_mode="Markdown")


async def main():
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())