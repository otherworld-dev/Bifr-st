"""
Robot Calibration Panel
Interactive UI for calibrating joint angles to match physical robot with DH parameters

This panel edits DH parameters directly (theta_offset and direction fields).
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from pathlib import Path
import json
import logging
from forward_kinematics import get_dh_params, reload_dh_parameters

logger = logging.getLogger(__name__)

# DH parameters file path
DH_PARAMS_FILE = Path(__file__).parent / 'dh_parameters.json'


class JointCalibrationWidget(QtWidgets.QWidget):
    """Widget for calibrating a single joint"""

    # Signal emitted when calibration values change
    calibration_changed = QtCore.pyqtSignal(str, float, int)  # joint_name, offset, direction
    test_movement = QtCore.pyqtSignal(str, float)  # joint_name, delta_angle

    def __init__(self, joint_name, joint_description, parent=None):
        super().__init__(parent)
        self.joint_name = joint_name
        self.joint_description = joint_description
        self.current_offset = 0.0
        self.current_direction = 1

        self.setup_ui()

    def setup_ui(self):
        """Create UI elements for this joint"""
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel(f"<b>{self.joint_name}</b>")
        header_label.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(header_label)

        desc_label = QtWidgets.QLabel(self.joint_description)
        desc_label.setStyleSheet("color: gray; font-size: 10px;")
        header_layout.addWidget(desc_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Frame for controls
        frame = QtWidgets.QFrame()
        frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        frame_layout = QtWidgets.QGridLayout(frame)

        # Row 0: Current firmware angle display
        frame_layout.addWidget(QtWidgets.QLabel("Firmware Angle:"), 0, 0)
        self.firmware_angle_label = QtWidgets.QLabel("0.00°")
        self.firmware_angle_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        frame_layout.addWidget(self.firmware_angle_label, 0, 1)

        # Row 1: Direction control
        frame_layout.addWidget(QtWidgets.QLabel("Direction:"), 1, 0)
        direction_layout = QtWidgets.QHBoxLayout()
        self.direction_button_group = QtWidgets.QButtonGroup(self)

        self.forward_radio = QtWidgets.QRadioButton("Forward (+1)")
        self.forward_radio.setChecked(True)
        self.direction_button_group.addButton(self.forward_radio, 1)
        direction_layout.addWidget(self.forward_radio)

        self.reverse_radio = QtWidgets.QRadioButton("Reverse (-1)")
        self.direction_button_group.addButton(self.reverse_radio, -1)
        direction_layout.addWidget(self.reverse_radio)

        direction_layout.addStretch()
        frame_layout.addLayout(direction_layout, 1, 1, 1, 3)

        # Row 2: Offset control
        frame_layout.addWidget(QtWidgets.QLabel("Offset (°):"), 2, 0)
        self.offset_spinbox = QtWidgets.QDoubleSpinBox()
        self.offset_spinbox.setRange(-180, 180)
        self.offset_spinbox.setDecimals(2)
        self.offset_spinbox.setSingleStep(1.0)
        self.offset_spinbox.setValue(0.0)
        frame_layout.addWidget(self.offset_spinbox, 2, 1)

        # Quick offset buttons
        offset_btn_layout = QtWidgets.QHBoxLayout()
        self.offset_minus_10 = QtWidgets.QPushButton("-10")
        self.offset_minus_10.setMaximumWidth(50)
        self.offset_minus_1 = QtWidgets.QPushButton("-1")
        self.offset_minus_1.setMaximumWidth(50)
        self.offset_plus_1 = QtWidgets.QPushButton("+1")
        self.offset_plus_1.setMaximumWidth(50)
        self.offset_plus_10 = QtWidgets.QPushButton("+10")
        self.offset_plus_10.setMaximumWidth(50)

        offset_btn_layout.addWidget(self.offset_minus_10)
        offset_btn_layout.addWidget(self.offset_minus_1)
        offset_btn_layout.addWidget(self.offset_plus_1)
        offset_btn_layout.addWidget(self.offset_plus_10)
        frame_layout.addLayout(offset_btn_layout, 2, 2, 1, 2)

        # Row 3: Calibrated angle display
        frame_layout.addWidget(QtWidgets.QLabel("Calibrated Angle:"), 3, 0)
        self.calibrated_angle_label = QtWidgets.QLabel("0.00°")
        self.calibrated_angle_label.setStyleSheet("font-weight: bold; color: #00aa00;")
        frame_layout.addWidget(self.calibrated_angle_label, 3, 1)

        # Row 4: Test movement buttons
        frame_layout.addWidget(QtWidgets.QLabel("Test Movement:"), 4, 0)
        test_btn_layout = QtWidgets.QHBoxLayout()

        self.test_minus_10 = QtWidgets.QPushButton("-10°")
        self.test_minus_10.setStyleSheet("background-color: #ffcccc;")
        self.test_minus_1 = QtWidgets.QPushButton("-1°")
        self.test_minus_1.setStyleSheet("background-color: #ffcccc;")
        self.test_plus_1 = QtWidgets.QPushButton("+1°")
        self.test_plus_1.setStyleSheet("background-color: #ccffcc;")
        self.test_plus_10 = QtWidgets.QPushButton("+10°")
        self.test_plus_10.setStyleSheet("background-color: #ccffcc;")

        test_btn_layout.addWidget(self.test_minus_10)
        test_btn_layout.addWidget(self.test_minus_1)
        test_btn_layout.addWidget(self.test_plus_1)
        test_btn_layout.addWidget(self.test_plus_10)
        frame_layout.addLayout(test_btn_layout, 4, 1, 1, 3)

        # Row 5: Status checkbox
        self.verified_checkbox = QtWidgets.QCheckBox("✓ Verified - Matches physical robot")
        self.verified_checkbox.setStyleSheet("color: green; font-weight: bold;")
        frame_layout.addWidget(self.verified_checkbox, 5, 0, 1, 4)

        main_layout.addWidget(frame)

        # Connect signals
        self.direction_button_group.buttonToggled.connect(self.on_direction_changed)
        self.offset_spinbox.valueChanged.connect(self.on_offset_changed)

        self.offset_minus_10.clicked.connect(lambda: self.adjust_offset(-10))
        self.offset_minus_1.clicked.connect(lambda: self.adjust_offset(-1))
        self.offset_plus_1.clicked.connect(lambda: self.adjust_offset(1))
        self.offset_plus_10.clicked.connect(lambda: self.adjust_offset(10))

        self.test_minus_10.clicked.connect(lambda: self.test_movement.emit(self.joint_name, -10))
        self.test_minus_1.clicked.connect(lambda: self.test_movement.emit(self.joint_name, -1))
        self.test_plus_1.clicked.connect(lambda: self.test_movement.emit(self.joint_name, 1))
        self.test_plus_10.clicked.connect(lambda: self.test_movement.emit(self.joint_name, 10))

    def on_direction_changed(self, button, checked):
        """Called when direction radio button changes"""
        # Only process when a button is being checked (not unchecked)
        if not checked:
            return
        direction = self.direction_button_group.checkedId()
        # Guard against invalid direction values
        if direction not in (1, -1):
            direction = 1
        self.current_direction = direction
        self.update_calibrated_angle()
        self.calibration_changed.emit(self.joint_name, self.current_offset, self.current_direction)

    def on_offset_changed(self, value):
        """Called when offset spinbox changes"""
        self.current_offset = value
        self.update_calibrated_angle()
        self.calibration_changed.emit(self.joint_name, self.current_offset, self.current_direction)

    def adjust_offset(self, delta):
        """Adjust offset by delta amount"""
        new_value = self.offset_spinbox.value() + delta
        self.offset_spinbox.setValue(new_value)

    def update_firmware_angle(self, angle):
        """Update the displayed firmware angle"""
        self.firmware_angle_label.setText(f"{angle:.2f}°")
        self.update_calibrated_angle()

    def update_calibrated_angle(self):
        """Recalculate and display calibrated angle"""
        firmware_angle = float(self.firmware_angle_label.text().replace('°', ''))
        calibrated = (firmware_angle * self.current_direction) + self.current_offset
        self.calibrated_angle_label.setText(f"{calibrated:.2f}°")

    def set_calibration(self, offset, direction):
        """Set calibration values programmatically"""
        self.current_offset = offset
        self.current_direction = direction

        self.offset_spinbox.setValue(offset)
        if direction == 1:
            self.forward_radio.setChecked(True)
        else:
            self.reverse_radio.setChecked(True)

        self.update_calibrated_angle()

    def get_calibration(self):
        """Get current calibration values"""
        return {
            'offset': self.current_offset,
            'direction': self.current_direction,
            'verified': self.verified_checkbox.isChecked()
        }


class CalibrationPanel(QtWidgets.QWidget):
    """Main calibration panel with all joints"""

    def __init__(self, gui_instance, parent=None):
        super().__init__(parent)
        self.gui_instance = gui_instance
        self.joint_widgets = {}

        self.setup_ui()
        self.load_current_calibration()

        logger.info("Calibration panel initialized")

    def setup_ui(self):
        """Create the calibration panel UI"""
        main_layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel("<h2>Robot Calibration</h2>")
        main_layout.addWidget(header)

        # Instructions
        instructions = QtWidgets.QLabel(
            "<b>Instructions:</b><br>"
            "1. <b>Home the robot first</b> using the Home button<br>"
            "2. For each joint, test movement with +/- buttons<br>"
            "3. Verify the 3D visualization matches physical robot movement<br>"
            "4. If direction is wrong, toggle 'Reverse'<br>"
            "5. Adjust offset if home position doesn't match 0°<br>"
            "6. Check '✓ Verified' when joint is correct<br>"
            "7. Click 'Save Calibration' when all joints verified"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("background-color: #ffffcc; padding: 10px; border: 1px solid #cccc00;")
        main_layout.addWidget(instructions)

        # Scroll area for joint widgets
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

        # Create joint calibration widgets
        joint_info = [
            ('Art1', 'Base rotation (X axis)'),
            ('Art2', 'Shoulder pitch (Y axis)'),
            ('Art3', 'Elbow pitch (Z axis)'),
            ('Art4', 'Wrist roll (U axis)'),
            ('Art5', 'Wrist pitch (V+W differential)'),
            ('Art6', 'Wrist yaw (V-W differential)')
        ]

        for joint_name, description in joint_info:
            widget = JointCalibrationWidget(joint_name, description)
            widget.calibration_changed.connect(self.on_calibration_changed)
            widget.test_movement.connect(self.on_test_movement)
            self.joint_widgets[joint_name] = widget
            scroll_layout.addWidget(widget)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Action buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.reset_button = QtWidgets.QPushButton("Reset All")
        self.reset_button.setToolTip("Reset all calibration to defaults (offset=0, direction=forward)")
        self.reset_button.clicked.connect(self.reset_calibration)
        button_layout.addWidget(self.reset_button)

        self.load_button = QtWidgets.QPushButton("Load from DH Params")
        self.load_button.setToolTip("Load calibration from dh_parameters.json")
        self.load_button.clicked.connect(self.load_current_calibration)
        button_layout.addWidget(self.load_button)

        button_layout.addStretch()

        self.save_button = QtWidgets.QPushButton("💾 Save Calibration")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.save_button.setToolTip("Save calibration to dh_parameters.json and apply immediately")
        self.save_button.clicked.connect(self.save_calibration)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

        # Status bar
        self.status_label = QtWidgets.QLabel("Status: Ready to calibrate")
        self.status_label.setStyleSheet("background-color: #e0e0e0; padding: 5px;")
        main_layout.addWidget(self.status_label)

    def on_calibration_changed(self, joint_name, offset, direction):
        """Handle calibration value changes"""
        logger.debug(f"Calibration changed: {joint_name} offset={offset}, direction={direction}")
        # Could auto-update visualization here if desired

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

    def load_current_calibration(self):
        """Load calibration from DH parameters file"""
        try:
            dh_params = get_dh_params()
            if dh_params is None:
                raise ValueError("DH parameters not loaded")

            # Map link index to joint name
            link_to_joint = {
                0: 'Art1',
                1: 'Art2',
                2: 'Art3',
                3: 'Art4',
                4: 'Art5',
                5: 'Art6'
            }

            for i, link_data in enumerate(dh_params):
                joint_name = link_to_joint.get(i)
                if joint_name and joint_name in self.joint_widgets:
                    # theta_offset in DH params is the calibration offset
                    offset = link_data.get('theta_offset', 0.0)
                    direction = link_data.get('direction', 1)
                    self.joint_widgets[joint_name].set_calibration(offset, direction)

            self.status_label.setText("Status: Loaded calibration from DH parameters")
            self.status_label.setStyleSheet("background-color: #ccffcc; padding: 5px;")
            logger.info("Loaded calibration from dh_parameters.json")

        except Exception as e:
            logger.error(f"Error loading calibration: {e}")
            logger.exception("Full traceback:")
            self.status_label.setText(f"Status: Error loading calibration - {e}")
            self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")

    def save_calibration(self):
        """Save calibration to DH parameters file"""
        try:
            # Check if all joints are verified
            unverified = []
            for joint_name, widget in self.joint_widgets.items():
                if not widget.verified_checkbox.isChecked():
                    unverified.append(joint_name)

            if unverified:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Unverified Joints",
                    f"The following joints are not verified:\n{', '.join(unverified)}\n\n"
                    "Do you want to save anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )

                if reply == QtWidgets.QMessageBox.No:
                    return

            # Load existing DH parameters to preserve geometry fields
            with open(DH_PARAMS_FILE, 'r') as f:
                dh_data = json.load(f)

            # Map joint name to link index
            joint_to_link = {
                'Art1': 0,
                'Art2': 1,
                'Art3': 2,
                'Art4': 3,
                'Art5': 4,
                'Art6': 5
            }

            # Update only theta_offset and direction fields
            for joint_name, widget in self.joint_widgets.items():
                cal = widget.get_calibration()
                link_idx = joint_to_link[joint_name]

                # Update calibration fields, preserve geometry
                dh_data['links'][link_idx]['theta_offset'] = cal['offset']
                dh_data['links'][link_idx]['direction'] = cal['direction']

            # Update metadata
            dh_data['version'] = '1.1'
            dh_data['description'] = 'Thor Robot DH Parameters with calibration'
            dh_data['date_modified'] = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd")

            # Save to DH parameters file
            with open(DH_PARAMS_FILE, 'w') as f:
                json.dump(dh_data, f, indent=4)

            # Reload DH parameters in FK module
            reload_dh_parameters()

            self.status_label.setText("Status: ✓ Calibration saved to DH parameters!")
            self.status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px; font-weight: bold;")
            logger.info("Calibration saved to dh_parameters.json")

            # Show success message
            QtWidgets.QMessageBox.information(
                self,
                "Calibration Saved",
                "Calibration saved to DH parameters!\n\n"
                "The new calibration is now active and will be used for:\n"
                "• 3D visualization\n"
                "• Forward kinematics\n"
                "• All future movements"
            )

        except Exception as e:
            logger.error(f"Error saving calibration: {e}")
            logger.exception("Calibration save error:")
            self.status_label.setText(f"Status: Error saving - {e}")
            self.status_label.setStyleSheet("background-color: #ffcccc; padding: 5px;")

            QtWidgets.QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save calibration:\n{e}"
            )

    def reset_calibration(self):
        """Reset all calibration to defaults"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Reset Calibration",
            "Reset all joints to default calibration?\n\n"
            "(Offset = 0°, Direction = Forward)\n\n"
            "This will not save automatically.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            for widget in self.joint_widgets.values():
                widget.set_calibration(0.0, 1)
                widget.verified_checkbox.setChecked(False)

            self.status_label.setText("Status: All calibration reset to defaults")
            self.status_label.setStyleSheet("background-color: #ffeecc; padding: 5px;")
            logger.info("Calibration reset to defaults")

    def update_firmware_angles(self, angles_dict):
        """Update displayed firmware angles from position feedback"""
        for joint_name, widget in self.joint_widgets.items():
            key = joint_name.lower()
            if key in angles_dict:
                widget.update_firmware_angle(angles_dict[key])
