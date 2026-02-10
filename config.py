import os

TOKEN = "8276545596:AAEfbFRteSFa2JRIy7fZMmgIJhc1CKZf3oY"
ADMIN_IDS = [1661192784, 1029208933, 510501198, 1330932352, 920171351]

CONF_NAME = "Rus'co 26"
PAYMENT_DDL = "2026-02-23"  # Дедлайн оплаты (ГГГГ-ММ-ДД)
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
GS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1Wl4Lv76YglBwf7WCb4PW5K_fNzYErPYn-7WOmZ1XBBQ"
DB_FILE = "participants.csv"

