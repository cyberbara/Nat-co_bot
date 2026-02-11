import asyncio
import logging
import pandas as pd
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config

# Настройки логирования
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.TOKEN)
dp = Dispatcher()
router = Router()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


class RegStates(StatesGroup):
    fio = State()
    dob = State()
    phone = State()
    vk_nick = State()  # Новый стейт
    lc_ig = State()
    position = State()
    needs_release = State()
    uni_name = State()
    english = State()
    allergies = State()
    is_vegan = State()
    diet_info = State()
    arrival_moscow = State()
    stay_place = State()
    expectations_cc = State()
    expectations_content = State()
    is_volunteer = State()
    # Разделенные согласия
    agree_pers_data = State()
    agree_privacy = State()
    agree_photo_video = State()

    plan_date = State()
    waiting_payment = State()
    waiting_post = State()


# --- Вспомогательные функции ---
def get_db():
    if os.path.exists(config.DB_FILE):
        try:
            return pd.read_csv(config.DB_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def validate_date(date_text):
    try:
        return datetime.strptime(date_text, "%d.%m.%Y").date()
    except ValueError:
        return None


async def save_to_gsheets(data):
    if not config.USE_GOOGLE_SHEETS: return
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(config.GS_KEY_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(config.GS_SHEET_URL).sheet1
        row = [datetime.now().strftime("%Y-%m-%d %H:%M")] + list(data.values())
        sheet.append_row(row)
    except Exception as e:
        logging.error(f"GSheets Error: {e}")


def get_inline_kb(options, prefix="sel_"):
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(text=opt, callback_data=f"{prefix}{opt}"[:64])
    return builder.adjust(1).as_markup()


# --- Хендлеры регистрации ---

@router.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer("Привет! Напиши свое ФИО:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegStates.fio)


@router.message(RegStates.fio)
async def p_fio(m: types.Message, state: FSMContext):
    await state.update_data(fio=m.text)
    await m.answer("Дата рождения (ДД.ММ.ГГГГ):")
    await state.set_state(RegStates.dob)


@router.message(RegStates.dob)
async def p_dob(m: types.Message, state: FSMContext):
    d = validate_date(m.text)
    if not d:
        await m.answer("❌ Неверный формат даты. Введи ДД.ММ.ГГГГ")
        return
    await state.update_data(dob=m.text)
    await m.answer("Номер телефона:")
    await state.set_state(RegStates.phone)


@router.message(RegStates.phone)
async def p_phone(m: types.Message, state: FSMContext):
    await state.update_data(phone=m.text, tg=f"@{m.from_user.username}")
    await m.answer("Напиши свой ВК ник:")
    await state.set_state(RegStates.vk_nick)


@router.message(RegStates.vk_nick)
async def p_vk(m: types.Message, state: FSMContext):
    await state.update_data(vk=m.text)
    lcs = list(config.LC_REQUISITES.keys()) + ["Другой"]
    await m.answer("Выбери свой LC / IG:", reply_markup=get_inline_kb(lcs, "lc_"))
    await state.set_state(RegStates.lc_ig)


@router.callback_query(F.data.startswith("lc_"))
async def sel_lc(call: types.CallbackQuery, state: FSMContext):
    lc = call.data.replace("lc_", "")
    await state.update_data(lc_ig=lc)
    await call.message.edit_text(f"Выбрано: {lc}\nТвоя позиция (Member/TL/EB/итд):")
    await state.set_state(RegStates.position)


@router.message(RegStates.position)
async def p_pos(m: types.Message, state: FSMContext):
    await state.update_data(pos=m.text)
    kb = ReplyKeyboardBuilder().button(text="Да").button(text="Нет").as_markup(resize_keyboard=True)
    await m.answer("Нужна справка в ВУЗ?", reply_markup=kb)
    await state.set_state(RegStates.needs_release)


@router.message(RegStates.needs_release)
async def p_rel(m: types.Message, state: FSMContext):
    opts = ["Начальный", "Средний", "Продвинутый"]
    if m.text.lower() == "да":
        await m.answer("Название ВУЗа:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.uni_name)
    elif m.text.lower() == "нет":
        await state.update_data(uni="—")
        await m.answer("Понял.", reply_markup=types.ReplyKeyboardRemove())
        await m.answer("Уровень английского:", reply_markup=get_inline_kb(opts))
        await state.set_state(RegStates.english)
    else:
        await m.answer("Пожалуйста, нажми кнопку Да или Нет.")


@router.message(RegStates.uni_name)
async def p_uni(m: types.Message, state: FSMContext):
    await state.update_data(uni=m.text)
    opts = ["Начальный", "Средний", "Продвинутый"]
    await m.answer("Уровень английского:", reply_markup=get_inline_kb(opts))
    await state.set_state(RegStates.english)


@router.callback_query(F.data.startswith("sel_"))
async def handle_sel(call: types.CallbackQuery, state: FSMContext):
    val = call.data.replace("sel_", "")
    st = await state.get_state()
    original_text = call.message.text

    if st == RegStates.english.state:
        await state.update_data(eng=val)
        await call.message.edit_text(f"{original_text}\n✅ Выбрано: {val}")
        await call.message.answer("Подскажи, есть ли у тебя аллергии на какие-либо продукты/запахи?")
        await state.set_state(RegStates.allergies)

    elif st == RegStates.arrival_moscow.state:
        await state.update_data(arr=val)
        opts = ["Хост", "Друзья", "Свое жилье", "Другое"]
        await call.message.edit_text(f"{original_text}\n✅ Выбрано: {val}")
        await call.message.answer("Где будешь жить?", reply_markup=get_inline_kb(opts))
        await state.set_state(RegStates.stay_place)

    elif st == RegStates.stay_place.state:
        await state.update_data(stay=val)
        await call.message.edit_text(f"{original_text}\n✅ Выбрано: {val}")
        await call.message.answer("Ожидания от команды оргов?")
        await state.set_state(RegStates.expectations_cc)

    # Логика согласий
    elif st == RegStates.agree_pers_data.state:
        await call.message.edit_text("✅ Согласие на обработку данных принято.")
        kb = InlineKeyboardBuilder().button(text="✅ Согласен", callback_data="sel_agree").as_markup()
        await call.message.answer("Согласие с [политикой конфиденциальности](https://example.com/privacy)",
                                  parse_mode="Markdown", reply_markup=kb)
        await state.set_state(RegStates.agree_privacy)

    elif st == RegStates.agree_privacy.state:
        await call.message.edit_text("✅ Согласие с политикой принято.")
        kb = InlineKeyboardBuilder().button(text="✅ Согласен", callback_data="sel_agree").as_markup()
        await call.message.answer("Согласие на фото и видеосъёмку", reply_markup=kb)
        await state.set_state(RegStates.agree_photo_video)

    elif st == RegStates.agree_photo_video.state:
        await call.message.edit_text("✅ Согласие на съемку принято.")
        deadline_str = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").strftime("%d.%m.%Y")
        await call.message.answer(
            f"Когда планируешь оплатить взнос?\n⚠️ Крайний срок: **{deadline_str}**\nВведите дату (ДД.ММ.ГГГГ):",
            parse_mode="Markdown")
        await state.set_state(RegStates.plan_date)

    await call.answer()


@router.message(RegStates.allergies)
async def p_alg(m: types.Message, state: FSMContext):
    await state.update_data(alg=m.text)
    kb = ReplyKeyboardBuilder().button(text="Да").button(text="Нет").as_markup(resize_keyboard=True)
    await m.answer("Напиши, если ты веган/вегетарианец", reply_markup=kb)
    await state.set_state(RegStates.is_vegan)


@router.message(RegStates.is_vegan)
async def p_vegan(m: types.Message, state: FSMContext):
    if m.text.lower() == "да":
        await m.answer("Что ты ешь/не ешь?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(RegStates.diet_info)
    elif m.text.lower() == "нет":
        await state.update_data(diet="Обычное")
        await m.answer("Окей, обычное питание.", reply_markup=types.ReplyKeyboardRemove())
        opts = ["В дни конфы", "За 1 день до", "Раньше"]
        await m.answer("Когда приедешь?", reply_markup=get_inline_kb(opts))
        await state.set_state(RegStates.arrival_moscow)
    else:
        await m.answer("Используй кнопки Да/Нет")


@router.message(RegStates.diet_info)
async def p_diet(m: types.Message, state: FSMContext):
    await state.update_data(diet=m.text)
    opts = ["В дни конфы", "За 1 день до", "Раньше"]
    await m.answer("Когда приедешь?", reply_markup=get_inline_kb(opts))
    await state.set_state(RegStates.arrival_moscow)


@router.message(RegStates.expectations_cc)
async def p_cc(m: types.Message, state: FSMContext):
    await state.update_data(cc=m.text)
    await m.answer("Ожидания от контента?")
    await state.set_state(RegStates.expectations_content)


@router.message(RegStates.expectations_content)
async def p_cont(m: types.Message, state: FSMContext):
    await state.update_data(cont=m.text)
    kb = ReplyKeyboardBuilder().button(text="Да").button(text="Нет").as_markup(resize_keyboard=True)
    await m.answer("Хочешь быть волонтером?", reply_markup=kb)
    await state.set_state(RegStates.is_volunteer)


@router.message(RegStates.is_volunteer)
async def p_vol(m: types.Message, state: FSMContext):
    if m.text.lower() not in ['да', 'нет']:
        await m.answer("Пожалуйста, выбери Да или Нет.")
        return
    await state.update_data(vol=m.text)
    await m.answer("Хорошо.", reply_markup=types.ReplyKeyboardRemove())

    # Первое согласие
    kb = InlineKeyboardBuilder().button(text="✅ Согласен", callback_data="sel_agree").as_markup()
    await m.answer("Согласие на [обработку персональных данных](https://example.com/data)",
                   parse_mode="Markdown", reply_markup=kb)
    await state.set_state(RegStates.agree_pers_data)


@router.message(RegStates.plan_date)
async def p_fin(m: types.Message, state: FSMContext):
    input_date = validate_date(m.text)
    try:
        deadline_date = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").date()
    except ValueError:
        deadline_date = datetime(2030, 1, 1).date()

    if not input_date:
        await m.answer("❌ Неверный формат. Введи ДД.ММ.ГГГГ")
        return
    if input_date > deadline_date:
        await m.answer(f"❌ Позже дедлайна ({deadline_date.strftime('%d.%m.%Y')}). Укажи другую дату.")
        return

    data = await state.get_data()
    data['plan_pay'] = m.text
    df = get_db()
    new_data = {'id': m.from_user.id, **data, 'status': 'Pending'}
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_csv(config.DB_FILE, index=False)
    await save_to_gsheets(data)

    user_lc = data.get('lc_ig', 'Other')
    reqs = config.LC_REQUISITES.get(user_lc, config.REQ_1)

    confirm_msg = (
        "✅ **РЕГИСТРАЦИЯ ПРИНЯТА!**\n\n"
        f"📅 Твой план оплаты: {m.text}\n"
        f"👇 **РЕКВИЗИТЫ ({user_lc}):**\n{reqs}\n\n"
        "Также спешим тебя заранее предупредить, что у нас действует система штрафов при отмене регистрации:\n\n"
        "0 ₽ — до 27.03.26\n"
        "710 ₽ — с 27.03 по 03.04.26\n"
        "2130 ₽ — с 03.04 по 10.04.26\n"
        "7100 ₽ — с 10.04 по 17.04.26\n\n"
        "💙 **После оплаты отправь, пожалуйста, чек в этот чат в pdf формате!**"
    )
    await m.answer(confirm_msg, parse_mode="Markdown")
    await state.set_state(RegStates.waiting_payment)

# --- Админ-команды ---

@router.message(Command("confirm"))
async def adm_confirm(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return
    try:
        parts = m.text.split()
        if len(parts) < 2:
            await m.answer("Используй: `/confirm ID`")
            return
        uid = int(parts[1])
        df = get_db()
        if not df.empty and uid in df['id'].values:
            df.loc[df['id'] == uid, 'status'] = 'Confirmed'
            df.to_csv(config.DB_FILE, index=False)
            await bot.send_message(uid, "🎉 **Оплата подтверждена!**\nУвидимся на конференции!", parse_mode="Markdown")
            await m.answer(f"✅ Участник {uid} подтвержден.")
    except Exception as e:
        await m.answer(f"Ошибка: {e}")


@router.message(Command("admin"))
async def adm_panel(m: types.Message):
    if m.from_user.id not in config.ADMIN_IDS: return
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Стата", callback_data="a_st")
    kb.button(text="📥 База", callback_data="a_ex")
    await m.answer("🛠 Админка:", reply_markup=kb.adjust(1).as_markup())


@router.callback_query(F.data == "a_st")
async def a_st(c: types.CallbackQuery):
    df = get_db()
    await c.message.answer(f"Всего заявок: {len(df)}")
    await c.answer()


@router.callback_query(F.data == "a_ex")
async def a_ex(c: types.CallbackQuery):
    if os.path.exists(config.DB_FILE):
        await c.message.answer_document(types.FSInputFile(config.DB_FILE))
    await c.answer()


@router.message(Command("post"))
async def adm_post(m: types.Message, state: FSMContext):
    if m.from_user.id in config.ADMIN_IDS:
        await m.answer("Пришли сообщение для рассылки:")
        await state.set_state(RegStates.waiting_post)


@router.message(RegStates.waiting_post)
async def post_go(m: types.Message, state: FSMContext):
    df = get_db()
    if df.empty:
        await m.answer("База пуста.")
        return
    uids = df['id'].unique()
    count = 0
    for u in uids:
        try:
            await m.copy_to(u)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await m.answer(f"Разослано на {count} чел.")
    await state.clear()

# --- Логика напоминаний ---
async def send_payment_reminders():
    # ... (код напоминаний без изменений)
    logging.info("Checking for payment reminders...")
    df = get_db()
    if df.empty or 'status' not in df.columns: return
    try:
        ddl_date = datetime.strptime(config.PAYMENT_DDL, "%Y-%m-%d").date()
        today = datetime.now().date()
        days_left = (ddl_date - today).days

        if days_left in [7, 3, 1]:
            pending_users = df[df['status'] == 'Pending']
            for _, user in pending_users.iterrows():
                user_id = user['id']
                user_lc = user.get('lc_ig', 'Other')
                reqs = config.LC_REQUISITES.get(user_lc, config.REQ_1)
                msg = f"🔔 Напоминание! До дедлайна {days_left} дн. Взнос: {config.REG_FEE}₽"
                try:
                    await bot.send_message(user_id, msg)
                    await asyncio.sleep(0.05)
                except Exception:
                    pass
    except Exception as e:
        logging.error(f"Reminder Error: {e}")

async def main():
    dp.include_router(router)
    scheduler.add_job(send_payment_reminders, 'cron', hour=11, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")