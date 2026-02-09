import os

TOKEN = "твой_токен_бота"
ADMIN_IDS = [1661192784]

CONF_NAME = "Nat'co 26"
PAYMENT_DDL = "2025-12-21"  # Дедлайн оплаты (ГГГГ-ММ-ДД)
REG_FEE = 1500

# Реквизиты (те же группы)
REQ_1 = "💳 **РАЙФФАЙЗЕН**: `5379653044766234` (Елисеев А. Д.)"
REQ_2 = "💳 **СБЕРБАНК**: `2202202044156549` (Плешакова А. В.)"
REQ_3 = "💳 **СБЕРБАНК**: `2202206338732253` (Ибрагимова А.Р.)"

LC_REQUISITES = {
    "Moscow": REQ_1, "SPUEF": REQ_1, "YouLead": REQ_1, "EST": REQ_1,
    "Tyumen": REQ_2, "Ufa": REQ_2, "Kazan": REQ_2, "Tomsk": REQ_2,
    "Ekaterinburg": REQ_3, "E&G": REQ_3, "Voronezh": REQ_3
}

USE_GOOGLE_SHEETS = True
GS_KEY_FILE = "google_key.json"
GS_SHEET_URL = "https://docs.google.com/spreadsheets/d/ТВОЙ_ID"
DB_FILE = "participants.csv"

# Google Sheets
USE_GOOGLE_SHEETS = True
GS_KEY_FILE = "google_key.json"
GS_SHEET_URL = "https://docs.google.com/spreadsheets/d/ТВОЙ_ID_ТАБЛИЦЫ"

DB_FILE = "participants.csv"