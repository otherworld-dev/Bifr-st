"""
Robot Calibration Panel
Consolidates all calibration settings:
- Motor direction verification
- Gripper PWM calibration
- DH parameters editing
"""

from PyQt5 import QtCore, QtGui, QtWidgets
import json
import logging
import paths
from forward_kinematics import get_dh_params, reload_dh_parameters
from config_g_manager import JOINT_TO_DRIVES, get_joint_directions, set_joint_direction
import config

logger = logging.getLogger(__name__)


class CollapsibleSection(QtWidgets.QWidget):
    """A section with a clickable header that toggles content visibility."""

    expanded = QtCore.pyqtSignal(object)  # Emitted with self when section expands

    def __init__(self, title, is_expanded=True, parent=None):
        super().__init__(parent)
        self._title = title
        self._expanded = is_expanded

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.toggle_btn = QtWidgets.QPushButton()
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 10px;
                background-color: #e0e0e0;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #d0d0d0; }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.content)

        self._update_header()
        if not is_expanded:
            self.content.hide()

    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self._update_header()
        if self._expanded:
            self.expanded.emit(self)

    def collapse(self):
        """Collapse this section programmatically."""
        if self._expanded:
            self._expanded = False
            self.content.hide()
            self._update_header()

    def _update_header(self):
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self.toggle_btn.setText(f"{arrow}  {self._title}")

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


# DH parameters file path
DH_PARAMS_FILE = paths.get_data_dir() / 'dh_parameters.json'
GRIPPER_CALIBRATION_FILE = paths.get_data_dir() / 'gripper_calibration.json'
HOME_POSITION_FILE = paths.get_data_dir() / 'home_position.json'
PARK_POSITION_FILE = paths.get_data_dir() / 'park_position.json'


