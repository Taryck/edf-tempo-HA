"""Couleur Tempo effective : RTE à l'heure configurée, Lixee en secours."""

from __future__ import annotations

from datetime import datetime, timedelta, time
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time, async_track_state_change_event
from .const import (
    CONF_LIXEE_ENTITIES, CONF_LIXEE_LOCK_HOURS, CONF_TEMPO_SWITCH_TIME,
    DEFAULT_LIXEE_LOCK_HOURS, DEFAULT_TEMPO_SWITCH_TIME, PARIS_TIME_ZONE,
)

COLORS = {"BLUE": "blue", "WHITE": "white", "RED": "red"}
NTARF = {"1": "blue", "2": "blue", "3": "white", "4": "white", "5": "red", "6": "red"}


def lixee_color(state):
    """2) Reconnaître la couleur, sans confondre HP/HC avec un changement de jour."""
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    value = state.state.strip().upper().replace(" ", "")
    if value in NTARF:
        return NTARF[value]
    for name, color in (("BLEU", "blue"), ("BLUE", "blue"), ("BLANC", "white"),
                        ("WHITE", "white"), ("ROUGE", "red"), ("RED", "red")):
        if name in value:
            return color
    return None


class EffectiveTempoTracker:
    """3) RTE prioritaire à 06:00 ; premier changement Lixee après 06:00 sinon."""

    def __init__(self, hass, entry, coordinator):
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.color = None
        self.source = None
        self._day = None
        self._lock_until = None
        self._listeners = set()
        self._unsub = []
        self._unsub_switch = None
        self._started = False
        self._pending = False

    def subscribe(self, listener):
        self._listeners.add(listener)

    def unsubscribe(self, listener):
        self._listeners.discard(listener)

    def _notify(self):
        for listener in tuple(self._listeners):
            listener()

    def _switch_time(self):
        try:
            hour, minute = map(int, self.entry.options.get(
                CONF_TEMPO_SWITCH_TIME, DEFAULT_TEMPO_SWITCH_TIME).split(":"))
            return time(hour, minute)
        except (ValueError, TypeError):
            return time(6, 0)

    def _current_day(self, now):
        # 1) Avant l'heure de bascule, le jour tarifaire est encore celui de la veille.
        return now.date() if now.time().replace(tzinfo=None) >= self._switch_time() else now.date() - timedelta(days=1)

    def _rte_color(self, day):
        data = self.coordinator.data
        if data is None:
            return None
        for item in (data.today, data.tomorrow):
            if item.date == day.isoformat():
                return COLORS.get(item.color_code)
        return None

    def _set(self, color, source):
        if (color, source) != (self.color, self.source):
            self.color, self.source = color, source
            self._notify()

    def _apply_day(self):
        now = datetime.now(PARIS_TIME_ZONE)
        day = self._current_day(now)
        if day != self._day:
            self._day = day
            self._lock_until = None
            # 3) Pas de couleur RTE pour ce jour : unknown, jamais l'ancienne couleur.
            color = self._rte_color(day)
            self._pending = color is None
            self._set(color, "rte" if color else None)
        elif self._pending:
            # Une annonce RTE tardive reprend toujours la priorité.
            color = self._rte_color(day)
            if color:
                self._pending = False
                self._set(color, "rte")

    @callback
    def _on_rte_update(self):
        self._apply_day()

    @callback
    def _on_lixee_change(self, event):
        if not self._pending:
            return
        now = datetime.now(PARIS_TIME_ZONE)
        # 2) Seuls les changements détectés à partir de la bascule sont recevables.
        if self._current_day(now) != now.date():
            return
        if self._lock_until is not None and now < self._lock_until:
            return
        old = lixee_color(event.data.get("old_state"))
        new = lixee_color(event.data.get("new_state"))
        if old is None or new is None or old == new:
            return
        self._set(new, "lixee")
        self._lock_until = now + timedelta(hours=int(self.entry.options.get(
            CONF_LIXEE_LOCK_HOURS, DEFAULT_LIXEE_LOCK_HOURS)))

    @callback
    def _on_switch(self, _now):
        self._apply_day()
        self._schedule_next()

    def _schedule_next(self):
        now = datetime.now(PARIS_TIME_ZONE)
        target = datetime.combine(now.date(), self._switch_time(), tzinfo=PARIS_TIME_ZONE)
        if target <= now:
            target = datetime.combine(now.date() + timedelta(days=1), self._switch_time(), tzinfo=PARIS_TIME_ZONE)
        if self._unsub_switch is not None:
            self._unsub_switch()
        self._unsub_switch = async_track_point_in_time(self.hass, self._on_switch, target)

    async def async_start(self):
        if self._started:
            return
        self._started = True
        self._apply_day()
        self._unsub.append(self.coordinator.async_add_listener(self._on_rte_update))
        # 2) N entités LTARF et NTARF, la première bascule de couleur l'emporte.
        entities = self.entry.options.get(CONF_LIXEE_ENTITIES, [])
        if entities:
            self._unsub.append(async_track_state_change_event(
                self.hass, entities, self._on_lixee_change))
        self._schedule_next()

    async def async_stop_if_unused(self):
        if self._listeners:
            return
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        if self._unsub_switch is not None:
            self._unsub_switch()
            self._unsub_switch = None
        self._started = False
