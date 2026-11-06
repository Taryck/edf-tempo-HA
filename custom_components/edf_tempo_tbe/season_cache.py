"""Season summary caching for EDF Tempo Rev TBE."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import COLOR_LABELS, TempoCalendarData, TempoDayData, TempoSeasonSummaryData
from .const import DOMAIN, PARIS_TIME_ZONE

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_season_cache"
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TempoSeasonCacheEntry:
    """Season cache entry containing the summary and known day-color map."""

    summary: TempoSeasonSummaryData
    day_colors: dict[str, str]
    updated_at: str | None = None


class EdfTempoSeasonCache:
    """Persist season summaries to avoid repeated full-season API calls."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the season cache store."""
        self._store: Store[dict[str, dict[str, object]]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )
        self._data: dict[str, dict[str, object]] = {}

    async def async_load(self) -> None:
        """Load cached data from storage."""
        try:
            stored = await self._store.async_load()
        except (OSError, TypeError, ValueError) as err:
            _LOGGER.warning("Ignoring unreadable EDF Tempo Rev TBE season cache: %s", err)
            self._data = {}
            return

        if not isinstance(stored, dict):
            if stored is not None:
                _LOGGER.warning("Ignoring invalid EDF Tempo Rev TBE season cache structure")
            self._data = {}
            return

        self._data = {
            season_start: payload
            for season_start, payload in stored.items()
            if isinstance(season_start, str)
            and _deserialize_entry(season_start, payload) is not None
        }
        invalid_entries = len(stored) - len(self._data)
        if invalid_entries:
            _LOGGER.warning(
                "Ignored %s invalid EDF Tempo Rev TBE season cache entries",
                invalid_entries,
            )
        _LOGGER.debug("Loaded EDF Tempo Rev TBE season cache with %s entries", len(self._data))

    def get(self, season_start: str) -> TempoSeasonCacheEntry | None:
        """Return a cached season entry."""
        return _deserialize_entry(season_start, self._data.get(season_start))

    def calendar_for(self, today: date) -> TempoCalendarData | None:
        """Build a dated offline snapshot from the current season cache."""
        start_year = today.year if today.month >= 9 else today.year - 1
        entry = self.get(f"{start_year}-09-01")
        if entry is None:
            return None

        def cached_day(day: date) -> TempoDayData:
            key = day.isoformat()
            color = entry.day_colors.get(key)
            return TempoDayData(key, color, COLOR_LABELS.get(color), False, None)

        return TempoCalendarData(
            today=cached_day(today),
            tomorrow=cached_day(today + timedelta(days=1)),
            season_summary=entry.summary,
            fetched_at="",
            summary_updated_at=entry.updated_at,
        )

    async def async_clear(self) -> None:
        """Clear cached seasons from memory and Home Assistant storage."""
        self._data.clear()
        await self._store.async_remove()
        _LOGGER.debug("Cleared EDF Tempo Rev TBE season cache")

    async def async_set(self, entry: TempoSeasonCacheEntry) -> None:
        """Persist a season entry."""
        self._data[entry.summary.season_start] = {
            "summary": asdict(entry.summary),
            "day_colors": entry.day_colors,
            "updated_at": entry.updated_at,
        }
        await self._store.async_save(self._data)
        _LOGGER.debug(
            "Saved EDF Tempo Rev TBE season cache entry for %s with %s known days",
            entry.summary.season_start,
            len(entry.day_colors),
        )

    async def async_update_current_season(
        self,
        entry: TempoSeasonCacheEntry,
        today: TempoDayData,
        tomorrow: TempoDayData,
    ) -> TempoSeasonCacheEntry:
        """Update the current season cache entry from fresh today/tomorrow values."""
        day_colors = dict(entry.day_colors)
        changed = False

        for day in (today, tomorrow):
            if day.color_code is None:
                continue
            if not (entry.summary.season_start <= day.date <= entry.summary.season_end):
                continue

            previous_color = day_colors.get(day.date)
            if previous_color != day.color_code:
                day_colors[day.date] = day.color_code
                changed = True

        if not changed:
            _LOGGER.debug(
                "No current-season cache update required for %s",
                entry.summary.season_start,
            )
            return entry

        updated_entry = TempoSeasonCacheEntry(
            summary=_build_summary(entry.summary.season_start, entry.summary.season_end, day_colors),
            day_colors=day_colors,
            updated_at=datetime.now(PARIS_TIME_ZONE).isoformat(),
        )
        await self.async_set(updated_entry)
        _LOGGER.debug(
            "Updated current EDF Tempo Rev TBE season cache for %s",
            entry.summary.season_start,
        )
        return updated_entry


