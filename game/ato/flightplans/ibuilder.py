from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TYPE_CHECKING, TypeVar

from game.navmesh import NavMeshError
from .flightplan import FlightPlan, Layout
from .planningerror import PlanningError
from ..packagewaypoints import PackageWaypoints

if TYPE_CHECKING:
    from game.coalition import Coalition
    from game.data.doctrine import Doctrine
    from game.theater import ConflictTheater
    from game.threatzones import ThreatZones
    from ..flight import Flight
    from ..package import Package


FlightPlanT = TypeVar("FlightPlanT", bound=FlightPlan[Any])
LayoutT = TypeVar("LayoutT", bound=Layout)


class IBuilder(ABC, Generic[FlightPlanT, LayoutT]):
    def __init__(self, flight: Flight) -> None:
        self.flight = flight
        self._flight_plan: FlightPlanT | None = None

    def get_or_build(self) -> FlightPlanT:
        if self._flight_plan is None:
            self.regenerate()
            assert self._flight_plan is not None
        return self._flight_plan

    def regenerate(self, dump_debug_info: bool = False) -> None:
        try:
            self._generate_package_waypoints_if_needed(dump_debug_info)
            self._flight_plan = self.build(dump_debug_info)
            self._flight_plan.add_waypoint_actions()
        except NavMeshError as ex:
            color = "blue" if self.flight.squadron.player else "red"
            raise PlanningError(
                f"Could not plan {color} {self.flight.flight_type.value} from "
                f"{self.flight.departure} to {self.package.target}"
            ) from ex

    def _generate_package_waypoints_if_needed(self, dump_debug_info: bool) -> None:
        # Package waypoints are only valid for offensive missions. Skip this if the
        # target is friendly.
        if self.package.target.is_friendly(self.is_player):
            return

        if self.package.waypoints is None or dump_debug_info:
            self.package.waypoints = PackageWaypoints.create(
                self.package, self.coalition, dump_debug_info
            )

    @property
    def theater(self) -> ConflictTheater:
        return self.flight.departure.theater

    @abstractmethod
    def build(self, dump_debug_info: bool = False) -> FlightPlanT: ...

    @property
    def package(self) -> Package:
        return self.flight.package

    @property
    def coalition(self) -> Coalition:
        return self.flight.coalition

    @property
    def is_player(self) -> bool:
        return self.coalition.player

    @property
    def doctrine(self) -> Doctrine:
        return self.coalition.doctrine

    @property
    def threat_zones(self) -> ThreatZones:
        return self.coalition.opponent.threat_zone
