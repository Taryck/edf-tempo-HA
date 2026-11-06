"""Couleur Tempo effective : RTE à l'heure configurée, Lixee en secours."""

from __future__ import annotations

from datetime import datetime, timedelta, time
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time, async_track_state_change_event
from .const import (
    CONF_LIXEE_ENTITIES, CONF_LIXEE_LOCK_HOURS, CONF_TEMPO_SWITCH_TIME,
    DEFAULT_LIXEE_LOCK_HOURS, DEFAULT_TEMPO_SWITCH_TIME, PARIS_TIME_ZONE,
)

# Couleurs Tempo utilisées par les deux sources.
COULEURS = ("Bleu", "Blanc", "Rouge")

# Correspondance des index tarifaires NTARF :
# 1/2 = Bleu, 3/4 = Blanc, 5/6 = Rouge (HC/HP).
NTARF = {
    "1": "Bleu",
    "2": "Bleu",
    "3": "Blanc",
    "4": "Blanc",
    "5": "Rouge",
    "6": "Rouge",
}

# Sources possibles de la couleur Tempo effective.
RTE = "rte"
LIXEE = "lixee"

def lixee_color(state):
    """2) Reconnaître la couleur, sans confondre HP/HC avec un changement de jour."""
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    value = state.state.strip().upper().replace(" ", "")
    # NTARF : index numérique.
    if value in NTARF:
        return NTARF[value]

    # LTARF : libellé contenant la couleur française.
    for couleur in COULEURS:
        if couleur.upper() in value:
            return couleur
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
        self._rte_decision = None
        self._lixee_first = None
        self._unsub_lixee = None

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
                return {"BLUE": "Bleu", "WHITE": "Blanc", "RED": "Rouge"}.get(item.color_code)
        return None

    def _set(self, color, source):
        if (color, source) != (self.color, self.source):
            self.color, self.source = color, source
            self._notify()

    def rte_est_hs(self, jour):
        """À 04:00 : absence de couleur RTE datée = secours Lixee pour ce jour."""
        return self._rte_color(jour) is None

    def _surveiller_lixee(self):
        """À 05:00 : écouter simultanément les 2 x X capteurs LTARF/NTARF."""
        if self._unsub_lixee is not None:
            return
        entities = self.entry.options.get(CONF_LIXEE_ENTITIES, [])
        if entities:
            self._unsub_lixee = async_track_state_change_event(
                self.hass, entities, self._on_lixee_change)

    def _arreter_lixee(self):
        if self._unsub_lixee is not None:
            self._unsub_lixee()
            self._unsub_lixee = None

    def _decider_rte(self, jour):
        """À 04:00, figer le choix RTE/Lixee jusqu'au lendemain."""
        self._rte_decision = (jour, None if self.rte_est_hs(jour) else self._rte_color(jour))
        self._lixee_first = None
        self._lock_until = None
        if self._rte_decision[1] is not None:
            self._arreter_lixee()

    def _apply_day(self):
        """À 06:00 : appliquer la décision de 04:00, sans consulter RTE à nouveau."""
        now = datetime.now(PARIS_TIME_ZONE)
        jour = self._current_day(now)
        if self._day == jour:
            return
        self._day = jour
        if self._rte_decision is None or self._rte_decision[0] != jour:
            # Redémarrage après 04:00 : impossible de reconstituer la décision passée.
            self._set(None, None)
            return
        couleur_rte = self._rte_decision[1]
        if couleur_rte is not None:
            self._set(couleur_rte, RTE)
        elif self._lixee_first is not None:
            self._set(self._lixee_first[1], LIXEE)
        else:
            self._set(None, None)

    @callback
    def _on_rte_update(self):
        # RTE est ignoré après la décision de 04:00 pour la journée en cours.
        pass

    @callback
    def _on_lixee_change(self, event):
        """Retenir le premier événement valide reçu depuis 05:00, tous Lixee confondus."""
        now = datetime.now(PARIS_TIME_ZONE)
        if self._rte_decision is None or self._rte_decision != (now.date(), None):
            return
        if self._lixee_first is not None:
            return
        ancien = lixee_color(event.data.get("old_state"))
        nouveau = lixee_color(event.data.get("new_state"))
        if nouveau is None or ancien == nouveau:
            return
        # La date est celle de l'événement reçu, jamais celle de la dernière valeur.
        self._lixee_first = (now, nouveau)
        if self._current_day(now) == now.date():
            self._apply_day()
            self._set(nouveau, LIXEE)
            self._lock_until = now + timedelta(hours=int(self.entry.options.get(
                CONF_LIXEE_LOCK_HOURS, DEFAULT_LIXEE_LOCK_HOURS)))

    @callback
    def _on_switch(self, _now):
        now = datetime.now(PARIS_TIME_ZONE)
        bascule = datetime.combine(now.date(), self._switch_time(), tzinfo=PARIS_TIME_ZONE)
        if now < bascule - timedelta(hours=1):
            # 04:00 : décider RTE ou Lixee, puis oublier RTE jusqu'au lendemain.
            self._decider_rte(now.date())
        elif now < bascule:
            # 05:00 : écouter les changements des 2 x X capteurs uniquement si RTE HS.
            if self._rte_decision == (now.date(), None):
                self._surveiller_lixee()
        else:
            # 06:00 : publier la couleur décidée.
            self._apply_day()
        self._schedule_next()

    def _schedule_next(self):
        now = datetime.now(PARIS_TIME_ZONE)
        bascule = datetime.combine(now.date(), self._switch_time(), tzinfo=PARIS_TIME_ZONE)
        horaires = (bascule - timedelta(hours=2), bascule - timedelta(hours=1), bascule)
        target = next((instant for instant in horaires if instant > now), None)
        if target is None:
            bascule = datetime.combine(now.date() + timedelta(days=1), self._switch_time(), tzinfo=PARIS_TIME_ZONE)
            target = bascule - timedelta(hours=2)
        if self._unsub_switch is not None:
            self._unsub_switch()
        self._unsub_switch = async_track_point_in_time(self.hass, self._on_switch, target)

    async def async_start(self):
        if self._started:
            return
        self._started = True
        self._apply_day()
        # 04:00 est la seule décision RTE ; les mises à jour ultérieures sont ignorées.
        self._schedule_next()

    async def async_stop_if_unused(self):
        if self._listeners:
            return
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        self._arreter_lixee()
        if self._unsub_switch is not None:
            self._unsub_switch()
            self._unsub_switch = None
        self._started = False
