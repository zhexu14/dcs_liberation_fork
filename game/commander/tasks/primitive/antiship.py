from __future__ import annotations

from dataclasses import dataclass

from game.commander.missionproposals import EscortType
from game.commander.tasks.packageplanningtask import PackagePlanningTask
from game.commander.theaterstate import TheaterState
from game.theater.theatergroundobject import (
    NavalGroundObject,
    LhaGroundObject,
    CarrierGroundObject,
)
from game.ato.flighttype import FlightType
from typing import Dict


class PlanAntiShip(PackagePlanningTask[NavalGroundObject]):
    # Tracks capital ship targets and the number of flights assign to each target.
    # Larger ships (CVN, LHA) require multiple 4-ship flights firing multiple missiles
    # to have a good chance of being destroyed. There is no point in damaging the target
    # only as we do not track damage across turns.
    capital_ship_packages: Dict[str, int] = {}

    def preconditions_met(self, state: TheaterState) -> bool:
        if (
            self.target not in state.threatening_air_defenses
            and self.target not in state.enemy_ships
        ):
            return False
        if not self.target_area_preconditions_met(state, ignore_iads=True):
            return False
        return super().preconditions_met(state)

    def apply_effects(self, state: TheaterState) -> None:
        if self.target.is_capital_ship:
            self.register_effects(self.target)
            if (
                self.capital_ship_packages[self.target.name]
                >= state.context.coalition.doctrine.antiship_capital_ship_packages
            ):
                state.eliminate_ship(self.target)
                self.capital_ship_packages.pop(self.target.name)
        else:
            state.eliminate_ship(self.target)

    def propose_flights(self) -> None:
        flight_size = 2
        # When attacking capital ships, use larger flight size to increase likelihood the target will be killed
        # rather than being damaged. There is no point in only damaging the target as we do not track damage
        # across turns. Four is the largest flight size that can be set.
        if self.target.is_capital_ship:
            flight_size = 4
        self.propose_flight(FlightType.ANTISHIP, flight_size)
        self.propose_flight(FlightType.ESCORT, 2, EscortType.AirToAir)

    @classmethod
    def register_effects(cls, target: NavalGroundObject) -> None:
        if target.name not in cls.capital_ship_packages:
            cls.capital_ship_packages[target.name] = 0
        cls.capital_ship_packages[target.name] += 1
