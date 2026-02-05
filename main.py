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
    expectations = State()
    waiting_photo = State()
    plan_date = State()
    waiting_payment = State()
    waiting_post = State() # Для рассылки

# --- Вспомогательные функции ---
def get_db():
    if os.path.exists(config.DB_FILE) and os.path.getsize(config.DB_FILE) > 0:
        return pd.read_csv(config.DB_FILE)
    return pd.DataFrame()

def save_user(data, tg_id, username):
    df = get_db()
    new_data = {
        'tg_id': tg_id,
        'username': f"@{username}" if username else "N/A",
        'status': 'Awaiting Payment',
        'reg_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
        **data
    }
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_csv(config.DB_FILE, index=False)

def get_yes_no_kb():
    return ReplyKeyboardBuilder().button(text="Да").button(text="Нет").as_markup(resize_keyboard=True)

# --- РЕГИСТРАЦИЯ ---
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
    await m.answer("📸 Пришли своё фото для пропуска (картинкой):")
    await state.set_state(RegStates.waiting_photo)


@router.message(RegStates.waiting_photo, F.photo)
async def p_photo(m: types.Message, state: FSMContext):
    data = await state.get_data()
    # Чистим ФИО для имени файла
    safe_fio = re.sub(r'[^\w\s-]', '', data['fio']).strip().replace(' ', '_')

    file_info = await bot.get_file(m.photo[-1].file_id)
    dest = os.path.join(config.PHOTOS_DIR, f"{safe_fio}.jpg")
    await bot.download_file(file_info.file_path, dest)

    await state.update_data(photo_saved=dest)
    ddl = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").strftime("%d.%m.%Y")
    await m.answer(f"✅ Фото сохранено.\n\nКогда оплатишь? (Дедлайн: {ddl})\nФормат: ДД.ММ.ГГГГ")
    await state.set_state(RegStates.plan_date)


@router.message(RegStates.plan_date)
async def p_date(m: types.Message, state: FSMContext):
    try:
        plan_dt = datetime.strptime(m.text, "%d.%m.%Y")
        await state.update_data(plan_pay_date=m.text)
        data = await state.get_data()
        save_user(data, m.from_user.id, m.from_user.username)

        kb = ReplyKeyboardBuilder().button(text="✅ Я оплатил(а)").as_markup(resize_keyboard=True)
        await m.answer(f"Данные сохранены!\n\n{config.REQUISITES}\n\nКак оплатишь — кидай чек сюда!", reply_markup=kb)
        await state.set_state(RegStates.waiting_payment)
    except:
        await m.answer("❌ Напиши дату как 20.12.2025")


@router.message(RegStates.waiting_payment, F.photo | F.document)
async def p_receipt(m: types.Message):
    for aid in config.ADMIN_IDS:
        await bot.send_message(aid, f"🧾 **ЧЕК** от {m.from_user.id}\n`/confirm {m.from_user.id}`",
                               parse_mode="Markdown")
        await m.send_copy(chat_id=aid)
    await m.answer("Принято! Скоро подтвердим.")


# --- FAQ ---
@router.message(Command("faq"))
async def cmd_faq(m: types.Message):
    kb = InlineKeyboardBuilder()
    for q in config.FAQ_DATA.keys():
        kb.button(text=q, callback_data=f"faq_{list(config.FAQ_DATA.keys()).index(q)}")
    await m.answer("Частые вопросы 👇", reply_markup=kb.adjust(1).as_markup())


@router.callback_query(F.data.startswith("faq_"))
async def faq_ans(call: types.CallbackQuery):
    idx = int(call.data.split("_")[1])
    q = list(config.FAQ_DATA.keys())[idx]
    await call.message.answer(f"❓ **{q}**\n\n{config.FAQ_DATA[q]}", parse_mode="Markdown")
    await call.answer()


# --- АДМИН ПАНЕЛЬ ---
@router.message(Command("admin"))
async def adm_panel(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return

    msg = (
        "🛠 **АДМИН-ПАНЕЛЬ NAT'CO 26**\n\n"
        "**Команды:**\n"
        "• `/admin` — вызвать это меню\n"
        "• `/post` — создать пост для рассылки\n"
        "• `/confirm ID` — подтвердить оплату\n"
        "• `/delete ID` — удалить участника\n"
        "• `/stats` — быстрая статистика\n\n"
        "**Кнопки ниже:**"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="adm_stats")
    kb.button(text="📥 База (CSV)", callback_data="adm_export")
    kb.button(text="📸 Выгрузить все фото", callback_data="adm_photos")
    await m.answer(msg, reply_markup=kb.adjust(1).as_markup(), parse_mode="Markdown")


@router.callback_query(F.data == "adm_stats")
async def call_stats(c: types.CallbackQuery):
    df = get_db()
    total = len(df)
    paid = len(df[df['status'] == 'Confirmed'])
    await c.message.answer(f"📈 Всего заявок: {total}\n✅ Оплачено: {paid}")
    await c.answer()


@router.callback_query(F.data == "adm_photos")
async def call_photos(c: types.CallbackQuery):
    files = os.listdir(config.PHOTOS_DIR)
    if not files: return await c.answer("Фотографий нет")

    await c.message.answer(f"📤 Начинаю выгрузку {len(files)} фото...")
    for f in files:
        photo = types.FSInputFile(os.path.join(config.PHOTOS_DIR, f))
        await bot.send_photo(c.from_user.id, photo, caption=f"👤 {f}")
        await asyncio.sleep(0.05)
    await c.answer()


# --- РАССЫЛКА ПОСТОВ ---
@router.message(Command("post"))
async def adm_post_start(m: types.Message, state: FSMContext):
    if m.from_user.id not in config.ADMIN_IDS: return
    await m.answer("Пришли сообщение (текст/фото/видео) для рассылки. Я покажу превью.")
    await state.set_state(RegStates.waiting_post)


@router.message(RegStates.waiting_post)
async def adm_post_preview(m: types.Message, state: FSMContext):
    await state.update_data(post_id=m.message_id, post_chat=m.chat.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 ОТПРАВИТЬ ВСЕМ", callback_data="broadcast_go")
    kb.button(text="❌ ОТМЕНА", callback_data="broadcast_cancel")
    await m.answer("ПРЕВЬЮ ПОСТА:")
    await m.copy_to(chat_id=m.chat.id)
    await m.answer("Рассылаем?", reply_markup=kb.adjust(1).as_markup())


@router.callback_query(F.data == "broadcast_go")
async def broadcast_go(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    df = get_db()
    uids = df['tg_id'].unique()

    await c.message.edit_text(f"🚀 Рассылка на {len(uids)} чел...")
    for uid in uids:
        try:
            await bot.copy_message(uid, data['post_chat'], data['post_id'])
            await asyncio.sleep(0.05)
        except:
            pass
    await c.message.answer("✅ Готово!")
    await state.clear()


# --- УТИЛИТЫ ---
@router.message(Command("confirm"))
async def adm_confirm(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return
    uid = int(m.text.split()[1])
    df = get_db()
    df.loc[df['tg_id'] == uid, 'status'] = 'Confirmed'
    df.to_csv(config.DB_FILE, index=False)
    await bot.send_message(uid, "✨ Твоя оплата подтверждена!")
    await m.answer(f"✅ {uid} подтвержден")


@router.message(Command("delete"))
async def adm_delete(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return
    uid = int(m.text.split()[1])
    df = get_db()
    df = df[df['tg_id'] != uid]
    df.to_csv(config.DB_FILE, index=False)
    await m.answer(f"💀 Участник {uid} удален")


async def main():
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())