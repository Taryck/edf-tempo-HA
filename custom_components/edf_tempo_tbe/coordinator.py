"""Data coordinator for the EDF Tempo Rev TBE integration."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EdfTempoApiError,
    EdfTempoAuthError,
    EdfTempoClient,
    TempoCalendarData,
    TempoSeasonSummaryData,
)
from .const import (
    DOMAIN,
    MIDDAY_POLL_SLOTS,
    MIDDAY_POLL_WINDOW_END,
    MIN_SEASON_START_YEAR,
    OVERNIGHT_POLL_SLOTS,
    OVERNIGHT_POLL_WINDOW_END,
    PARIS_TIME_ZONE,
)
from .season_cache import EdfTempoSeasonCache, TempoSeasonCacheEntry, build_cache_entry

_LOGGER = logging.getLogger(__name__)

API_RETRY_INTERVAL = timedelta(minutes=5)


class EdfTempoDataUpdateCoordinator(DataUpdateCoordinator[TempoCalendarData]):
    """Coordinate EDF Tempo Rev TBE API updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: EdfTempoClient,
        season_cache: EdfTempoSeasonCache,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=API_RETRY_INTERVAL,
            always_update=False,
        )
        self.client = client
        self._season_cache = season_cache
        self._season_loads: dict[str, asyncio.Task[TempoSeasonCacheEntry]] = {}
        self._overnight_baseline_date: str | None = None
        self._overnight_baseline: TempoCalendarData | None = None
        self._midday_baseline_date: str | None = None
        self._midday_baseline: TempoCalendarData | None = None
        self._expired_snapshot_notified_for: str | None = None
        self._refresh_started_after_failure = False

    async def _async_setup(self) -> None:
        """Validate credentials before the first refresh."""
        try:
            await self.client.async_validate_credentials()
            _LOGGER.debug("EDF Tempo Rev TBE credentials validated successfully")
        except EdfTempoAuthError as err:
            _LOGGER.warning("EDF Tempo Rev TBE authentication failed during coordinator setup")
            self.config_entry.async_start_reauth(self.hass)
            raise UpdateFailed(f"Unable to authenticate with RTE: {err}") from err
        except EdfTempoApiError as err:
            _LOGGER.warning("EDF Tempo Rev TBE credential validation failed: %s", err)
            raise UpdateFailed(f"Unable to validate credentials: {err}") from err

    async def _async_update_data(self) -> TempoCalendarData:
        """Fetch data from the EDF Tempo Rev TBE API."""
        self._refresh_started_after_failure = not self.last_update_success
        # DataUpdateCoordinator keeps the last successful payload after an
        # update failure. Reuse it so the recovery refresh can still detect a
        # publication change and restore the correct window schedule.
        previous_data = self.data
        _LOGGER.debug("Refreshing EDF Tempo Rev TBE coordinator data")
        try:
            day_window = await self.client.async_get_tempo_days()
        except EdfTempoAuthError as err:
            self.update_interval = API_RETRY_INTERVAL
            _LOGGER.warning("EDF Tempo Rev TBE authentication failed during data refresh")
            self.config_entry.async_start_reauth(self.hass)
            raise UpdateFailed(f"Unable to authenticate with RTE: {err}") from err
        except EdfTempoApiError as err:
            self.update_interval = API_RETRY_INTERVAL
            _LOGGER.warning("EDF Tempo Rev TBE day colors refresh failed: %s", err)
            raise UpdateFailed(f"Unable to fetch Tempo day colors: {err}") from err

        season_refresh_failed = False
        try:
            season_summary = await self._async_get_current_season_summary(
                day_window.today, day_window.tomorrow
            )
        except (EdfTempoApiError, EdfTempoAuthError, OSError) as err:
            season_refresh_failed = True
            if isinstance(err, EdfTempoAuthError):
                self.config_entry.async_start_reauth(self.hass)
            season_summary = self._last_current_season_summary(previous_data)
            _LOGGER.warning(
                "EDF Tempo Rev TBE season summary refresh failed; retrying in %s seconds: %s",
                int(API_RETRY_INTERVAL.total_seconds()),
                err,
            )
        season_cache = getattr(self, "_season_cache", None)
        cached_season = (
            season_cache.get(season_summary.season_start)
            if season_cache is not None and season_summary is not None
            else None
        )
        if cached_season is not None and cached_season.summary == season_summary:
            summary_updated_at = cached_season.updated_at
        elif (
            previous_data is not None
            and previous_data.season_summary == season_summary
        ):
            summary_updated_at = previous_data.summary_updated_at
        else:
            summary_updated_at = None
        data = TempoCalendarData(
            today=day_window.today,
            tomorrow=day_window.tomorrow,
            season_summary=season_summary,
            fetched_at=datetime.now(PARIS_TIME_ZONE).isoformat(),
            summary_updated_at=summary_updated_at,
        )

        if season_refresh_failed:
            self.update_interval = API_RETRY_INTERVAL
        else:
            self.update_interval = self._compute_next_update_interval(data, previous_data)
        _LOGGER.debug(
            "EDF Tempo Rev TBE day colors refreshed: season_success=%s today=%s tomorrow=%s next_update_in=%ss",
            not season_refresh_failed,
            data.today.color_code,
            data.tomorrow.color_code,
            int(self.update_interval.total_seconds()),
        )

        return data

    def _last_current_season_summary(
        self, previous_data: TempoCalendarData | None
    ) -> TempoSeasonSummaryData | None:
        """Retain only a summary that belongs to the current season."""
        season_start = f"{self.current_season_start_year}-09-01"
        cached = self._season_cache.get(season_start)
        if cached is not None:
            return cached.summary
        previous_summary = previous_data.season_summary if previous_data is not None else None
        if previous_summary is not None and previous_summary.season_start == season_start:
            return previous_summary
        return None

    @callback
    def _async_refresh_finished(self) -> None:
        """Update entities when stale day data crosses a Paris date boundary."""
        if self.last_update_success:
            self._expired_snapshot_notified_for = None
            return

        today_key = datetime.now(PARIS_TIME_ZONE).date().isoformat()
        if (
            self._expired_snapshot_notified_for == today_key
            or (self.data is not None and self.data.today.date == today_key)
        ):
            return

        self._expired_snapshot_notified_for = today_key
        # Home Assistant notifies listeners itself on the first failure. It
        # skips them after consecutive failures, so only fill that gap here.
        if self._refresh_started_after_failure:
            self.async_update_listeners()

    async def _async_get_current_season_summary(self, today, tomorrow):
        """Return the current season summary using cache-first logic."""
        _LOGGER.debug(
            "Building current EDF Tempo Rev TBE season summary with today=%s tomorrow=%s",
            today.color_code,
            tomorrow.color_code,
        )
        cache_entry = await self.async_get_season_entry(self.current_season_start_year)
        cache_entry = await self._season_cache.async_update_current_season(
            cache_entry,
            today,
            tomorrow,
        )
        return cache_entry.summary

    async def async_get_season_entry(self, season_start_year: int) -> TempoSeasonCacheEntry:
        """Return a cache entry for the requested season, fetching it on demand if needed."""
        if season_start_year < MIN_SEASON_START_YEAR or season_start_year > self.current_season_start_year:
            raise EdfTempoApiError("Requested season is outside the supported range")

        season_start = datetime(season_start_year, 9, 1, tzinfo=PARIS_TIME_ZONE).date()
        season_end = datetime(season_start_year + 1, 8, 31, tzinfo=PARIS_TIME_ZONE).date()
        season_start_key = season_start.isoformat()

        cache_entry = self._season_cache.get(season_start_key)
        if cache_entry is None:
            task = self._season_loads.get(season_start_key)
            if task is None:
                task = asyncio.create_task(self._async_load_season(season_start, season_end))
                self._season_loads[season_start_key] = task
                task.add_done_callback(
                    lambda completed: self._season_load_finished(season_start_key, completed)
                )
            # A closing card must not cancel a download shared with other callers.
            cache_entry = await asyncio.shield(task)
        else:
            _LOGGER.debug("EDF Tempo Rev TBE season cache hit for %s", season_start_key)

        if (
            season_start_year == self.current_season_start_year
            and self.last_update_success
            and self.data is not None
        ):
            _LOGGER.debug("Refreshing current season cache entry from live day window")
            cache_entry = await self._season_cache.async_update_current_season(
                cache_entry,
                self.data.today,
                self.data.tomorrow,
            )

        return cache_entry

    async def _async_load_season(self, season_start: date, season_end: date) -> TempoSeasonCacheEntry:
        """Download and persist one missing season for all concurrent callers."""
        _LOGGER.debug("EDF Tempo Rev TBE season cache miss for %s", season_start)
        day_colors = await self.client.async_get_season_day_colors(season_start, season_end)
        entry = build_cache_entry(season_start.isoformat(), season_end.isoformat(), day_colors)
        await self._season_cache.async_set(entry)
        return entry

    @callback
    def _season_load_finished(
        self, season_start_key: str, task: asyncio.Task[TempoSeasonCacheEntry]
    ) -> None:
        """Release the shared task and retrieve errors even if all callers left."""
        if self._season_loads.get(season_start_key) is task:
            del self._season_loads[season_start_key]
        if not task.cancelled():
            task.exception()

    @property
    def current_season_start_year(self) -> int:
        """Return the current season start year."""
        now = datetime.now(PARIS_TIME_ZONE)
        season_start, _season_end = self.client._get_current_season_bounds(now)
        return season_start.year

    def _compute_next_update_interval(
        self,
        current_data: TempoCalendarData,
        previous_data: TempoCalendarData | None,
    ) -> timedelta:
        """Compute the delay until the next required polling slot."""
        now = datetime.now(PARIS_TIME_ZONE)
        self._refresh_window_baselines(now, current_data, previous_data)

        overnight_changed = self._has_overnight_update(current_data)
        overnight_interval = self._next_slot_delay(
            now,
            OVERNIGHT_POLL_SLOTS,
            OVERNIGHT_POLL_WINDOW_END,
            stop_polling=overnight_changed,
        )
        if overnight_interval is not None:
            _LOGGER.debug(
                "EDF Tempo Rev TBE next update scheduled in overnight window: %ss",
                int(overnight_interval.total_seconds()),
            )
            return overnight_interval

        midday_changed = self._has_midday_update(current_data)
        midday_interval = self._next_slot_delay(
            now,
            MIDDAY_POLL_SLOTS,
            MIDDAY_POLL_WINDOW_END,
            stop_polling=midday_changed,
        )
        if midday_interval is not None:
            _LOGGER.debug(
                "EDF Tempo Rev TBE next update scheduled in midday window: %ss",
                int(midday_interval.total_seconds()),
            )
            return midday_interval

        next_midnight = datetime.combine(
            now.date() + timedelta(days=1),
            OVERNIGHT_POLL_SLOTS[0],
            tzinfo=PARIS_TIME_ZONE,
        )
        next_interval = max(next_midnight - now, timedelta(minutes=1))
        _LOGGER.debug(
            "EDF Tempo Rev TBE next update scheduled for next overnight window in %ss",
            int(next_interval.total_seconds()),
        )
        return next_interval

    def _refresh_window_baselines(
        self,
        now: datetime,
        current_data: TempoCalendarData,
        previous_data: TempoCalendarData | None,
    ) -> None:
        """Capture the pre-window baseline for overnight and midday polling."""
        today_key = now.date().isoformat()

        overnight_end = datetime.combine(
            now.date(), OVERNIGHT_POLL_WINDOW_END, tzinfo=PARIS_TIME_ZONE
        )
        if now <= overnight_end and self._overnight_baseline_date != today_key:
            self._overnight_baseline_date = today_key
            self._overnight_baseline = previous_data or current_data
        elif now > overnight_end and self._overnight_baseline_date != today_key:
            self._overnight_baseline_date = today_key
            self._overnight_baseline = current_data

        midday_start = datetime.combine(now.date(), MIDDAY_POLL_SLOTS[0], tzinfo=PARIS_TIME_ZONE)
        midday_end = datetime.combine(now.date(), MIDDAY_POLL_WINDOW_END, tzinfo=PARIS_TIME_ZONE)
        if midday_start <= now <= midday_end and self._midday_baseline_date != today_key:
            self._midday_baseline_date = today_key
            self._midday_baseline = previous_data or current_data
        elif now > midday_end and self._midday_baseline_date != today_key:
            self._midday_baseline_date = today_key
            self._midday_baseline = current_data

    def _has_overnight_update(self, current_data: TempoCalendarData) -> bool:
        """Return True when the overnight window has produced a new daily state."""
        today_key = datetime.now(PARIS_TIME_ZONE).date().isoformat()
        if self._overnight_baseline is None or self._overnight_baseline_date != today_key:
            return False

        baseline = self._overnight_baseline
        return (
            baseline.today.color_code != current_data.today.color_code
            or baseline.today.date != current_data.today.date
            or baseline.tomorrow.color_code != current_data.tomorrow.color_code
            or baseline.tomorrow.date != current_data.tomorrow.date
        )

    def _has_midday_update(self, current_data: TempoCalendarData) -> bool:
        """Return True when the midday window has produced a new state."""
        today_key = datetime.now(PARIS_TIME_ZONE).date().isoformat()
        if self._midday_baseline is None or self._midday_baseline_date != today_key:
            return False

        baseline = self._midday_baseline
        return (
            baseline.today.color_code != current_data.today.color_code
            or baseline.tomorrow.color_code != current_data.tomorrow.color_code
            or baseline.tomorrow.date != current_data.tomorrow.date
        )

    def _next_slot_delay(
        self,
        now: datetime,
        slots: tuple,
        window_end: time,
        *,
        stop_polling: bool,
    ) -> timedelta | None:
        """Return the delay to the next polling slot for a window."""
        window_end_dt = datetime.combine(now.date(), window_end, tzinfo=PARIS_TIME_ZONE)
        if stop_polling and now <= window_end_dt:
            return None

        slot_datetimes = [
            datetime.combine(now.date(), slot, tzinfo=PARIS_TIME_ZONE) for slot in slots
        ]

        for slot in slot_datetimes:
            if now < slot:
                return slot - now

        if now <= window_end_dt and not stop_polling:
            next_day_first_slot = slot_datetimes[0] + timedelta(days=1)
            return next_day_first_slot - now

        return None