def load_gripper_calibration_on_startup():
    """
    Load gripper calibration from file and apply to config module.
    Call this at application startup to ensure settings are loaded
    before the calibration panel is opened.
    """
    try:
        if GRIPPER_CALIBRATION_FILE.exists():
            with open(GRIPPER_CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
            config.GRIPPER_PWM_OPEN = data.get('pwm_open', 255)
            config.GRIPPER_PWM_CLOSED = data.get('pwm_closed', 0)
            logger.info(f"Loaded gripper calibration: open={config.GRIPPER_PWM_OPEN}, closed={config.GRIPPER_PWM_CLOSED}")
        else:
            logger.debug("No gripper calibration file found, using defaults")
    except Exception as e:
        logger.error(f"Error loading gripper calibration on startup: {e}")


def load_home_position_on_startup():
    """
    Load home position from file and apply to config module.
    Call this at application startup.
    """
    try:
        if HOME_POSITION_FILE.exists():
            with open(HOME_POSITION_FILE, 'r') as f:
                data = json.load(f)
            for joint in ('Art1', 'Art2', 'Art3', 'Art4', 'Art5', 'Art6'):
                if joint in data:
                    config.HOME_POSITION[joint] = data[joint]
            logger.info(f"Loaded home position: {config.HOME_POSITION}")
        else:
            logger.debug("No home position file found, using defaults")
    except Exception as e:
        logger.error(f"Error loading home position on startup: {e}")


def load_park_position_on_startup():
    """
    Load park position from file and apply to config module.
    Call this at application startup.
    """
    try:
        if PARK_POSITION_FILE.exists():
            with open(PARK_POSITION_FILE, 'r') as f:
                data = json.load(f)
            for joint in ('Art1', 'Art2', 'Art3', 'Art4', 'Art5', 'Art6'):
                if joint in data:
                    config.PARK_POSITION[joint] = data[joint]
            logger.info(f"Loaded park position: {config.PARK_POSITION}")
        else:
            logger.debug("No park position file found, using defaults")
    except Exception as e:
        logger.error(f"Error loading park position on startup: {e}")


class JointCalibrationWidget(QtWidgets.QWidget):
    """Compact single-row widget for verifying direction of a single joint"""

    test_movement = QtCore.pyqtSignal(str, float)  # joint_name, delta_angle
    direction_changed = QtCore.pyqtSignal(str, int)  # joint_name, direction (+1 or -1)

    def __init__(self, joint_name, joint_description, parent=None):
        super().__init__(parent)
        self.joint_name = joint_name
        self.joint_description = joint_description
        self.current_direction = 1
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        name_label = QtWidgets.QLabel(f"<b>{self.joint_name}</b>")
        name_label.setMinimumWidth(35)
        layout.addWidget(name_label)

        desc_label = QtWidgets.QLabel(self.joint_description)
        desc_label.setStyleSheet("color: #666;")
        desc_label.setMinimumWidth(140)
        layout.addWidget(desc_label)

        layout.addStretch()

        # Test buttons
        self.test_minus = QtWidgets.QPushButton("\u221210\u00b0")
        self.test_minus.setFixedWidth(45)
        self.test_minus.setStyleSheet("background-color: #ffcccc;")
        self.test_minus.clicked.connect(lambda: self.test_movement.emit(self.joint_name, -10))
        layout.addWidget(self.test_minus)

        self.test_plus = QtWidgets.QPushButton("+10\u00b0")
        self.test_plus.setFixedWidth(45)
        self.test_plus.setStyleSheet("background-color: #ccffcc;")
        self.test_plus.clicked.connect(lambda: self.test_movement.emit(self.joint_name, 10))
        layout.addWidget(self.test_plus)

        layout.addSpacing(10)

        # Direction toggle
        self.direction_button_group = QtWidgets.QButtonGroup(self)
        self.forward_radio = QtWidgets.QRadioButton("Fwd")
        self.forward_radio.setChecked(True)
        self.direction_button_group.addButton(self.forward_radio, 1)
        layout.addWidget(self.forward_radio)

        self.reverse_radio = QtWidgets.QRadioButton("Rev")
        self.direction_button_group.addButton(self.reverse_radio, -1)
        layout.addWidget(self.reverse_radio)

        self.forward_radio.clicked.connect(lambda: self._on_user_direction_click(1))
        self.reverse_radio.clicked.connect(lambda: self._on_user_direction_click(-1))

    def _on_user_direction_click(self, direction):
        """Called when user clicks a direction radio button"""
        self.current_direction = direction
        self.direction_changed.emit(self.joint_name, direction)

    def set_direction(self, direction):
        """Set direction programmatically"""
        self.current_direction = direction
        if direction == 1:
            self.forward_radio.setChecked(True)
        else:
            self.reverse_radio.setChecked(True)

    def get_direction(self):
        """Get current direction value"""
        return self.current_direction


class GripperCalibrationWidget(QtWidgets.QWidget):
    """Widget for calibrating gripper open/closed positions via slide-observe-capture"""

    test_gripper = QtCore.pyqtSignal(int)  # PWM value to send to servo
    limits_changed = QtCore.pyqtSignal()   # Emitted when open/closed limits are captured

    def __init__(self, parent=None):
        super().__init__(parent)
        self._open_pwm = 255
        self._closed_pwm = 0
        self.setup_ui()
        self.load_calibration()

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        desc = QtWidgets.QLabel(
            "Drag the slider to move the gripper, then capture the open and closed positions."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 4px;")
        main_layout.addWidget(desc)

        frame = QtWidgets.QFrame()
        frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        frame_layout = QtWidgets.QVBoxLayout(frame)

        # Slider row
        slider_row = QtWidgets.QHBoxLayout()
        closed_label = QtWidgets.QLabel("Closed")
        closed_label.setStyleSheet("font-weight: bold; color: #cc4444;")
        slider_row.addWidget(closed_label)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 255)
        self.slider.setValue(128)
        self.slider.setMinimumHeight(28)
        slider_row.addWidget(self.slider, 1)

        open_label = QtWidgets.QLabel("Open")
        open_label.setStyleSheet("font-weight: bold; color: #44aa44;")
        slider_row.addWidget(open_label)

        self.pwm_label = QtWidgets.QLabel("PWM: 128")
        self.pwm_label.setMinimumWidth(60)
        self.pwm_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.pwm_label.setStyleSheet("color: #666;")
        slider_row.addWidget(self.pwm_label)

        frame_layout.addLayout(slider_row)

        # Update label live; send command on release
        self.slider.valueChanged.connect(lambda v: self.pwm_label.setText(f"PWM: {v}"))
        self.slider.sliderReleased.connect(lambda: self.test_gripper.emit(self.slider.value()))

        # Capture buttons
        btn_row = QtWidgets.QHBoxLayout()

        self.set_closed_btn = QtWidgets.QPushButton("Set as Closed Limit")
        self.set_closed_btn.setStyleSheet("background-color: #ffcccc;")
        self.set_closed_btn.clicked.connect(self._capture_closed)
        btn_row.addWidget(self.set_closed_btn)

        self.set_open_btn = QtWidgets.QPushButton("Set as Open Limit")
        self.set_open_btn.setStyleSheet("background-color: #ccffcc;")
        self.set_open_btn.clicked.connect(self._capture_open)
        btn_row.addWidget(self.set_open_btn)

        frame_layout.addLayout(btn_row)

        # Saved limits display
        limits_row = QtWidgets.QHBoxLayout()
        self.closed_limit_label = QtWidgets.QLabel("Closed: 0")
        self.closed_limit_label.setStyleSheet("font-weight: bold; color: #cc4444;")
        limits_row.addWidget(self.closed_limit_label)
        limits_row.addStretch()
        self.open_limit_label = QtWidgets.QLabel("Open: 255")
        self.open_limit_label.setStyleSheet("font-weight: bold; color: #44aa44;")
        limits_row.addWidget(self.open_limit_label)
        frame_layout.addLayout(limits_row)

        main_layout.addWidget(frame)

    def _capture_open(self):
        self._open_pwm = self.slider.value()
        self._update_limit_labels()
        self.limits_changed.emit()

    def _capture_closed(self):
        self._closed_pwm = self.slider.value()
        self._update_limit_labels()
        self.limits_changed.emit()

    def _update_limit_labels(self):
        self.closed_limit_label.setText(f"Closed: {self._closed_pwm}")
        self.open_limit_label.setText(f"Open: {self._open_pwm}")

    def get_open_pwm(self):
        return self._open_pwm

    def get_closed_pwm(self):
        return self._closed_pwm

    def load_calibration(self):
        try:
            if GRIPPER_CALIBRATION_FILE.exists():
                with open(GRIPPER_CALIBRATION_FILE, 'r') as f:
                    data = json.load(f)
                self._open_pwm = data.get('pwm_open', 255)
                self._closed_pwm = data.get('pwm_closed', 0)
                logger.info("Loaded gripper calibration from file")
            else:
                self._open_pwm = config.GRIPPER_PWM_OPEN
                self._closed_pwm = config.GRIPPER_PWM_CLOSED
                logger.info("Using default gripper calibration from config")

            self._update_limit_labels()
            self.apply_to_config()
        except Exception as e:
            logger.error(f"Error loading gripper calibration: {e}")

    def apply_to_config(self):
        config.GRIPPER_PWM_OPEN = self._open_pwm
        config.GRIPPER_PWM_CLOSED = self._closed_pwm
        logger.debug(f"Applied gripper PWM: open={self._open_pwm}, closed={self._closed_pwm}")


class DHParametersWidget(QtWidgets.QWidget):
    """Widget for editing DH parameters table"""

    parameters_changed = QtCore.pyqtSignal()  # Emitted when parameters are saved
    preview_changed = QtCore.pyqtSignal()  # Emitted when any value changes (for live preview)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinboxes = {}
        self._loading = False
        self.setup_ui()
        self.load_parameters()

    def setup_ui(self):
        """Create UI elements for DH parameters"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Link", "θ offset (°)", "d (mm)", "a (mm)", "α (°)"])
        self.table.setRowCount(6)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.table.setColumnWidth(0, 40)

        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(220)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f9f9f9;
                gridline-color: #ddd;
                border: 1px solid #ccc;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 4px;
                border: 1px solid #ccc;
                font-weight: bold;
            }
        """)

        # Create widgets for each cell
        for row in range(6):
            # Link number (read-only)
            link_item = QtWidgets.QTableWidgetItem(str(row + 1))
            link_item.setFlags(QtCore.Qt.ItemIsEnabled)
            link_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 0, link_item)

            # theta_offset spinbox
            spinbox = QtWidgets.QDoubleSpinBox()
            spinbox.setRange(-360, 360)
            spinbox.setDecimals(2)
            spinbox.setSingleStep(1.0)
            spinbox.setAlignment(QtCore.Qt.AlignCenter)
            self.table.setCellWidget(row, 1, spinbox)
            self.spinboxes[(row, 'theta_offset')] = spinbox

            # d, a, alpha spinboxes
            for col, param in enumerate(['d', 'a', 'alpha'], start=2):
                spinbox = QtWidgets.QDoubleSpinBox()
                spinbox.setRange(-1000 if param in ['d', 'a'] else -360, 1000 if param in ['d', 'a'] else 360)
                spinbox.setDecimals(2)
                spinbox.setSingleStep(1.0)
                spinbox.setAlignment(QtCore.Qt.AlignCenter)
                self.table.setCellWidget(row, col, spinbox)
                self.spinboxes[(row, param)] = spinbox

        main_layout.addWidget(self.table)

        # Connect all spinboxes to emit preview_changed
        for spinbox in self.spinboxes.values():
            spinbox.valueChanged.connect(self._on_value_changed)

        # Buttons (Load/Reset only — Save is handled by the panel-level Save All)
        button_layout = QtWidgets.QHBoxLayout()

        self.load_button = QtWidgets.QPushButton("Load")
        self.load_button.clicked.connect(self.load_parameters)
        button_layout.addWidget(self.load_button)

        self.reset_button = QtWidgets.QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.reset_to_default)
        button_layout.addWidget(self.reset_button)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

    def load_parameters(self):
        """Load DH parameters from file"""
        self._loading = True
        try:
            if DH_PARAMS_FILE.exists():
                with open(DH_PARAMS_FILE, 'r') as f:
                    dh_params = json.load(f)

                for link_data in dh_params['links']:
                    row = link_data['link'] - 1
                    self.spinboxes[(row, 'theta_offset')].setValue(link_data['theta_offset'])
                    self.spinboxes[(row, 'd')].setValue(link_data['d'])
                    self.spinboxes[(row, 'a')].setValue(link_data['a'])
                    self.spinboxes[(row, 'alpha')].setValue(link_data['alpha'])

                logger.info("Loaded DH parameters from file")
            else:
                self.reset_to_default()
        except Exception as e:
            logger.error(f"Error loading DH parameters: {e}")
        finally:
            self._loading = False

    def _on_value_changed(self):
        """Handle spinbox/combo value change - emit preview signal"""
        if not self._loading:
            self.preview_changed.emit()

    def get_parameters(self):
        """Get current DH parameters from the table as a list of dicts"""
        params = []
        descriptions = ["Base rotation", "Shoulder", "Elbow", "Wrist roll", "Wrist pitch", "Wrist yaw / TCP"]
        for row in range(6):
            params.append({
                "link": row + 1,
                "theta_offset": self.spinboxes[(row, 'theta_offset')].value(),
                "d": self.spinboxes[(row, 'd')].value(),
                "a": self.spinboxes[(row, 'a')].value(),
                "alpha": self.spinboxes[(row, 'alpha')].value(),
                "description": descriptions[row],
            })
        return params

    def save_parameters(self):
        """Save DH parameters to file"""
        try:
            descriptions = ["Base rotation", "Shoulder", "Elbow", "Wrist roll", "Wrist pitch", "Wrist yaw / TCP"]

            dh_data = {
                "version": "1.1",
                "description": "ThorRR Robot DH Parameters",
                "date_modified": QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd"),
                "links": []
            }

            for row in range(6):
                link_data = {
                    "link": row + 1,
                    "theta_offset": self.spinboxes[(row, 'theta_offset')].value(),
                    "d": self.spinboxes[(row, 'd')].value(),
                    "a": self.spinboxes[(row, 'a')].value(),
                    "alpha": self.spinboxes[(row, 'alpha')].value(),
                    "description": descriptions[row]
                }
                dh_data['links'].append(link_data)

            with open(DH_PARAMS_FILE, 'w') as f:
                json.dump(dh_data, f, indent=4)

            reload_dh_parameters()
            self.parameters_changed.emit()

            logger.info("Saved DH parameters to file")

        except Exception as e:
            logger.error(f"Error saving DH parameters: {e}")
            raise

    def reset_to_default(self):
        """Reset to default ThorRR DH parameters"""
        self._loading = True
        try:
            default_params = [
                {"theta_offset": 0, "d": 202, "a": 0, "alpha": 90},
                {"theta_offset": 90, "d": 0, "a": 160, "alpha": 0},
                {"theta_offset": 90, "d": 0, "a": 0, "alpha": 90},
                {"theta_offset": 0, "d": 195, "a": 0, "alpha": -90},
                {"theta_offset": 0, "d": 0, "a": 0, "alpha": 90},
                {"theta_offset": 0, "d": 67.15, "a": 0, "alpha": 0},
            ]

            for row, params in enumerate(default_params):
                self.spinboxes[(row, 'theta_offset')].setValue(params['theta_offset'])
                self.spinboxes[(row, 'd')].setValue(params['d'])
                self.spinboxes[(row, 'a')].setValue(params['a'])
                self.spinboxes[(row, 'alpha')].setValue(params['alpha'])

            logger.info("Reset DH parameters to defaults")
        finally:
            self._loading = False


