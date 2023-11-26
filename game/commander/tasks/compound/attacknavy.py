from collections.abc import Iterator

from game.commander.tasks.primitive.antiship import PlanAntiShip
from game.commander.theaterstate import TheaterState
from game.htn import CompoundTask, Method
from game.theater.theatergroundobject import CarrierGroundObject, LhaGroundObject


class AttackNavy(CompoundTask[TheaterState]):
    def each_valid_method(self, state: TheaterState) -> Iterator[Method[TheaterState]]:
        for ship in state.enemy_ships:
            if ship.is_capital_ship:
                methods = []
                for i in range(
                    state.context.coalition.doctrine.antiship_capital_ship_packages
                ):
                    methods.append(PlanAntiShip(ship))
                yield methods
            else:
                yield [PlanAntiShip(ship)]
