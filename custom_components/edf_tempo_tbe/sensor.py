"""Sensor platform for the EDF Tempo Rev TBE integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import TempoDayData, TempoSeasonSummaryData
from .const import (
    ATTR_BLUE_DAYS,
    ATTR_BLUE_TOTAL,
    ATTR_COLOR_CODE,
    ATTR_DATE,
    ATTR_FALLBACK,
    ATTR_RED_DAYS,
    ATTR_RED_TOTAL,
    ATTR_SEASON_END,
    ATTR_SEASON_START,
    ATTR_TOTAL_PLACED,
    ATTR_UPDATED_DATE,
    ATTR_WHITE_DAYS,
    ATTR_WHITE_TOTAL,
    DEFAULT_NAME,
    DOMAIN,
    PARIS_TIME_ZONE,
)
from .coordinator import EdfTempoDataUpdateCoordinator
from .effective import EffectiveTempoTracker


@dataclass(frozen=True, slots=True)
class EdfTempoSensorEntityDescription(SensorEntityDescription):
    """Describe an EDF Tempo Rev TBE sensor."""

    value_key: str = ""


TEMPO_COLOR_OPTIONS = ["blue", "white", "red", "unknown"]
REMAINING_DAY_FIELDS = {
    "remaining_red_days": ("red_days", "red_total"),
    "remaining_white_days": ("white_days", "white_total"),
    "remaining_blue_days": ("blue_days", "blue_total"),
}


SENSORS: tuple[EdfTempoSensorEntityDescription, ...] = (
    EdfTempoSensorEntityDescription(
        key="today",
        translation_key="today",
        device_class=SensorDeviceClass.ENUM,
        options=TEMPO_COLOR_OPTIONS,
        value_key="today",
    ),
    EdfTempoSensorEntityDescription(
        key="tomorrow",
        translation_key="tomorrow",
        device_class=SensorDeviceClass.ENUM,
        options=TEMPO_COLOR_OPTIONS,
        value_key="tomorrow",
    ),
    EdfTempoSensorEntityDescription(
        key="season_summary",
        translation_key="season_summary",
        value_key="season_summary",
    ),
    EdfTempoSensorEntityDescription(
        key="remaining_red_days",
        translation_key="remaining_red_days",
        native_unit_of_measurement="d",
        value_key="remaining_red_days",
    ),
    EdfTempoSensorEntityDescription(
        key="remaining_white_days",
        translation_key="remaining_white_days",
        native_unit_of_measurement="d",
        value_key="remaining_white_days",
    ),
    EdfTempoSensorEntityDescription(
        key="remaining_blue_days",
        translation_key="remaining_blue_days",
        native_unit_of_measurement="d",
        value_key="remaining_blue_days",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EDF Tempo Rev TBE sensors from a config entry."""
    coordinator: EdfTempoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # 3/4) Deux capteurs supplémentaires : couleur effective et origine de sa décision.
    tracker = EffectiveTempoTracker(hass, entry, coordinator)
    async_add_entities([
        *(EdfTempoSensor(coordinator, entry, description) for description in SENSORS),
        EffectiveTempoSensor(tracker, entry, "edf_tempo_tbe"),
        EffectiveTempoSensor(tracker, entry, "edf_tempo_tbe_source"),
    ])