def build_cache_entry(
    season_start: str,
    season_end: str,
    day_colors: dict[str, str],
) -> TempoSeasonCacheEntry:
    """Build a cache entry from a date->color map."""
    normalized_day_colors = {
        str(day): normalized_color
        for day, color in day_colors.items()
        if (normalized_color := str(color).upper()) in {"BLUE", "WHITE", "RED"}
    }
    return TempoSeasonCacheEntry(
        summary=_build_summary(season_start, season_end, normalized_day_colors),
        day_colors=normalized_day_colors,
        updated_at=datetime.now(PARIS_TIME_ZONE).isoformat(),
    )


def _deserialize_entry(
    season_start_key: str,
    payload: object,
) -> TempoSeasonCacheEntry | None:
    """Validate and deserialize one persisted cache entry."""
    if not isinstance(payload, dict):
        return None

    summary_payload = payload.get("summary")
    day_colors_payload = payload.get("day_colors")
    if not isinstance(summary_payload, dict) or not isinstance(day_colors_payload, dict):
        return None

    updated_at = payload.get("updated_at")
    if updated_at is not None:
        if not isinstance(updated_at, str):
            return None
        try:
            parsed_updated_at = datetime.fromisoformat(updated_at)
        except ValueError:
            return None
        if parsed_updated_at.tzinfo is None:
            return None

    required_text_fields = ("season_start", "season_end")
    required_number_fields = (
        "total_placed",
        "blue_days",
        "white_days",
        "red_days",
        "blue_total",
        "white_total",
        "red_total",
    )
    if any(not isinstance(summary_payload.get(field), str) for field in required_text_fields):
        return None
    if any(
        not isinstance(summary_payload.get(field), int)
        or isinstance(summary_payload.get(field), bool)
        or summary_payload[field] < 0
        for field in required_number_fields
    ):
        return None

    season_start = summary_payload["season_start"]
    season_end = summary_payload["season_end"]
    if season_start != season_start_key:
        return None
    try:
        start_date = date.fromisoformat(season_start)
        end_date = date.fromisoformat(season_end)
    except ValueError:
        return None
    if start_date > end_date:
        return None

    day_colors: dict[str, str] = {}
    for day_value, color in day_colors_payload.items():
        if not isinstance(day_value, str) or color not in {"BLUE", "WHITE", "RED"}:
            return None
        try:
            day_date = date.fromisoformat(day_value)
        except ValueError:
            return None
        if not start_date <= day_date <= end_date:
            return None
        day_colors[day_value] = color

    expected_summary = _build_summary(season_start, season_end, day_colors)
    if any(
        summary_payload[field] != getattr(expected_summary, field)
        for field in ("total_placed", "blue_days", "white_days", "red_days")
    ):
        return None

    return TempoSeasonCacheEntry(
        summary=TempoSeasonSummaryData(
            season_start=season_start,
            season_end=season_end,
            total_placed=summary_payload["total_placed"],
            blue_days=summary_payload["blue_days"],
            white_days=summary_payload["white_days"],
            red_days=summary_payload["red_days"],
            blue_total=summary_payload["blue_total"],
            white_total=summary_payload["white_total"],
            red_total=summary_payload["red_total"],
        ),
        day_colors=day_colors,
        updated_at=updated_at,
    )


def _build_summary(
    season_start: str,
    season_end: str,
    day_colors: dict[str, str],
) -> TempoSeasonSummaryData:
    """Build a season summary from its date->color map."""
    blue_days = sum(1 for color in day_colors.values() if color == "BLUE")
    white_days = sum(1 for color in day_colors.values() if color == "WHITE")
    red_days = sum(1 for color in day_colors.values() if color == "RED")

    return TempoSeasonSummaryData(
        season_start=season_start,
        season_end=season_end,
        total_placed=blue_days + white_days + red_days,
        blue_days=blue_days,
        white_days=white_days,
        red_days=red_days,
    )