class HomePositionWidget(QtWidgets.QWidget):
    """Widget for setting the software home position (joint angles)"""

    position_changed = QtCore.pyqtSignal()

    # Joint limits matching the main GUI spinboxes
    JOINT_LIMITS = {
        'Art1': (-97, 97),
        'Art2': (-90, 90),
        'Art3': (-90, 90),
        'Art4': (-180, 180),
        'Art5': (-90, 90),
        'Art6': (-180, 180),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinboxes = {}
        self._loading = False
        self.setup_ui()
        self.load_from_config()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        desc = QtWidgets.QLabel(
            "Joint angles the robot moves to when the Home button is pressed."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 4px;")
        layout.addWidget(desc)

        # Grid of joint spinboxes
        grid = QtWidgets.QGridLayout()
        for i, (joint, (lo, hi)) in enumerate(self.JOINT_LIMITS.items()):
            label = QtWidgets.QLabel(f"{joint}:")
            label.setFixedWidth(40)
            grid.addWidget(label, i // 3, (i % 3) * 2)

            spinbox = QtWidgets.QDoubleSpinBox()
            spinbox.setRange(lo, hi)
            spinbox.setDecimals(1)
            spinbox.setSuffix("°")
            spinbox.setValue(config.HOME_POSITION.get(joint, 0.0))
            spinbox.valueChanged.connect(self._on_value_changed)
            grid.addWidget(spinbox, i // 3, (i % 3) * 2 + 1)
            self.spinboxes[joint] = spinbox

        layout.addLayout(grid)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.capture_button = QtWidgets.QPushButton("Capture Current")
        self.capture_button.setToolTip("Set home position to current joint angles")
        self.capture_button.clicked.connect(self._capture_current)
        btn_layout.addWidget(self.capture_button)

        self.reset_button = QtWidgets.QPushButton("Reset to Zero")
        self.reset_button.clicked.connect(self._reset_to_zero)
        btn_layout.addWidget(self.reset_button)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def load_from_config(self):
        """Load values from config.HOME_POSITION into spinboxes"""
        self._loading = True
        for joint, spinbox in self.spinboxes.items():
            spinbox.setValue(config.HOME_POSITION.get(joint, 0.0))
        self._loading = False

    def _on_value_changed(self):
        if not self._loading:
            self._save()
            self.position_changed.emit()

    def _save(self):
        """Save current spinbox values to config and file"""
        data = {}
        for joint, spinbox in self.spinboxes.items():
            val = spinbox.value()
            config.HOME_POSITION[joint] = val
            data[joint] = val
        try:
            with open(HOME_POSITION_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            logger.debug(f"Saved home position: {data}")
        except Exception as e:
            logger.error(f"Error saving home position: {e}")

    def _capture_current(self):
        """Capture current joint angles from the main GUI spinboxes"""
        gui = self._find_gui_instance()
        if not gui:
            logger.warning("Cannot capture: no GUI instance found")
            return
        self._loading = True
        for joint in self.spinboxes:
            spinbox_name = f'SpinBox{joint}'
            if hasattr(gui, spinbox_name):
                val = getattr(gui, spinbox_name).value()
                self.spinboxes[joint].setValue(val)
        self._loading = False
        self._save()
        self.position_changed.emit()

    def _reset_to_zero(self):
        self._loading = True
        for spinbox in self.spinboxes.values():
            spinbox.setValue(0.0)
        self._loading = False
        self._save()
        self.position_changed.emit()

    def _find_gui_instance(self):
        """Walk up the parent chain to find the CalibrationPanel's gui_instance"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'gui_instance'):
                return parent.gui_instance
            parent = parent.parent()
        return None


class ParkPositionWidget(QtWidgets.QWidget):
    """Widget for setting the park position (joint angles before shutdown)"""

    position_changed = QtCore.pyqtSignal()

    JOINT_LIMITS = {
        'Art1': (-97, 97),
        'Art2': (-90, 90),
        'Art3': (-90, 90),
        'Art4': (-180, 180),
        'Art5': (-90, 90),
        'Art6': (-180, 180),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinboxes = {}
        self._loading = False
        self.setup_ui()
        self.load_from_config()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        desc = QtWidgets.QLabel(
            "Position the robot moves to before shutdown. "
            "Gripper closes and motors disable after arrival."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 4px;")
        layout.addWidget(desc)

        grid = QtWidgets.QGridLayout()
        for i, (joint, (lo, hi)) in enumerate(self.JOINT_LIMITS.items()):
            label = QtWidgets.QLabel(f"{joint}:")
            label.setFixedWidth(40)
            grid.addWidget(label, i // 3, (i % 3) * 2)

            spinbox = QtWidgets.QDoubleSpinBox()
            spinbox.setRange(lo, hi)
            spinbox.setDecimals(1)
            spinbox.setSuffix("\u00b0")
            spinbox.setValue(config.PARK_POSITION.get(joint, 0.0))
            spinbox.valueChanged.connect(self._on_value_changed)
            grid.addWidget(spinbox, i // 3, (i % 3) * 2 + 1)
            self.spinboxes[joint] = spinbox

        layout.addLayout(grid)

        btn_layout = QtWidgets.QHBoxLayout()
        self.capture_button = QtWidgets.QPushButton("Capture Current")
        self.capture_button.setToolTip("Set park position to current joint angles")
        self.capture_button.clicked.connect(self._capture_current)
        btn_layout.addWidget(self.capture_button)

        self.reset_button = QtWidgets.QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self._reset_to_default)
        btn_layout.addWidget(self.reset_button)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def load_from_config(self):
        self._loading = True
        for joint, spinbox in self.spinboxes.items():
            spinbox.setValue(config.PARK_POSITION.get(joint, 0.0))
        self._loading = False

    def _on_value_changed(self):
        if not self._loading:
            self._save()
            self.position_changed.emit()

    def _save(self):
        data = {}
        for joint, spinbox in self.spinboxes.items():
            val = spinbox.value()
            config.PARK_POSITION[joint] = val
            data[joint] = val
        try:
            with open(PARK_POSITION_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            logger.debug(f"Saved park position: {data}")
        except Exception as e:
            logger.error(f"Error saving park position: {e}")

    def _capture_current(self):
        gui = self._find_gui_instance()
        if not gui:
            logger.warning("Cannot capture: no GUI instance found")
            return
        self._loading = True
        for joint in self.spinboxes:
            spinbox_name = f'SpinBox{joint}'
            if hasattr(gui, spinbox_name):
                val = getattr(gui, spinbox_name).value()
                self.spinboxes[joint].setValue(val)
        self._loading = False
        self._save()
        self.position_changed.emit()

    def _reset_to_default(self):
        self._loading = True
        defaults = {'Art1': 0.0, 'Art2': 90.0, 'Art3': -90.0,
                     'Art4': 0.0, 'Art5': 0.0, 'Art6': 0.0}
        for joint, spinbox in self.spinboxes.items():
            spinbox.setValue(defaults.get(joint, 0.0))
        self._loading = False
        self._save()
        self.position_changed.emit()

    def _find_gui_instance(self):
        parent = self.parent()
        while parent:
            if hasattr(parent, 'gui_instance'):
                return parent.gui_instance
            parent = parent.parent()
        return None


class CalibrationPanel(QtWidgets.QWidget):
    """Main calibration panel with direction verification, gripper calibration, and DH parameters"""

    def __init__(self, gui_instance, parent=None):
        super().__init__(parent)
        self.gui_instance = gui_instance
        self.joint_widgets = {}

        self.setup_ui()
        self.load_current_calibration()

        logger.info("Calibration panel initialised")

    def setup_ui(self):
        """Create the calibration panel UI"""
        main_layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel("<h2>Robot Calibration</h2>")
        main_layout.addWidget(header)

        # Scroll area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

        # --- Joint Calibration ---
        joint_section = CollapsibleSection("Joint Calibration", is_expanded=True)

        instructions = QtWidgets.QLabel(
            "Click +10\u00b0 to test each joint. If the robot moves opposite "
            "to the visualization, toggle to Rev."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; margin-bottom: 4px;")
        joint_section.add_widget(instructions)

        joint_info = [
            ('Art1', 'Base rotation'),
            ('Art2', 'Shoulder pitch'),
            ('Art3', 'Elbow pitch'),
            ('Art4', 'Wrist roll'),
            ('Art5', 'Wrist pitch'),
            ('Art6', 'Wrist yaw')
        ]
        for joint_name, description in joint_info:
            widget = JointCalibrationWidget(joint_name, description)
            widget.test_movement.connect(self.on_test_movement)
            widget.direction_changed.connect(self.on_joint_direction_changed)
            self.joint_widgets[joint_name] = widget
            joint_section.add_widget(widget)

        scroll_layout.addWidget(joint_section)

        # --- Gripper Calibration ---
        gripper_section = CollapsibleSection("Gripper Calibration", is_expanded=False)
        self.gripper_calibration = GripperCalibrationWidget()
        self.gripper_calibration.test_gripper.connect(self.on_test_gripper)
        self.gripper_calibration.limits_changed.connect(self._auto_save_gripper)
        gripper_section.add_widget(self.gripper_calibration)
        scroll_layout.addWidget(gripper_section)

        # --- Home Position ---
        home_section = CollapsibleSection("Home Position", is_expanded=False)
        self.home_position = HomePositionWidget()
        home_section.add_widget(self.home_position)
        scroll_layout.addWidget(home_section)

        # --- Park Position ---
        park_section = CollapsibleSection("Park Position", is_expanded=False)
        self.park_position = ParkPositionWidget()
        park_section.add_widget(self.park_position)
        scroll_layout.addWidget(park_section)

        # --- DH Parameters ---
        dh_section = CollapsibleSection("DH Parameters", is_expanded=False)
        self.dh_parameters = DHParametersWidget()
        dh_section.add_widget(self.dh_parameters)
        scroll_layout.addWidget(dh_section)

        # Accordion: expanding one section collapses the others
        self._sections = [joint_section, gripper_section, home_section,
                          park_section, dh_section]
        for section in self._sections:
            section.expanded.connect(self._on_section_expanded)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Save All button at the bottom
        self.save_all_button = QtWidgets.QPushButton("Save All Calibration Settings")
        self.save_all_button.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; "
            "padding: 8px; font-size: 13px;"
        )
        self.save_all_button.clicked.connect(self.save_all)
        main_layout.addWidget(self.save_all_button)

        # Status bar
        self.status_label = QtWidgets.QLabel("Status: Ready to calibrate")
        self.status_label.setStyleSheet("background-color: #e0e0e0; padding: 5px;")
        main_layout.addWidget(self.status_label)

    def _on_section_expanded(self, opened_section):
        """Accordion: collapse every section except the one just opened."""
        for section in self._sections:
            if section is not opened_section:
                section.collapse()

    def on_test_movement(self, joint_name, delta_angle):
        """Handle test movement button clicks"""
        logger.info(f"Test movement: {joint_name} {delta_angle:+.1f}°")

        # Get the corresponding spinbox from main GUI
        joint_spinbox_map = {
            'Art1': 'SpinBoxArt1',
            'Art2': 'SpinBoxArt2',
            'Art3': 'SpinBoxArt3',
            'Art4': 'SpinBoxArt4',
            'Art5': 'SpinBoxArt5',
            'Art6': 'SpinBoxArt6'
        }

        spinbox_name = joint_spinbox_map.get(joint_name)
        if spinbox_name and hasattr(self.gui_instance, spinbox_name):
            spinbox = getattr(self.gui_instance, spinbox_name)
            new_value = spinbox.value() + delta_angle
            spinbox.setValue(new_value)

            # Execute movement
            self.gui_instance.FKMoveJoint(joint_name)

            self.status_label.setText(f"Status: Moved {joint_name} {delta_angle:+.1f}° → {new_value:.1f}°")
            self.status_label.setStyleSheet("background-color: #ccffcc; padding: 5px;")

    def on_joint_direction_changed(self, joint_name, direction):
        """Send M569 command to firmware and update config.g for persistence."""
        drives = JOINT_TO_DRIVES.get(joint_name)
        if drives is None:
            return

        try:
            s_value = 0 if direction == 1 else 1
            dir_label = 'Forward' if direction == 1 else 'Reverse'

            # Send M569 commands to firmware for each drive
            commands_sent = 0
            if self.gui_instance and hasattr(self.gui_instance, 'command_sender'):
                for drive in drives:
                    command = f"M569 P{drive} S{s_value}"
                    if self.gui_instance.command_sender.send_if_connected(command):
                        commands_sent += 1
                    else:
                        logger.warning(f"Not connected - M569 P{drive} not sent")

            # Always persist to config.g (even when not connected)
            config_g_path = paths.get_exe_dir() / 'Firmware Configs' / 'config.g'
            set_joint_direction(config_g_path, joint_name, direction)

            if commands_sent > 0:
                logger.info(f"{joint_name} direction set to {dir_label} (sent {commands_sent} M569 command(s))")
                self.status_label.setText(f"Status: {joint_name} = {dir_label} (M569 sent)")
            else:
                logger.info(f"{joint_name} direction set to {dir_label} (saved to config.g, not connected)")
                self.status_label.setText(f"Status: {joint_name} = {dir_label} (saved, not connected)")
            self.status_label.setStyleSheet("background-color: #ccffcc; padding: 5px;")

        except Exception as e:
            logger.error(f"Error updating {joint_name} direction: {e}")
            self.status_label.setText(f"Status: Error - {e}")
            self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")

    def on_test_gripper(self, pwm_value):
        """Handle gripper test button clicks - send direct PWM command"""
        logger.info(f"Test gripper PWM: {pwm_value}")

        if not self.gui_instance:
            self.status_label.setText("Status: No GUI instance - cannot send command")
            self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")
            return

        # Convert PWM to servo angle (0-255 PWM -> 0-180 servo angle)
        servo_angle = int((pwm_value / 255.0) * 180.0)
        command = f"M280 P0 S{servo_angle}"

        # Send via command_sender if connected
        if hasattr(self.gui_instance, 'command_sender') and self.gui_instance.command_sender:
            sent = self.gui_instance.command_sender.send_if_connected(command)
            if sent:
                self.status_label.setText(f"Status: Sent gripper test PWM={pwm_value} (angle={servo_angle}°)")
                self.status_label.setStyleSheet("background-color: #ccffcc; padding: 5px;")
            else:
                self.status_label.setText("Status: Not connected - cannot send gripper command")
                self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")
        else:
            self.status_label.setText("Status: Command sender not available")
            self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")

    def load_current_calibration(self):
        """Load direction settings from config.g M569 commands"""
        try:
            config_g_path = paths.get_exe_dir() / 'Firmware Configs' / 'config.g'
            directions = get_joint_directions(config_g_path)

            for joint_name, direction in directions.items():
                if joint_name in self.joint_widgets:
                    self.joint_widgets[joint_name].set_direction(direction)

            self.status_label.setText("Status: Loaded motor directions from config.g")
            self.status_label.setStyleSheet("background-color: #ccffcc; padding: 5px;")
            logger.info("Loaded direction settings from config.g")

        except Exception as e:
            logger.error(f"Error loading calibration: {e}")
            logger.exception("Full traceback:")
            self.status_label.setText(f"Status: Error loading - {e}")
            self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")

    def _auto_save_gripper(self):
        """Auto-save gripper calibration when limits change."""
        try:
            gripper_data = {
                'pwm_open': self.gripper_calibration.get_open_pwm(),
                'pwm_closed': self.gripper_calibration.get_closed_pwm()
            }
            with open(GRIPPER_CALIBRATION_FILE, 'w') as f:
                json.dump(gripper_data, f, indent=4)
            self.gripper_calibration.apply_to_config()
            logger.debug(f"Auto-saved gripper calibration: {gripper_data}")
        except Exception as e:
            logger.error(f"Error auto-saving gripper calibration: {e}")

    def save_all(self):
        """Save all calibration settings to their respective files."""
        errors = []

        # DH parameters
        try:
            self.dh_parameters.save_parameters()
        except Exception as e:
            errors.append(f"DH parameters: {e}")

        # Gripper calibration
        try:
            self._auto_save_gripper()
        except Exception as e:
            errors.append(f"Gripper calibration: {e}")

        # Home position
        try:
            self.home_position._save()
        except Exception as e:
            errors.append(f"Home position: {e}")

        # Park position
        try:
            self.park_position._save()
        except Exception as e:
            errors.append(f"Park position: {e}")

        if errors:
            msg = "Some settings failed to save:\n" + "\n".join(errors)
            self.status_label.setText(f"Status: Save errors")
            self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")
            QtWidgets.QMessageBox.warning(self, "Save Errors", msg)
        else:
            self.status_label.setText("Status: All calibration settings saved")
            self.status_label.setStyleSheet("background-color: #ccffcc; padding: 5px;")
            logger.info("All calibration settings saved")

