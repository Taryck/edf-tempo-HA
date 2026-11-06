"""Constants for the EDF Tempo Rev TBE integration."""

from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

DOMAIN = "edf_tempo_tbe"
MIN_SEASON_START_YEAR = 2015
DATA_COORDINATOR = "coordinator"

CARD_FILENAME = "card.js"
CARD_URL_PATH = "/edf_tempo_tbe/card.js"
LEGACY_CARD_URL_PATH = "/local/edf_tempo_tbe/card.js"
INTEGRATION_VERSION = "1.2.12"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

# 1) Heure de bascule tarifaire RTE (heure locale Europe/Paris).
CONF_TEMPO_SWITCH_TIME = "tempo_switch_time"
DEFAULT_TEMPO_SWITCH_TIME = "06:00"
# 2) Entités LTARF/NTARF de N Lixee, surveillées simultanément.
CONF_LIXEE_ENTITIES = "lixee_entities"
# 3) Le premier changement Lixee bloque les suivants (12 h par défaut).
CONF_LIXEE_LOCK_HOURS = "lixee_lock_hours"
DEFAULT_LIXEE_LOCK_HOURS = 12

PLATFORMS = ["sensor"]

DEFAULT_NAME = "EDF Tempo Rev TBE"

TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"
API_BASE_URL = "https://digital.iservices.rte-france.com"
TEMPO_CALENDARS_PATH = "/open_api/tempo_like_supply_contract/v1/tempo_like_calendars"

PARIS_TIME_ZONE = ZoneInfo("Europe/Paris")

POLL_INTERVAL_MINUTES = 30

MIDDAY_POLL_WINDOW_END = time(hour=13, minute=0)
MIDDAY_POLL_SLOTS = (
    time(hour=10, minute=40),
    time(hour=11, minute=10),
    time(hour=11, minute=40),
    time(hour=12, minute=0),
    time(hour=12, minute=30),
    time(hour=13, minute=0),
)

OVERNIGHT_POLL_WINDOW_END = time(hour=4, minute=0)
OVERNIGHT_POLL_SLOTS = (
    time(hour=0, minute=0),
    time(hour=0, minute=30),
    time(hour=1, minute=0),
    time(hour=1, minute=30),
    time(hour=2, minute=0),
    time(hour=2, minute=30),
    time(hour=3, minute=0),
    time(hour=3, minute=30),
    time(hour=4, minute=0),
)

ATTR_COLOR_CODE = "color_code"
ATTR_DATE = "date"
ATTR_FALLBACK = "fallback"
ATTR_UPDATED_DATE = "updated_date"
ATTR_SEASON_START = "season_start"
ATTR_SEASON_END = "season_end"
ATTR_TOTAL_PLACED = "total_placed"
ATTR_BLUE_DAYS = "blue_days"
ATTR_WHITE_DAYS = "white_days"
ATTR_RED_DAYS = "red_days"
ATTR_BLUE_TOTAL = "blue_total"
ATTR_WHITE_TOTAL = "white_total"
ATTR_RED_TOTAL = "red_total"

TEMPO_BLUE_TOTAL = 300
TEMPO_WHITE_TOTAL = 43
TEMPO_RED_TOTAL = 22