class EdfTempoSensor(CoordinatorEntity[EdfTempoDataUpdateCoordinator], SensorEntity):
    """Representation of an EDF Tempo Rev TBE sensor."""

    entity_description: EdfTempoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EdfTempoDataUpdateCoordinator,
        entry: ConfigEntry,
        description: EdfTempoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        """Return a language-independent object ID component.

        Home Assistant prefixes this component with the device name. Defining
        the property explicitly prevents the translated entity name from being
        used when a French installation creates the entity registry entry.
        """
        return self.entity_description.key

    @property
    def available(self) -> bool:
        """An API outage does not make the sensor unavailable."""
        return True

    @property
    def native_value(self) -> str | int:
        """Return the current state."""
        if self.coordinator.data is None:
            if self.entity_description.value_key in {"today", "tomorrow"}:
                return "unknown"
            return "0" if self.entity_description.value_key == "season_summary" else 0
        if (
            self.entity_description.value_key not in {"today", "tomorrow"}
            and self._season_summary is None
        ):
            return "0" if self.entity_description.value_key == "season_summary" else 0
        if self.entity_description.value_key == "season_summary":
            return str(self._season_summary.total_placed)
        if self.entity_description.value_key in REMAINING_DAY_FIELDS:
            used_field, total_field = REMAINING_DAY_FIELDS[
                self.entity_description.value_key
            ]
            return max(
                getattr(self._season_summary, total_field)
                - getattr(self._season_summary, used_field),
                0,
            )
        color_code = self._day_data.color_code
        if color_code in {"BLUE", "WHITE", "RED"}:
            return color_code.lower()
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional sensor attributes."""
        if self.coordinator.data is None:
            if self.entity_description.value_key in {"today", "tomorrow"}:
                return {ATTR_DATE: self._day_data.date, ATTR_COLOR_CODE: None}
            return self._empty_summary_attributes
        if (
            self.entity_description.value_key not in {"today", "tomorrow"}
            and self._season_summary is None
        ):
            return self._empty_summary_attributes
        if self.entity_description.value_key == "season_summary":
            return {
                "summary_updated_at": self.coordinator.data.summary_updated_at,
                ATTR_SEASON_START: self._season_summary.season_start,
                ATTR_SEASON_END: self._season_summary.season_end,
                ATTR_TOTAL_PLACED: self._season_summary.total_placed,
                ATTR_BLUE_DAYS: self._season_summary.blue_days,
                ATTR_WHITE_DAYS: self._season_summary.white_days,
                ATTR_RED_DAYS: self._season_summary.red_days,
                ATTR_BLUE_TOTAL: self._season_summary.blue_total,
                ATTR_WHITE_TOTAL: self._season_summary.white_total,
                ATTR_RED_TOTAL: self._season_summary.red_total,
            }
        if self.entity_description.value_key in REMAINING_DAY_FIELDS:
            used_field, total_field = REMAINING_DAY_FIELDS[
                self.entity_description.value_key
            ]
            return {
                ATTR_SEASON_START: self._season_summary.season_start,
                ATTR_SEASON_END: self._season_summary.season_end,
                "used_days": getattr(self._season_summary, used_field),
                "total_days": getattr(self._season_summary, total_field),
            }
        return {
            ATTR_DATE: self._day_data.date,
            ATTR_COLOR_CODE: self._day_data.color_code,
            ATTR_FALLBACK: self._day_data.fallback,
            ATTR_UPDATED_DATE: self._day_data.updated_date,
            **(
                {"fetched_at": self.coordinator.data.fetched_at}
                if self.entity_description.value_key == "tomorrow"
                else {}
            ),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the integration device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Community integration",
            model="Tempo data source: RTE",
        )

    @property
    def _day_data(self) -> TempoDayData:
        """Use a color only when its date matches the displayed day."""
        today = datetime.now(PARIS_TIME_ZONE).date()
        target_date = (
            today
            if self.entity_description.value_key == "today"
            else today + timedelta(days=1)
        )
        target_key = target_date.isoformat()
        data = self.coordinator.data
        if data is None:
            return TempoDayData(target_key, None, None, False, None)
        candidates = (
            (data.today, data.tomorrow)
            if target_date == today
            else (data.tomorrow,)
        )
        for candidate in candidates:
            if candidate.date == target_key:
                return candidate
        return TempoDayData(target_key, None, None, False, None)

    @property
    def _season_summary(self) -> TempoSeasonSummaryData | None:
        """Return the season summary data."""
        return self.coordinator.data.season_summary

    @property
    def _empty_summary_attributes(self) -> dict[str, Any]:
        """Expose zero-valued counters with the current season dates."""
        today = datetime.now(PARIS_TIME_ZONE).date()
        start_year = today.year if today.month >= 9 else today.year - 1
        season_dates = {
            ATTR_SEASON_START: f"{start_year}-09-01",
            ATTR_SEASON_END: f"{start_year + 1}-08-31",
        }
        if self.entity_description.value_key == "season_summary":
            return {
                **season_dates,
                "summary_updated_at": None,
                ATTR_TOTAL_PLACED: 0,
                ATTR_BLUE_DAYS: 0,
                ATTR_WHITE_DAYS: 0,
                ATTR_RED_DAYS: 0,
                ATTR_BLUE_TOTAL: 0,
                ATTR_WHITE_TOTAL: 0,
                ATTR_RED_TOTAL: 0,
            }
        return {**season_dates, "used_days": 0, "total_days": 0}


class EffectiveTempoSensor(SensorEntity):
    """3) Couleur effective à l’heure configurée ; 4) source RTE ou Lixee."""

    _attr_has_entity_name = False

    def __init__(self, tracker: EffectiveTempoTracker, entry: ConfigEntry, key: str) -> None:
        self.tracker = tracker
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = key

    @property
    def native_value(self) -> str | None:
        return self.tracker.color if self.key == "edf_tempo_tbe" else self.tracker.source

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.tracker.subscribe(self.async_write_ha_state)
        self.async_on_remove(lambda: self.tracker.unsubscribe(self.async_write_ha_state))
        await self.tracker.async_start()

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        await self.tracker.async_stop_if_unused()
