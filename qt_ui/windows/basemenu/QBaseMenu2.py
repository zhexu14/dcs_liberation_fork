import textwrap

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from game import Game
from game.ato.flighttype import FlightType
from game.config import RUNWAY_REPAIR_COST
from game.server import EventStream
from game.sim.missionresultsprocessor import MissionResultsProcessor
from game.theater import (
    AMMO_DEPOT_FRONTLINE_UNIT_CONTRIBUTION,
    ControlPoint,
    ControlPointType,
    FREE_FRONTLINE_UNIT_SUPPLY,
)
from qt_ui.cheatcontext import game_state_modifying_cheat_context
from qt_ui.dialogs import Dialog
from qt_ui.models import GameModel
from qt_ui.uiconstants import EVENT_ICONS
from qt_ui.windows.GameUpdateSignal import GameUpdateSignal
from qt_ui.windows.basemenu.NewUnitTransferDialog import NewUnitTransferDialog
from qt_ui.windows.basemenu.QBaseMenuTabs import QBaseMenuTabs
from qt_ui.windows.basemenu.UnitTransactionFrame import UnitTransactionFrame


class QBaseMenu2(QDialog):
    def __init__(self, parent, cp: ControlPoint, game_model: GameModel):
        super(QBaseMenu2, self).__init__(parent)

        # Attrs
        self.cp = cp
        self.game_model = game_model
        self.objectName = "menuDialogue"

        if self.cp.captured:
            self.deliveryEvent = None

        self.setWindowIcon(EVENT_ICONS["capture"])

        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setMinimumSize(300, 200)
        self.setMinimumWidth(1024)
        self.setMaximumWidth(1024)
        self.setModal(True)

        self.setWindowTitle(self.cp.name)

        base_menu_header = QWidget()
        top_layout = QHBoxLayout()

        header = QLabel(self)
        header.setGeometry(0, 0, 655, 106)
        pixmap = QPixmap(self.get_base_image())
        header.setPixmap(pixmap)

        description_layout = QVBoxLayout()
        top_layout.addLayout(description_layout)

        title = QLabel("<b>" + self.cp.name + "</b>")
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title.setProperty("style", "base-title")
        description_layout.addWidget(title)

        if self.cp.ferry_only:
            description_layout.addWidget(
                QLabel(
                    "<br />".join(
                        textwrap.wrap(
                            "This base only supports ferry missions. Transfer the "
                            "squadrons to a different base to use them.",
                            width=80,
                        )
                    )
                )
            )

        description_layout.addStretch()

        self.intel_summary = QLabel()
        self.intel_summary.setToolTip(self.generate_intel_tooltip())
        self.update_intel_summary()
        top_layout.addWidget(self.intel_summary)
        top_layout.setAlignment(Qt.AlignTop)

        runway_buttons_layout = QVBoxLayout()
        top_layout.addLayout(runway_buttons_layout)

        if (
            self.cp.runway_is_destroyable
            and self.game_model.game.settings.enable_runway_state_cheat
        ):
            self.cheat_runway_state = QPushButton()
            self.update_cheat_runway_state_text()
            self.cheat_runway_state.clicked.connect(self.on_cheat_runway_state)
            runway_buttons_layout.addWidget(self.cheat_runway_state)

        self.repair_button = QPushButton()
        self.repair_button.clicked.connect(self.begin_runway_repair)
        self.update_repair_button()
        runway_buttons_layout.addWidget(self.repair_button)
        runway_buttons_layout.addStretch()

        base_menu_header.setProperty("style", "baseMenuHeader")
        base_menu_header.setLayout(top_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(header)
        main_layout.addWidget(base_menu_header)
        main_layout.addWidget(QBaseMenuTabs(cp, self.game_model))
        bottom_row = QHBoxLayout()
        main_layout.addLayout(bottom_row)

        if FlightType.OCA_RUNWAY in self.cp.mission_types(for_player=True):
            runway_attack_button = QPushButton("Attack airfield")
            bottom_row.addWidget(runway_attack_button)

            runway_attack_button.setProperty("style", "btn-danger")
            runway_attack_button.clicked.connect(self.new_package)

        if self.cp.captured and self.has_transfer_destinations:
            transfer_button = QPushButton("Transfer Units")
            transfer_button.setProperty("style", "btn-success")
            bottom_row.addWidget(transfer_button)
            transfer_button.clicked.connect(self.open_transfer_dialog)

        if self.cheat_capturable:
            capture_button = QPushButton("CHEAT: Capture")
            capture_button.setProperty("style", "btn-danger")
            bottom_row.addWidget(capture_button)
            capture_button.clicked.connect(self.cheat_capture)

        self.budget_display = QLabel(
            UnitTransactionFrame.BUDGET_FORMAT.format(self.game_model.game.blue.budget)
        )
        self.budget_display.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.budget_display.setProperty("style", "budget-label")
        bottom_row.addWidget(self.budget_display)
        GameUpdateSignal.get_instance().budgetupdated.connect(self.update_budget)
        self.setLayout(main_layout)

    @property
    def cheat_capturable(self) -> bool:
        return self.game_model.game.settings.enable_base_capture_cheat

    def cheat_capture(self) -> None:
        with game_state_modifying_cheat_context(self.game_model.game) as events:
            self.cp.capture(
                self.game_model.game, events, for_player=not self.cp.captured
            )
            # Redeploy frontline units, as if the CP capture was done in mission.
            results_processor = MissionResultsProcessor(self.game_model.game)
            results_processor.redeploy_units(self.cp)
            self.close()

    @property
    def has_transfer_destinations(self) -> bool:
        return self.game_model.game.transit_network_for(
            self.cp.captured
        ).has_destinations(self.cp)

    def update_cheat_runway_state_text(self) -> None:
        if self.cp.runway_can_be_repaired:
            self.cheat_runway_state.setText("CHEAT: Repair runway")
        else:
            self.cheat_runway_state.setText("CHEAT: Destroy runway")

    def on_cheat_runway_state(self) -> None:
        if self.cp.runway_can_be_repaired:
            self.cp.runway_status.repair()
        else:
            self.cp.runway_status.damage()
        self.update_cheat_runway_state_text()
        self.update_repair_button()
        self.update_intel_summary()
        with EventStream.event_context() as events:
            events.update_control_point(self.cp)

    @property
    def can_repair_runway(self) -> bool:
        return self.cp.captured and self.cp.runway_can_be_repaired

    @property
    def can_afford_runway_repair(self) -> bool:
        return self.game_model.game.blue.budget >= RUNWAY_REPAIR_COST

    def begin_runway_repair(self) -> None:
        if not self.can_afford_runway_repair:
            QMessageBox.critical(
                self,
                "Cannot repair runway",
                f"Runway repair costs ${RUNWAY_REPAIR_COST}M but you have "
                f"only ${self.game_model.game.blue.budget}M available.",
                QMessageBox.Ok,
            )
            return
        if not self.can_repair_runway:
            QMessageBox.critical(
                self,
                "Cannot repair runway",
                f"Cannot repair this runway.",
                QMessageBox.Ok,
            )
            return

        self.cp.begin_runway_repair()
        self.game_model.game.blue.budget -= RUNWAY_REPAIR_COST
        self.update_repair_button()
        self.update_intel_summary()
        GameUpdateSignal.get_instance().updateGame(self.game_model.game)

    def update_repair_button(self) -> None:
        self.repair_button.setVisible(True)
        turns_remaining = self.cp.runway_status.repair_turns_remaining
        if self.cp.captured and turns_remaining is not None:
            self.repair_button.setText("Repairing...")
            self.repair_button.setDisabled(True)
            return

        if self.can_repair_runway:
            if self.can_afford_runway_repair:
                self.repair_button.setText(f"Repair ${RUNWAY_REPAIR_COST}M")
                self.repair_button.setDisabled(False)
                return
            else:
                self.repair_button.setText(
                    f"Cannot afford repair ${RUNWAY_REPAIR_COST}M"
                )
                self.repair_button.setDisabled(True)
                return

        self.repair_button.setVisible(False)
        self.repair_button.setDisabled(True)

    def update_intel_summary(self) -> None:
        aircraft = self.cp.allocated_aircraft().total_present
        parking = self.cp.total_aircraft_parking
        ground_unit_limit = self.cp.frontline_unit_count_limit
        deployable_unit_info = ""

        allocated = self.cp.allocated_ground_units(
            self.game_model.game.coalition_for(self.cp.captured).transfers
        )
        unit_overage = max(
            allocated.total_present - self.cp.frontline_unit_count_limit, 0
        )
        if self.cp.has_active_frontline:
            deployable_unit_info = (
                f" (Up to {ground_unit_limit} deployable, {unit_overage} reserve)"
            )

        intel_lines = [
            f"{aircraft}/{parking} aircraft",
            f"{self.cp.base.total_armor} ground units" + deployable_unit_info,
            f"{allocated.total_transferring} more ground units en route, {allocated.total_ordered} ordered",
        ]
        if (runway_description := self.cp.describe_runway_status()) is not None:
            intel_lines.append(runway_description)
        intel_lines.extend(
            [
                f"{self.cp.active_ammo_depots_count}/{self.cp.total_ammo_depots_count} ammo depots",
                f"{'Factory can produce units' if self.cp.has_factory else 'Does not have a factory'}",
            ]
        )

        self.intel_summary.setText("\n".join(intel_lines))

    def generate_intel_tooltip(self) -> str:
        tooltip = (
            f"Deployable unit limit ({self.cp.frontline_unit_count_limit}) = {FREE_FRONTLINE_UNIT_SUPPLY} (base) + "
            f" {AMMO_DEPOT_FRONTLINE_UNIT_CONTRIBUTION} (per connected ammo depot) * {self.cp.total_ammo_depots_count} "
            f"(depots)"
        )

        if self.cp.has_active_frontline:
            unit_overage = max(
                self.cp.base.total_armor - self.cp.frontline_unit_count_limit, 0
            )
            tooltip += (
                f"\n{unit_overage} units will be held in reserve and will not be deployed to "
                f"connected frontlines for this turn"
            )

        return tooltip

    def closeEvent(self, close_event: QCloseEvent):
        GameUpdateSignal.get_instance().updateGame(self.game_model.game)

    def get_base_image(self):
        if (
            self.cp.cptype == ControlPointType.AIRCRAFT_CARRIER_GROUP
            or self.cp.cptype == ControlPointType.LHA_GROUP
        ):
            carrier_type = self.cp.get_carrier_group_type(always_supercarrier=True)
            return f"./resources/ui/units/ships/{carrier_type.id}.png"
        elif self.cp.cptype == ControlPointType.FOB and self.cp.has_helipads:
            return "./resources/ui/heliport.png"
        elif self.cp.cptype == ControlPointType.FOB:
            return "./resources/ui/fob.png"
        else:
            return "./resources/ui/airbase.png"

    def new_package(self) -> None:
        Dialog.open_new_package_dialog(self.cp, parent=self.window())

    def open_transfer_dialog(self) -> None:
        NewUnitTransferDialog(self.game_model, self.cp, parent=self.window()).show()

    def update_budget(self, game: Game) -> None:
        self.budget_display.setText(
            UnitTransactionFrame.BUDGET_FORMAT.format(game.blue.budget)
        )
