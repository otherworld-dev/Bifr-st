# -*- coding: utf-8 -*-
"""
Bifrost Modern UI - Mode-Based Interface
Industry-standard robot control interface with mode switching

Modes:
- JOG: Manual joint control
- INVERSE: Inverse kinematics (Cartesian control)
- TEACH: Sequence programming
- TERMINAL: Console and debugging
- 3D VIEW: Full-screen visualization
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
                            QGridLayout, QLabel, QPushButton, QRadioButton,
                            QDoubleSpinBox, QCheckBox, QComboBox, QSpinBox,
                            QFrame, QButtonGroup, QStackedWidget, QTableWidget,
                            QTableWidgetItem, QHeaderView, QPlainTextEdit,
                            QLineEdit, QListWidget, QGroupBox, QSizePolicy)
from robot_3d_visualizer import Robot3DCanvas


class TableItemLabelWrapper:
    """
    Wrapper class to make QTableWidgetItem behave like QLabel for compatibility
    with existing bifrost.py code that calls .setText() on labels
    """
    def __init__(self, table_item):
        self.table_item = table_item

    def setText(self, text):
        """Delegate setText to QTableWidgetItem"""
        self.table_item.setText(text)

    def text(self):
        """Delegate text() to QTableWidgetItem"""
        return self.table_item.text()

    def setStyleSheet(self, stylesheet):
        """Handle stylesheet by setting background color for table items"""
        # Extract background-color from stylesheet
        if "background-color" in stylesheet:
            # Simple parsing for common patterns
            if "rgb(200, 255, 200)" in stylesheet:
                self.table_item.setBackground(QtGui.QColor(200, 255, 200))
            elif "rgb(255, 200, 200)" in stylesheet:
                self.table_item.setBackground(QtGui.QColor(255, 200, 200))
            elif "rgb(255, 255, 200)" in stylesheet:
                self.table_item.setBackground(QtGui.QColor(255, 255, 200))
            elif "rgb(200, 200, 200)" in stylesheet:
                self.table_item.setBackground(QtGui.QColor(200, 200, 200))
        # Ignore other stylesheet properties for table items


class ModernMainWindow(QMainWindow):
    """Modern mode-based GUI for Bifrost robot control"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bifrost - Thor Robot Control")
        self.setMinimumSize(1200, 750)

        # Create central widget
        self.centralwidget = QWidget()
        self.setCentralWidget(self.centralwidget)

        # Main layout
        main_layout = QVBoxLayout(self.centralwidget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Top bar (connection status)
        self.top_bar = ConnectionBar()
        main_layout.addWidget(self.top_bar)

        # Mode selector bar
        self.mode_selector = ModeSelectorBar()
        main_layout.addWidget(self.mode_selector)

        # Main content area (split left/right)
        content_splitter = QtWidgets.QSplitter(Qt.Horizontal)

        # Left panel: Mode-specific controls (40%)
        self.mode_stack = QStackedWidget()
        content_splitter.addWidget(self.mode_stack)

        # Right panel: Unified robot state (60%)
        self.robot_state_panel = RobotStatePanel()
        content_splitter.addWidget(self.robot_state_panel)

        # Set splitter proportions and initial sizes
        content_splitter.setStretchFactor(0, 40)  # Left: 40%
        content_splitter.setStretchFactor(1, 60)  # Right: 60%

        # Force initial sizes (40% / 60% of 1200px window = 480px / 720px)
        content_splitter.setSizes([480, 720])

        # Set minimum width for left panel so it can't be collapsed
        self.mode_stack.setMinimumWidth(400)

        # Prevent splitter panels from collapsing
        content_splitter.setCollapsible(0, False)  # Left panel
        content_splitter.setCollapsible(1, False)  # Right panel

        main_layout.addWidget(content_splitter)

        # Create mode panels
        self.setup_mode_panels()

        # Connect mode switching
        self.mode_selector.mode_changed.connect(self.switch_mode)

        # Default to JOG mode
        self.switch_mode(0)

    def setup_mode_panels(self):
        """Create all mode-specific panels"""
        # Mode 0: JOG
        self.jog_panel = JogModePanel()
        self.mode_stack.addWidget(self.jog_panel)

        # Mode 1: INVERSE
        self.inverse_panel = InverseModePanel()
        self.mode_stack.addWidget(self.inverse_panel)

        # Mode 2: TEACH
        self.teach_panel = TeachModePanel()
        self.mode_stack.addWidget(self.teach_panel)

        # Mode 3: TERMINAL
        self.terminal_panel = TerminalModePanel()
        self.mode_stack.addWidget(self.terminal_panel)

        # Mode 4: CALIBRATE
        from calibration_panel import CalibrationPanel
        # gui_instance will be set later by BifrostGUI
        self.calibration_panel = CalibrationPanel(gui_instance=None)
        self.mode_stack.addWidget(self.calibration_panel)

        # Mode 5: DH PARAMS
        from dh_panel import DHParametersPanel
        self.dh_panel = DHParametersPanel()
        self.mode_stack.addWidget(self.dh_panel)

        # Mode 6: FRAMES
        from frame_panel import FrameManagementPanel
        self.frames_panel = FrameManagementPanel()
        self.mode_stack.addWidget(self.frames_panel)

    def switch_mode(self, mode_index):
        """Switch to specified mode"""
        self.mode_stack.setCurrentIndex(mode_index)


class ConnectionBar(QFrame):
    """Top bar showing connection status and settings"""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(50)
        self.setMaximumHeight(50)
        self.setStyleSheet("ConnectionBar { background-color: #e8e8e8; border-bottom: 2px solid #ccc; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # App title
        title = QLabel("Bifrost")
        title_font = QtGui.QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        layout.addWidget(QLabel("|"))

        # Serial port
        self.SerialPortLabel = QLabel("COM Port:")
        layout.addWidget(self.SerialPortLabel)

        self.SerialPortComboBox = QComboBox()
        self.SerialPortComboBox.setMinimumWidth(80)
        layout.addWidget(self.SerialPortComboBox)

        self.SerialPortRefreshButton = QPushButton("⟳")
        self.SerialPortRefreshButton.setMaximumWidth(30)
        self.SerialPortRefreshButton.setToolTip("Refresh serial ports")
        layout.addWidget(self.SerialPortRefreshButton)

        # Baud rate
        layout.addWidget(QLabel("@"))
        self.BaudRateComboBox = QComboBox()
        self.BaudRateComboBox.setMinimumWidth(80)
        self.BaudRateComboBox.addItems([
            "9600", "14400", "19200", "28800", "38400",
            "57600", "115200", "230400", "250000", "500000", "1000000", "2000000"
        ])
        self.BaudRateComboBox.setCurrentText("115200")
        layout.addWidget(self.BaudRateComboBox)

        layout.addWidget(QLabel("|"))

        # Connection status
        layout.addWidget(QLabel("Status:"))
        self.RobotStateDisplay = QLabel("Disconnected")
        self.RobotStateDisplay.setFrameShape(QFrame.Box)
        self.RobotStateDisplay.setMinimumWidth(100)
        self.RobotStateDisplay.setAlignment(Qt.AlignCenter)
        self.RobotStateDisplay.setStyleSheet("background-color: rgb(255, 0, 0); font-weight: bold; padding: 3px;")
        layout.addWidget(self.RobotStateDisplay)

        layout.addStretch()

        # Connect/Disconnect button
        self.ConnectButton = QPushButton("Connect")
        self.ConnectButton.setMinimumWidth(100)
        self.ConnectButton.setMinimumHeight(35)
        connect_font = QtGui.QFont()
        connect_font.setBold(True)
        self.ConnectButton.setFont(connect_font)
        layout.addWidget(self.ConnectButton)

        layout.addWidget(QLabel("|"))

        # Pause button (M410 - Quick Stop)
        self.PauseButton = QPushButton("⏸ PAUSE")
        self.PauseButton.setMinimumWidth(90)
        self.PauseButton.setMinimumHeight(35)
        pause_font = QtGui.QFont()
        pause_font.setBold(True)
        self.PauseButton.setFont(pause_font)
        self.PauseButton.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: 2px solid #F57C00;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        self.PauseButton.setToolTip("Quick Stop (M410) - Pause movement")
        layout.addWidget(self.PauseButton)

        # Emergency Stop button (M112 - Full Emergency Stop)
        self.EmergencyStopButton = QPushButton("🛑 E-STOP")
        self.EmergencyStopButton.setMinimumWidth(100)
        self.EmergencyStopButton.setMinimumHeight(35)
        estop_font = QtGui.QFont()
        estop_font.setBold(True)
        estop_font.setPointSize(10)
        self.EmergencyStopButton.setFont(estop_font)
        self.EmergencyStopButton.setStyleSheet("""
            QPushButton {
                background-color: #D32F2F;
                color: white;
                border: 3px solid #B71C1C;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #C62828;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
        """)
        self.EmergencyStopButton.setToolTip("Emergency Stop (M112) - Requires M999 reset")
        layout.addWidget(self.EmergencyStopButton)

        # About button
        self.SettingsButton = QPushButton("ℹ")
        self.SettingsButton.setMaximumWidth(40)
        self.SettingsButton.setMinimumHeight(35)
        self.SettingsButton.setToolTip("About")
        layout.addWidget(self.SettingsButton)


class ModeSelectorBar(QFrame):
    """Mode selection buttons"""

    mode_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(50)
        self.setMaximumHeight(50)
        self.setStyleSheet("ModeSelectorBar { background-color: #d8d8d8; border-bottom: 2px solid #bbb; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Mode buttons
        self.mode_group = QButtonGroup()

        self.btn_jog = QPushButton("📐 JOG")
        self.btn_jog.setCheckable(True)
        self.btn_jog.setMinimumHeight(35)
        self.btn_jog.setMinimumWidth(120)
        self.mode_group.addButton(self.btn_jog, 0)
        layout.addWidget(self.btn_jog)

        self.btn_inverse = QPushButton("🎯 INVERSE")
        self.btn_inverse.setCheckable(True)
        self.btn_inverse.setMinimumHeight(35)
        self.btn_inverse.setMinimumWidth(130)
        self.mode_group.addButton(self.btn_inverse, 1)
        layout.addWidget(self.btn_inverse)

        self.btn_teach = QPushButton("💾 TEACH")
        self.btn_teach.setCheckable(True)
        self.btn_teach.setMinimumHeight(35)
        self.btn_teach.setMinimumWidth(120)
        self.mode_group.addButton(self.btn_teach, 2)
        layout.addWidget(self.btn_teach)

        self.btn_terminal = QPushButton("🖥 TERMINAL")
        self.btn_terminal.setCheckable(True)
        self.btn_terminal.setMinimumHeight(35)
        self.btn_terminal.setMinimumWidth(140)
        self.mode_group.addButton(self.btn_terminal, 3)
        layout.addWidget(self.btn_terminal)

        self.btn_calibrate = QPushButton("🎯 CALIBRATE")
        self.btn_calibrate.setCheckable(True)
        self.btn_calibrate.setMinimumHeight(35)
        self.btn_calibrate.setMinimumWidth(150)
        self.mode_group.addButton(self.btn_calibrate, 4)
        layout.addWidget(self.btn_calibrate)

        self.btn_dh_params = QPushButton("⚙ DH PARAMS")
        self.btn_dh_params.setCheckable(True)
        self.btn_dh_params.setMinimumHeight(35)
        self.btn_dh_params.setMinimumWidth(140)
        self.mode_group.addButton(self.btn_dh_params, 5)
        layout.addWidget(self.btn_dh_params)

        self.btn_frames = QPushButton("📐 FRAMES")
        self.btn_frames.setCheckable(True)
        self.btn_frames.setMinimumHeight(35)
        self.btn_frames.setMinimumWidth(120)
        self.mode_group.addButton(self.btn_frames, 6)
        layout.addWidget(self.btn_frames)

        layout.addStretch()

        # Set default
        self.btn_jog.setChecked(True)

        # Connect signals
        self.mode_group.buttonClicked.connect(self.on_mode_clicked)

        # Style selected button
        self.update_button_styles()

    def on_mode_clicked(self, button):
        """Handle mode button click"""
        mode_id = self.mode_group.id(button)
        self.mode_changed.emit(mode_id)
        self.update_button_styles()

    def update_button_styles(self):
        """Update visual style of mode buttons"""
        for button in self.mode_group.buttons():
            if button.isChecked():
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        font-weight: bold;
                        border: 2px solid #45a049;
                        border-radius: 3px;
                    }
                """)
            else:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #f0f0f0;
                        color: #333;
                        border: 1px solid #ccc;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                    }
                """)


class RobotStatePanel(QFrame):
    """Right panel - always visible robot state"""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title = QLabel("Robot State")
        title_font = QtGui.QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Horizontal layout: Joint table (left) + Gripper buttons (middle) + Slider (right)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(5)

        # Joint status table (J1-J6 only, no gripper) - expanded width
        self.joint_table = JointStatusTable()
        controls_row.addWidget(self.joint_table)

        # Gripper control buttons (compact middle column)
        gripper_buttons_group = QGroupBox("Gripper")
        gripper_buttons_layout = QVBoxLayout(gripper_buttons_group)
        gripper_buttons_layout.setContentsMargins(4, 6, 4, 4)
        gripper_buttons_layout.setSpacing(3)
        gripper_buttons_group.setMaximumWidth(90)

        # Position display with spinbox
        pos_row = QHBoxLayout()
        pos_row.setSpacing(2)
        pos_label = QLabel("Pos:")
        pos_label.setStyleSheet("font-size: 8pt;")
        pos_row.addWidget(pos_label)
        self.gripper_spinbox = QSpinBox()
        self.gripper_spinbox.setRange(0, 100)
        self.gripper_spinbox.setValue(0)
        self.gripper_spinbox.setSuffix("%")
        self.gripper_spinbox.setMaximumWidth(55)
        self.gripper_spinbox.setStyleSheet("font-size: 8pt;")
        self.gripper_spinbox.setObjectName("SpinBoxGrip")
        pos_row.addWidget(self.gripper_spinbox)
        gripper_buttons_layout.addLayout(pos_row)

        # Preset buttons (stacked)
        self.gripper_open_btn = QPushButton("🔓 Open")
        self.gripper_open_btn.setMinimumHeight(35)
        self.gripper_open_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        gripper_buttons_layout.addWidget(self.gripper_open_btn)

        self.gripper_close_btn = QPushButton("🔒 Close")
        self.gripper_close_btn.setMinimumHeight(35)
        self.gripper_close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        gripper_buttons_layout.addWidget(self.gripper_close_btn)

        # Quick adjustment buttons (2x2 grid, compact)
        adj_grid = QGridLayout()
        adj_grid.setSpacing(2)
        adj_grid.setContentsMargins(0, 3, 0, 0)

        self.gripper_inc10 = QPushButton("+10")
        self.gripper_inc10.setMinimumHeight(30)
        self.gripper_inc10.setStyleSheet("font-size: 9pt;")
        adj_grid.addWidget(self.gripper_inc10, 0, 0)

        self.gripper_inc1 = QPushButton("+1")
        self.gripper_inc1.setMinimumHeight(30)
        self.gripper_inc1.setStyleSheet("font-size: 9pt;")
        adj_grid.addWidget(self.gripper_inc1, 0, 1)

        self.gripper_dec10 = QPushButton("-10")
        self.gripper_dec10.setMinimumHeight(30)
        self.gripper_dec10.setStyleSheet("font-size: 9pt;")
        adj_grid.addWidget(self.gripper_dec10, 1, 0)

        self.gripper_dec1 = QPushButton("-1")
        self.gripper_dec1.setMinimumHeight(30)
        self.gripper_dec1.setStyleSheet("font-size: 9pt;")
        adj_grid.addWidget(self.gripper_dec1, 1, 1)

        gripper_buttons_layout.addLayout(adj_grid)

        # Constrain to match table height
        gripper_buttons_group.setMaximumHeight(225)
        controls_row.addWidget(gripper_buttons_group)

        # Gripper slider (right side, vertical) - constrained to table height
        slider_group = QFrame()
        slider_group.setFrameShape(QFrame.StyledPanel)
        slider_layout = QVBoxLayout(slider_group)
        slider_layout.setContentsMargins(2, 2, 2, 2)
        slider_layout.setSpacing(1)
        slider_group.setMaximumWidth(45)
        slider_group.setMaximumHeight(225)  # Match table height

        # Top label
        open_label = QLabel("🔓")
        open_label.setAlignment(Qt.AlignCenter)
        open_label.setStyleSheet("font-size: 12pt;")
        slider_layout.addWidget(open_label)

        # Vertical slider - sized to fit within constrained height
        self.gripper_slider = QtWidgets.QSlider(Qt.Vertical)
        self.gripper_slider.setRange(0, 100)
        self.gripper_slider.setValue(0)
        self.gripper_slider.setTickPosition(QtWidgets.QSlider.TicksLeft)
        self.gripper_slider.setTickInterval(25)
        self.gripper_slider.setInvertedAppearance(False)  # 0 at bottom (closed), 100 at top (open)
        slider_layout.addWidget(self.gripper_slider)

        # Bottom label
        closed_label = QLabel("🔒")
        closed_label.setAlignment(Qt.AlignCenter)
        closed_label.setStyleSheet("font-size: 12pt;")
        slider_layout.addWidget(closed_label)

        controls_row.addWidget(slider_group)

        # Align controls to top of row
        controls_row.setAlignment(Qt.AlignTop)

        # Connect preset buttons - store references for bifrost.py to connect
        self.gripper_close_btn.clicked.connect(lambda: self.gripper_slider.setValue(0))
        self.gripper_open_btn.clicked.connect(lambda: self.gripper_slider.setValue(100))

        # Connect slider and spinbox
        self.gripper_slider.valueChanged.connect(self.gripper_spinbox.setValue)
        self.gripper_spinbox.valueChanged.connect(self.gripper_slider.setValue)

        # Add controls row to main layout
        layout.addLayout(controls_row)

        # 3D visualization - directly embedded to maximize space
        # Create 3D canvas widget - full width and height (increased size)
        self.robot_3d_canvas = Robot3DCanvas(self, width=7.5, height=6.5, dpi=95)
        self.robot_3d_canvas.setMinimumHeight(500)
        layout.addWidget(self.robot_3d_canvas)

        # Simple controls row (compact) - at bottom
        viz_controls = QHBoxLayout()
        viz_controls.setSpacing(8)
        viz_controls.setContentsMargins(0, 0, 0, 0)
        self.show_trajectory_check = QCheckBox("Trajectory")
        self.show_trajectory_check.setChecked(True)
        self.auto_rotate_check = QCheckBox("Auto-rotate")
        self.auto_rotate_check.setChecked(False)
        viz_controls.addWidget(self.show_trajectory_check)
        viz_controls.addWidget(self.auto_rotate_check)
        viz_controls.addStretch()
        layout.addLayout(viz_controls)


class JointStatusTable(QTableWidget):
    """Unified joint status table with controls"""

    def __init__(self):
        super().__init__()

        # Setup table
        self.setRowCount(6)  # J1-J6 only (gripper separated)
        self.setColumnCount(8)

        headers = ["Joint", "Cmd", "Actual", "ES", "[-10]", "[-1]", "[+1]", "[+10]"]
        self.setHorizontalHeaderLabels(headers)

        # Configure table appearance
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # Fill available space
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)  # Joint name fixed width
        self.horizontalHeader().resizeSection(0, 90)  # Set Joint column width to 90px
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # ES fixed
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setMinimumHeight(205)
        self.setMaximumHeight(225)

        # Populate rows (J1-J6 only, no gripper)
        joint_names = ["J1", "J2", "J3", "J4", "J5", "J6"]
        axis_labels = ["X", "Y", "Z", "U", "V", "W"]  # Corresponding axes

        for row, joint_name in enumerate(joint_names):
            # Joint name with axis label
            display_name = f"{joint_name} ({axis_labels[row]})"
            name_item = QTableWidgetItem(display_name)
            name_item.setTextAlignment(Qt.AlignCenter)
            name_font = QtGui.QFont()
            name_font.setBold(True)
            name_item.setFont(name_font)
            self.setItem(row, 0, name_item)

            # Command value (editable spinbox)
            cmd_spin = QDoubleSpinBox()
            cmd_spin.setAlignment(Qt.AlignCenter)
            # Set proper limits based on joint type (Art2, Art3, Art5 have 90° range)
            if joint_name in ['Art2', 'Art3', 'Art5']:
                cmd_spin.setMinimum(-90.0)
                cmd_spin.setMaximum(90.0)
            elif row < 6:  # Other joints (Art1, Art4, Art6)
                cmd_spin.setMinimum(-180.0)
                cmd_spin.setMaximum(180.0)
            else:  # Gripper
                cmd_spin.setMinimum(0.0)
                cmd_spin.setMaximum(100.0)
            cmd_spin.setDecimals(2 if row < 6 else 0)
            cmd_spin.setObjectName(f"SpinBox{joint_name}")
            self.setCellWidget(row, 1, cmd_spin)

            # Actual value (read-only)
            actual_item = QTableWidgetItem("0.0")
            actual_item.setTextAlignment(Qt.AlignCenter)
            actual_item.setFlags(Qt.ItemIsEnabled)
            actual_item.setBackground(QtGui.QColor(240, 240, 240))
            self.setItem(row, 2, actual_item)

            # Endstop status
            es_item = QTableWidgetItem("✓")
            es_item.setTextAlignment(Qt.AlignCenter)
            es_item.setBackground(QtGui.QColor(200, 255, 200))
            self.setItem(row, 3, es_item)

            # Inc/Dec buttons
            for col, delta in enumerate([-10, -1, 1, 10], start=4):
                btn = QPushButton(f"{delta:+d}")
                btn.setProperty("delta", delta)
                btn.setProperty("joint", joint_name)
                btn.setMinimumHeight(28)  # Make buttons taller
                # Remove max width - let buttons stretch to fill space
                self.setCellWidget(row, col, btn)

        # Store references for easy access
        self.spinboxes = {}
        self.actual_items = {}
        self.endstop_items = {}

        for row, joint_name in enumerate(joint_names):
            self.spinboxes[joint_name] = self.cellWidget(row, 1)
            self.actual_items[joint_name] = self.item(row, 2)
            self.endstop_items[joint_name] = self.item(row, 3)


class JogModePanel(QFrame):
    """MODE: JOG - Manual joint control"""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumSize(380, 600)  # Increased from 400 to 600 for more height
        self.setStyleSheet("JogModePanel { background-color: #f5f5f5; }")  # Light gray background

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)  # Add spacing between items

        # Movement type
        move_group = QGroupBox("Movement Type")
        move_layout = QVBoxLayout(move_group)

        self.G0MoveRadioButton = QRadioButton("Rapid (G0)")
        self.G0MoveRadioButton.setChecked(True)
        move_layout.addWidget(self.G0MoveRadioButton)

        self.G1MoveRadioButton = QRadioButton("Feed (G1)")
        move_layout.addWidget(self.G1MoveRadioButton)

        # Feed rate
        feed_layout = QHBoxLayout()
        self.FeedRateLabel = QLabel("Feed Rate:")
        self.FeedRateLabel.setEnabled(False)
        feed_layout.addWidget(self.FeedRateLabel)

        self.FeedRateInput = QSpinBox()
        self.FeedRateInput.setRange(1, 10000)
        self.FeedRateInput.setValue(1000)
        self.FeedRateInput.setSuffix(" mm/min")
        self.FeedRateInput.setEnabled(False)
        feed_layout.addWidget(self.FeedRateInput)

        move_layout.addLayout(feed_layout)
        layout.addWidget(move_group)

        # Connect radio buttons to enable/disable feedrate
        self.G1MoveRadioButton.toggled.connect(self.FeedRateLabel.setEnabled)
        self.G1MoveRadioButton.toggled.connect(self.FeedRateInput.setEnabled)

        # Jog mode
        self.JogModeCheckBox = QCheckBox("☑ Jog Mode (Live Movement)")
        jog_font = QtGui.QFont()
        jog_font.setBold(True)
        self.JogModeCheckBox.setFont(jog_font)
        self.JogModeCheckBox.setStyleSheet("color: rgb(200, 80, 0);")
        layout.addWidget(self.JogModeCheckBox)

        # Execute Movement button (visible when jog mode is OFF)
        self.ExecuteMovementButton = QPushButton("▶ Execute Movement")
        self.ExecuteMovementButton.setMinimumHeight(50)
        self.ExecuteMovementButton.setMinimumWidth(200)
        exec_font = QtGui.QFont()
        exec_font.setPointSize(11)
        exec_font.setBold(True)
        self.ExecuteMovementButton.setFont(exec_font)
        self.ExecuteMovementButton.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: 2px solid #1976D2;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
                border: 2px solid #9E9E9E;
            }
        """)
        self.ExecuteMovementButton.setToolTip("Execute movement to all currently set joint positions (G0/G1)")
        layout.addWidget(self.ExecuteMovementButton)

        layout.addStretch()

        # Quick commands
        quick_group = QGroupBox("Quick Commands")
        quick_layout = QVBoxLayout(quick_group)

        self.HomeButton = QPushButton("🏠 Home All Axes")
        self.HomeButton.setMinimumHeight(40)
        self.HomeButton.setMinimumWidth(200)
        quick_layout.addWidget(self.HomeButton)

        self.ZeroPositionButton = QPushButton("Zero All Positions")
        self.ZeroPositionButton.setMinimumHeight(40)
        self.ZeroPositionButton.setMinimumWidth(200)
        quick_layout.addWidget(self.ZeroPositionButton)

        self.KillAlarmLockButton = QPushButton("⚠ E-Stop")
        self.KillAlarmLockButton.setMinimumHeight(40)
        self.KillAlarmLockButton.setMinimumWidth(200)
        quick_layout.addWidget(self.KillAlarmLockButton)

        layout.addWidget(quick_group)


class InverseModePanel(QFrame):
    """MODE: INVERSE - Inverse kinematics control"""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Cartesian Target Position")
        title_font = QtGui.QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Visual directional pad
        pad_frame = QFrame()
        pad_frame.setFrameShape(QFrame.Box)
        pad_frame.setMinimumHeight(200)
        pad_layout = QGridLayout(pad_frame)

        # Y+ button
        self.IkIncButtonY = QPushButton("Y+")
        self.IkIncButtonY.setMinimumSize(60, 60)
        pad_layout.addWidget(self.IkIncButtonY, 0, 1)

        # X- button
        self.IkDecButtonX = QPushButton("X-")
        self.IkDecButtonX.setMinimumSize(60, 60)
        pad_layout.addWidget(self.IkDecButtonX, 1, 0)

        # Center label
        center_label = QLabel("[XYZ]")
        center_label.setAlignment(Qt.AlignCenter)
        center_label.setStyleSheet("border: 2px solid #999; border-radius: 5px; font-weight: bold;")
        center_label.setMinimumSize(60, 60)
        pad_layout.addWidget(center_label, 1, 1)

        # X+ button
        self.IkIncButtonX = QPushButton("X+")
        self.IkIncButtonX.setMinimumSize(60, 60)
        pad_layout.addWidget(self.IkIncButtonX, 1, 2)

        # Y- button
        self.IkDecButtonY = QPushButton("Y-")
        self.IkDecButtonY.setMinimumSize(60, 60)
        pad_layout.addWidget(self.IkDecButtonY, 2, 1)

        layout.addWidget(pad_frame)

        # Z axis controls
        z_group = QGroupBox("Z Axis")
        z_layout = QVBoxLayout(z_group)

        z_btn_layout = QHBoxLayout()
        self.IkIncButtonZ = QPushButton("▲ Z+")
        self.IkIncButtonZ.setMinimumHeight(40)
        z_btn_layout.addWidget(self.IkIncButtonZ)

        self.IkDecButtonZ = QPushButton("▼ Z-")
        self.IkDecButtonZ.setMinimumHeight(40)
        z_btn_layout.addWidget(self.IkDecButtonZ)

        z_layout.addLayout(z_btn_layout)
        layout.addWidget(z_group)

        # Position inputs
        pos_group = QGroupBox("Target Position")
        pos_layout = QGridLayout(pos_group)

        # X
        pos_layout.addWidget(QLabel("X:"), 0, 0)
        self.IKInputSpinBoxX = QDoubleSpinBox()
        self.IKInputSpinBoxX.setRange(-999, 999)
        self.IKInputSpinBoxX.setDecimals(2)
        self.IKInputSpinBoxX.setSuffix(" mm")
        pos_layout.addWidget(self.IKInputSpinBoxX, 0, 1)

        # Y
        pos_layout.addWidget(QLabel("Y:"), 1, 0)
        self.IKInputSpinBoxY = QDoubleSpinBox()
        self.IKInputSpinBoxY.setRange(-999, 999)
        self.IKInputSpinBoxY.setDecimals(2)
        self.IKInputSpinBoxY.setSuffix(" mm")
        pos_layout.addWidget(self.IKInputSpinBoxY, 1, 1)

        # Z
        pos_layout.addWidget(QLabel("Z:"), 2, 0)
        self.IKInputSpinBoxZ = QDoubleSpinBox()
        self.IKInputSpinBoxZ.setRange(-999, 999)
        self.IKInputSpinBoxZ.setDecimals(2)
        self.IKInputSpinBoxZ.setSuffix(" mm")
        pos_layout.addWidget(self.IKInputSpinBoxZ, 2, 1)

        layout.addWidget(pos_group)

        # Calculate button
        self.CalculateIKButton = QPushButton("Calculate IK Solution")
        self.CalculateIKButton.setMinimumHeight(35)
        layout.addWidget(self.CalculateIKButton)

        # IK solution display
        self.IkOutputValueFrame = QFrame()
        self.IkOutputValueFrame.setFrameShape(QFrame.Box)
        self.IkOutputValueFrame.setStyleSheet("background-color: rgb(255, 255, 255);")
        sol_layout = QVBoxLayout(self.IkOutputValueFrame)

        # Individual joint output labels (required by bifrost.py)
        output_grid = QGridLayout()
        output_grid.addWidget(QLabel("X:"), 0, 0)
        self.IkOutputValueX = QLabel("--")
        self.IkOutputValueX.setAlignment(Qt.AlignCenter)
        output_grid.addWidget(self.IkOutputValueX, 0, 1)

        output_grid.addWidget(QLabel("Y:"), 0, 2)
        self.IkOutputValueY = QLabel("--")
        self.IkOutputValueY.setAlignment(Qt.AlignCenter)
        output_grid.addWidget(self.IkOutputValueY, 0, 3)

        output_grid.addWidget(QLabel("Z:"), 0, 4)
        self.IkOutputValueZ = QLabel("--")
        self.IkOutputValueZ.setAlignment(Qt.AlignCenter)
        output_grid.addWidget(self.IkOutputValueZ, 0, 5)

        sol_layout.addLayout(output_grid)

        layout.addWidget(self.IkOutputValueFrame)

        layout.addStretch()


class PointEditDialog(QtWidgets.QDialog):
    """Dialog for adding/editing sequence points manually"""

    def __init__(self, parent=None, point_data=None, point_index=None):
        """
        Args:
            parent: Parent widget
            point_data: Dict with q1-q6, gripper, delay for editing (None for new point)
            point_index: Index of point being edited (None for new point)
        """
        super().__init__(parent)
        self.point_index = point_index
        self.setWindowTitle("Edit Point" if point_data else "Add Manual Point")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Joint inputs
        joints_group = QGroupBox("Joint Positions (degrees)")
        joints_layout = QGridLayout(joints_group)

        self.joint_spinboxes = {}
        joint_names = ['q1', 'q2', 'q3', 'q4', 'q5', 'q6']
        for i, name in enumerate(joint_names):
            row, col = i // 2, (i % 2) * 2
            joints_layout.addWidget(QLabel(f"{name.upper()}:"), row, col)
            spinbox = QDoubleSpinBox()
            spinbox.setRange(-360.0, 360.0)
            spinbox.setDecimals(2)
            spinbox.setSingleStep(1.0)
            spinbox.setSuffix("°")
            if point_data:
                spinbox.setValue(point_data.get(name, 0.0))
            self.joint_spinboxes[name] = spinbox
            joints_layout.addWidget(spinbox, row, col + 1)

        layout.addWidget(joints_group)

        # Gripper and delay
        extras_group = QGroupBox("Gripper & Timing")
        extras_layout = QGridLayout(extras_group)

        extras_layout.addWidget(QLabel("Gripper:"), 0, 0)
        self.gripper_spinbox = QDoubleSpinBox()
        self.gripper_spinbox.setRange(0.0, 100.0)
        self.gripper_spinbox.setDecimals(0)
        self.gripper_spinbox.setSingleStep(5.0)
        self.gripper_spinbox.setSuffix("%")
        if point_data:
            self.gripper_spinbox.setValue(point_data.get('gripper', 0.0))
        extras_layout.addWidget(self.gripper_spinbox, 0, 1)

        extras_layout.addWidget(QLabel("Delay:"), 1, 0)
        self.delay_spinbox = QDoubleSpinBox()
        self.delay_spinbox.setRange(0.0, 60.0)
        self.delay_spinbox.setDecimals(1)
        self.delay_spinbox.setSingleStep(0.5)
        self.delay_spinbox.setSuffix("s")
        self.delay_spinbox.setValue(point_data.get('delay', 1.0) if point_data else 1.0)
        extras_layout.addWidget(self.delay_spinbox, 1, 1)

        layout.addWidget(extras_group)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def get_point_data(self):
        """Return dict with all point values"""
        return {
            'q1': self.joint_spinboxes['q1'].value(),
            'q2': self.joint_spinboxes['q2'].value(),
            'q3': self.joint_spinboxes['q3'].value(),
            'q4': self.joint_spinboxes['q4'].value(),
            'q5': self.joint_spinboxes['q5'].value(),
            'q6': self.joint_spinboxes['q6'].value(),
            'gripper': self.gripper_spinbox.value(),
            'delay': self.delay_spinbox.value()
        }


class TeachModePanel(QFrame):
    """MODE: TEACH - Sequence programming"""

    # Signals for manual point operations
    manualPointRequested = pyqtSignal()  # Request to open add dialog
    pointEditRequested = pyqtSignal(int)  # Request to edit point at index
    importCsvRequested = pyqtSignal()  # Request to import CSV file

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Sequence name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Sequence:"))
        self.SequenceNameEdit = QLineEdit("Untitled_Sequence")
        name_layout.addWidget(self.SequenceNameEdit)
        layout.addLayout(name_layout)

        # Point list
        list_label = QLabel("Sequence Points:")
        layout.addWidget(list_label)

        self.sequencePointsList = QListWidget()
        self.sequencePointsList.setMinimumHeight(250)
        layout.addWidget(self.sequencePointsList, 1)  # Stretch factor 1 to fill remaining space

        # Recording controls
        rec_group = QGroupBox("Recording")
        rec_layout = QVBoxLayout(rec_group)

        self.sequenceRecordButton = QPushButton("⏺ Record Current Position")
        self.sequenceRecordButton.setMinimumHeight(35)
        rec_layout.addWidget(self.sequenceRecordButton)

        self.sequenceAddManualButton = QPushButton("✏ Add Manual Point")
        self.sequenceAddManualButton.setMinimumHeight(30)
        self.sequenceAddManualButton.clicked.connect(lambda: self.manualPointRequested.emit())
        rec_layout.addWidget(self.sequenceAddManualButton)

        self.sequenceDeleteButton = QPushButton("🗑 Delete Selected Point")
        self.sequenceDeleteButton.setMinimumHeight(30)
        rec_layout.addWidget(self.sequenceDeleteButton)

        self.sequenceClearButton = QPushButton("🆕 Clear All Points")
        self.sequenceClearButton.setMinimumHeight(30)
        rec_layout.addWidget(self.sequenceClearButton)

        layout.addWidget(rec_group)

        # Playback controls
        playback_group = QGroupBox("Playback")
        playback_layout = QVBoxLayout(playback_group)

        # Play/Pause/Stop buttons
        play_btn_layout = QHBoxLayout()
        self.sequencePlayButton = QPushButton("▶ Play")
        self.sequencePlayButton.setMinimumHeight(30)
        play_btn_layout.addWidget(self.sequencePlayButton)

        self.sequencePauseButton = QPushButton("⏸ Pause")
        self.sequencePauseButton.setMinimumHeight(30)
        self.sequencePauseButton.setEnabled(False)
        play_btn_layout.addWidget(self.sequencePauseButton)

        self.sequenceStopButton = QPushButton("⏹ Stop")
        self.sequenceStopButton.setMinimumHeight(30)
        self.sequenceStopButton.setEnabled(False)
        play_btn_layout.addWidget(self.sequenceStopButton)

        playback_layout.addLayout(play_btn_layout)

        # Speed and loop controls
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.sequenceSpeedSpinBox = QDoubleSpinBox()
        self.sequenceSpeedSpinBox.setRange(0.1, 10.0)
        self.sequenceSpeedSpinBox.setSingleStep(0.1)
        self.sequenceSpeedSpinBox.setValue(1.0)
        self.sequenceSpeedSpinBox.setSuffix("x")
        speed_layout.addWidget(self.sequenceSpeedSpinBox)

        self.sequenceLoopCheckBox = QCheckBox("Loop")
        speed_layout.addWidget(self.sequenceLoopCheckBox)

        playback_layout.addLayout(speed_layout)

        # Delay control
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay:"))
        self.sequenceDelaySpinBox = QDoubleSpinBox()
        self.sequenceDelaySpinBox.setRange(0.0, 60.0)
        self.sequenceDelaySpinBox.setSingleStep(0.1)
        self.sequenceDelaySpinBox.setValue(1.0)
        self.sequenceDelaySpinBox.setSuffix("s")
        delay_layout.addWidget(self.sequenceDelaySpinBox)

        playback_layout.addLayout(delay_layout)

        layout.addWidget(playback_group)

        # File operations
        file_layout = QHBoxLayout()
        self.sequenceSaveButton = QPushButton("💾 Save")
        file_layout.addWidget(self.sequenceSaveButton)

        self.sequenceLoadButton = QPushButton("📂 Load")
        file_layout.addWidget(self.sequenceLoadButton)

        self.sequenceImportCsvButton = QPushButton("📥 Import CSV")
        self.sequenceImportCsvButton.clicked.connect(lambda: self.importCsvRequested.emit())
        file_layout.addWidget(self.sequenceImportCsvButton)

        layout.addLayout(file_layout)

        # Double-click to edit point
        self.sequencePointsList.itemDoubleClicked.connect(self._on_point_double_clicked)

    def _on_point_double_clicked(self, item):
        """Handle double-click on a point to request editing"""
        index = self.sequencePointsList.row(item)
        self.pointEditRequested.emit(index)


class TerminalModePanel(QFrame):
    """MODE: TERMINAL - Console and debugging"""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Command input
        input_group = QGroupBox("G-Code / Command Input")
        input_layout = QVBoxLayout(input_group)

        cmd_layout = QHBoxLayout()
        self.ConsoleInput = QLineEdit()
        self.ConsoleInput.setPlaceholderText("Enter command (e.g., M114, G28, etc.)")
        cmd_layout.addWidget(self.ConsoleInput)

        self.ConsoleButtonSend = QPushButton("Send")
        self.ConsoleButtonSend.setMinimumWidth(80)
        cmd_layout.addWidget(self.ConsoleButtonSend)

        input_layout.addLayout(cmd_layout)

        # Quick commands
        quick_layout = QHBoxLayout()
        self.QuickM114Button = QPushButton("M114 (Position)")
        quick_layout.addWidget(self.QuickM114Button)

        self.QuickM119Button = QPushButton("M119 (Endstops)")
        quick_layout.addWidget(self.QuickM119Button)

        self.QuickG28Button = QPushButton("G28 (Home)")
        quick_layout.addWidget(self.QuickG28Button)

        input_layout.addLayout(quick_layout)

        layout.addWidget(input_group)

        # Console options
        options_layout = QHBoxLayout()
        self.ConsoleShowVerbosecheckBox = QCheckBox("Show M114 Verbose")
        options_layout.addWidget(self.ConsoleShowVerbosecheckBox)

        self.ConsoleShowOkRespcheckBox = QCheckBox("Show 'ok' Responses")
        options_layout.addWidget(self.ConsoleShowOkRespcheckBox)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Console output
        output_label = QLabel("Console Output:")
        layout.addWidget(output_label)

        self.ConsoleOutput = QPlainTextEdit()
        self.ConsoleOutput.setReadOnly(True)
        self.ConsoleOutput.setMinimumHeight(300)
        layout.addWidget(self.ConsoleOutput, 1)  # Stretch factor 1 to fill remaining space

        # Clear button
        self.ConsoleClearButton = QPushButton("Clear Console")
        layout.addWidget(self.ConsoleClearButton)


class Ui_MainWindow:
    """Main UI class compatible with existing bifrost.py interface"""

    def setup_mode_panels(self):
        """Create all mode-specific panels"""
        # Mode 0: JOG
        self.jog_panel = JogModePanel()
        self.mode_stack.addWidget(self.jog_panel)

        # Mode 1: INVERSE
        self.inverse_panel = InverseModePanel()
        self.mode_stack.addWidget(self.inverse_panel)

        # Mode 2: TEACH
        self.teach_panel = TeachModePanel()
        self.mode_stack.addWidget(self.teach_panel)

        # Mode 3: TERMINAL
        self.terminal_panel = TerminalModePanel()
        self.mode_stack.addWidget(self.terminal_panel)

        # Mode 4: CALIBRATE
        from calibration_panel import CalibrationPanel
        # gui_instance will be set later by BifrostGUI
        self.calibration_panel = CalibrationPanel(gui_instance=None)
        self.mode_stack.addWidget(self.calibration_panel)

        # Mode 5: DH PARAMS
        from dh_panel import DHParametersPanel
        self.dh_panel = DHParametersPanel()
        self.mode_stack.addWidget(self.dh_panel)

        # Mode 6: FRAMES
        from frame_panel import FrameManagementPanel
        self.frames_panel = FrameManagementPanel()
        self.mode_stack.addWidget(self.frames_panel)

    def switch_mode(self, mode_index):
        """Switch to specified mode"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Switching to mode {mode_index}, stack has {self.mode_stack.count()} widgets")
        self.mode_stack.setCurrentIndex(mode_index)
        current = self.mode_stack.currentWidget()
        if current:
            logger.info(f"Current widget after switch: {current.__class__.__name__}")
            current.show()  # Force show the current widget
            current.raise_()  # Bring to front

    def _fix_splitter_sizes(self):
        """Force splitter to correct sizes after window is shown"""
        if hasattr(self, 'content_splitter'):
            self.content_splitter.setSizes([480, 720])
            # Force all widgets to show
            self.top_bar.show()
            self.mode_selector.show()
            self.mode_stack.show()
            self.robot_state_panel.show()

    def setupUi(self, MainWindow):
        """Setup the modern UI directly in MainWindow"""
        # Setup window properties
        MainWindow.setWindowTitle("Bifrost - Thor Robot Control")
        MainWindow.setMinimumSize(1300, 800)
        MainWindow.resize(1400, 850)  # Default size to ensure everything fits

        # Create central widget
        self.centralwidget = QWidget()
        MainWindow.setCentralWidget(self.centralwidget)

        # Main layout
        main_layout = QVBoxLayout(self.centralwidget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Top bar (connection status)
        self.top_bar = ConnectionBar()
        main_layout.addWidget(self.top_bar)

        # Mode selector bar
        self.mode_selector = ModeSelectorBar()
        main_layout.addWidget(self.mode_selector)

        # Main content area (split left/right)
        content_splitter = QtWidgets.QSplitter(Qt.Horizontal)

        # Left panel: Mode-specific controls (40%)
        self.mode_stack = QStackedWidget()
        content_splitter.addWidget(self.mode_stack)

        # Right panel: Unified robot state (60%)
        self.robot_state_panel = RobotStatePanel()
        content_splitter.addWidget(self.robot_state_panel)

        # Set splitter proportions and initial sizes
        content_splitter.setStretchFactor(0, 40)  # Left: 40%
        content_splitter.setStretchFactor(1, 60)  # Right: 60%

        # Force initial sizes (40% / 60% of 1200px window = 480px / 720px)
        content_splitter.setSizes([480, 720])

        # Set minimum width for left panel so it can't be collapsed
        self.mode_stack.setMinimumWidth(400)

        # Prevent splitter panels from collapsing
        content_splitter.setCollapsible(0, False)  # Left panel
        content_splitter.setCollapsible(1, False)  # Right panel

        main_layout.addWidget(content_splitter)

        # Store reference for later use
        self.content_splitter = content_splitter

        # Create mode panels
        self.setup_mode_panels()

        # Connect mode switching
        self.mode_selector.mode_changed.connect(self.switch_mode)

        # Default to JOG mode
        self.switch_mode(0)

        # CRITICAL FIX: Apply splitter sizes after Qt processes events
        # This ensures window is fully realized before setting sizes
        QtCore.QTimer.singleShot(10, self._fix_splitter_sizes)

        # Now forward widget references for bifrost.py compatibility

        # Connection bar widgets
        self.SerialPortComboBox = self.top_bar.SerialPortComboBox
        self.SerialPortRefreshButton = self.top_bar.SerialPortRefreshButton
        self.BaudRateComboBox = self.top_bar.BaudRateComboBox
        self.RobotStateDisplay = self.top_bar.RobotStateDisplay
        self.ConnectButton = self.top_bar.ConnectButton
        self.PauseButton = self.top_bar.PauseButton
        self.EmergencyStopButton = self.top_bar.EmergencyStopButton
        self.SettingsButton = self.top_bar.SettingsButton

        # Joint table widgets
        joint_table = self.robot_state_panel.joint_table
        self.SpinBoxArt1 = joint_table.spinboxes["J1"]
        self.SpinBoxArt2 = joint_table.spinboxes["J2"]
        self.SpinBoxArt3 = joint_table.spinboxes["J3"]
        self.SpinBoxArt4 = joint_table.spinboxes["J4"]
        self.SpinBoxArt5 = joint_table.spinboxes["J5"]
        self.SpinBoxArt6 = joint_table.spinboxes["J6"]
        self.SpinBoxGripper = self.robot_state_panel.gripper_spinbox  # From separate gripper control

        # Actual position labels - wrap QTableWidgetItems in wrapper class for compatibility
        self.FKCurrentPosValueArt1 = TableItemLabelWrapper(joint_table.actual_items["J1"])
        self.FKCurrentPosValueArt2 = TableItemLabelWrapper(joint_table.actual_items["J2"])
        self.FKCurrentPosValueArt3 = TableItemLabelWrapper(joint_table.actual_items["J3"])
        self.FKCurrentPosValueArt4 = TableItemLabelWrapper(joint_table.actual_items["J4"])
        self.FKCurrentPosValueArt5 = TableItemLabelWrapper(joint_table.actual_items["J5"])
        self.FKCurrentPosValueArt6 = TableItemLabelWrapper(joint_table.actual_items["J6"])

        # Endstop labels - also wrap for compatibility
        self.endstopLabelArt1 = TableItemLabelWrapper(joint_table.endstop_items["J1"])
        self.endstopLabelArt2 = TableItemLabelWrapper(joint_table.endstop_items["J2"])
        self.endstopLabelArt3 = TableItemLabelWrapper(joint_table.endstop_items["J3"])
        self.endstopLabelArt4 = TableItemLabelWrapper(joint_table.endstop_items["J4"])
        self.endstopLabelArt5 = TableItemLabelWrapper(joint_table.endstop_items["J5"])
        self.endstopLabelArt6 = TableItemLabelWrapper(joint_table.endstop_items["J6"])

        # Inc/Dec buttons - connect them from table (J1-J6 only)
        for row in range(6):
            # Map table joint names to bifrost.py expected names
            joint_name_map = ["Art1", "Art2", "Art3", "Art4", "Art5", "Art6"]
            joint_name = joint_name_map[row]
            for col, delta in enumerate([-10, -1, 1, 10], start=4):
                btn = joint_table.cellWidget(row, col)
                # Store button references for compatibility
                if delta == -10:
                    setattr(self, f"FKDec10Button{joint_name}", btn)
                elif delta == -1:
                    setattr(self, f"FKDec1Button{joint_name}", btn)
                elif delta == 1:
                    setattr(self, f"FKInc1Button{joint_name}", btn)
                elif delta == 10:
                    setattr(self, f"FKInc10Button{joint_name}", btn)

        # Gripper buttons from separate control
        self.FKDec10ButtonGripper = self.robot_state_panel.gripper_dec10
        self.FKDec1ButtonGripper = self.robot_state_panel.gripper_dec1
        self.FKInc1ButtonGripper = self.robot_state_panel.gripper_inc1
        self.FKInc10ButtonGripper = self.robot_state_panel.gripper_inc10

        # Gripper preset buttons (Close/Open)
        self.gripper_close_btn = self.robot_state_panel.gripper_close_btn
        self.gripper_open_btn = self.robot_state_panel.gripper_open_btn

        # Create missing inc/dec buttons that bifrost.py expects (0.1 increments)
        # These are hidden in modern UI but need to exist for compatibility
        for joint in ['Art1', 'Art2', 'Art3', 'Art4', 'Art5', 'Art6']:
            # Create dummy buttons that are not visible
            dec_btn = QPushButton()
            dec_btn.setVisible(False)
            inc_btn = QPushButton()
            inc_btn.setVisible(False)
            setattr(self, f"FKDec0_1Button{joint}", dec_btn)
            setattr(self, f"FKInc0_1Button{joint}", inc_btn)

        # Individual Go buttons - create hidden dummy buttons
        for joint in ['Art1', 'Art2', 'Art3', 'Art4', 'Art5', 'Art6']:
            btn = QPushButton()
            btn.setVisible(False)
            setattr(self, f"FKGoButton{joint}", btn)

        self.GoButtonGripper = QPushButton()
        self.GoButtonGripper.setVisible(False)

        # Sliders - create hidden dummy sliders for compatibility (joints only)
        for joint in ['Art1', 'Art2', 'Art3', 'Art4', 'Art5', 'Art6']:
            slider = QtWidgets.QSlider()
            slider.setVisible(False)
            setattr(self, f"FKSlider{joint}", slider)

        # Gripper slider from separate control (real slider, visible)
        self.FKSliderGripper = self.robot_state_panel.gripper_slider
        self.SliderGripper = self.FKSliderGripper

        # 3D visualization canvas and controls
        self.position_canvas = self.robot_state_panel.robot_3d_canvas
        self.show_trajectory_check = self.robot_state_panel.show_trajectory_check
        self.auto_rotate_check = self.robot_state_panel.auto_rotate_check

        # Gripper buttons also need non-FK aliases for compatibility
        self.Dec10ButtonGripper = self.FKDec10ButtonGripper
        self.Dec1ButtonGripper = self.FKDec1ButtonGripper
        self.Inc1ButtonGripper = self.FKInc1ButtonGripper
        self.Inc10ButtonGripper = self.FKInc10ButtonGripper

        # JOG mode widgets
        self.G0MoveRadioButton = self.jog_panel.G0MoveRadioButton
        self.G1MoveRadioButton = self.jog_panel.G1MoveRadioButton
        self.FeedRateInput = self.jog_panel.FeedRateInput
        self.FeedRateLabel = self.jog_panel.FeedRateLabel
        self.JogModeCheckBox = self.jog_panel.JogModeCheckBox
        self.ExecuteMovementButton = self.jog_panel.ExecuteMovementButton
        self.HomeButton = self.jog_panel.HomeButton
        self.ZeroPositionButton = self.jog_panel.ZeroPositionButton
        self.KillAlarmLockButton = self.jog_panel.KillAlarmLockButton

        # Map FKGoAllButton to ExecuteMovementButton for compatibility
        self.FKGoAllButton = self.ExecuteMovementButton

        # INVERSE mode widgets
        self.IKInputSpinBoxX = self.inverse_panel.IKInputSpinBoxX
        self.IKInputSpinBoxY = self.inverse_panel.IKInputSpinBoxY
        self.IKInputSpinBoxZ = self.inverse_panel.IKInputSpinBoxZ
        self.IkIncButtonX = self.inverse_panel.IkIncButtonX
        self.IkDecButtonX = self.inverse_panel.IkDecButtonX
        self.IkIncButtonY = self.inverse_panel.IkIncButtonY
        self.IkDecButtonY = self.inverse_panel.IkDecButtonY
        self.IkIncButtonZ = self.inverse_panel.IkIncButtonZ
        self.IkDecButtonZ = self.inverse_panel.IkDecButtonZ
        self.IkOutputValueFrame = self.inverse_panel.IkOutputValueFrame
        self.IkOutputValueX = self.inverse_panel.IkOutputValueX
        self.IkOutputValueY = self.inverse_panel.IkOutputValueY
        self.IkOutputValueZ = self.inverse_panel.IkOutputValueZ

        # Create dummy IK labels/widgets that bifrost.py checks for enabled status
        self.InverseKinematicsLabel = QLabel()  # Dummy label
        self.IkOutputValueFrame_dummy = QFrame()  # Dummy frame (separate from the real one)

        # TEACH mode widgets
        self.sequencePointsList = self.teach_panel.sequencePointsList
        self.sequenceRecordButton = self.teach_panel.sequenceRecordButton
        self.sequenceAddManualButton = self.teach_panel.sequenceAddManualButton
        self.sequenceDeleteButton = self.teach_panel.sequenceDeleteButton
        self.sequenceClearButton = self.teach_panel.sequenceClearButton
        self.sequenceSaveButton = self.teach_panel.sequenceSaveButton
        self.sequenceLoadButton = self.teach_panel.sequenceLoadButton
        self.sequenceImportCsvButton = self.teach_panel.sequenceImportCsvButton

        # Add sequence playback widgets
        self.sequencePlayButton = self.teach_panel.sequencePlayButton
        self.sequencePauseButton = self.teach_panel.sequencePauseButton
        self.sequenceStopButton = self.teach_panel.sequenceStopButton
        self.sequenceSpeedSpinBox = self.teach_panel.sequenceSpeedSpinBox
        self.sequenceLoopCheckBox = self.teach_panel.sequenceLoopCheckBox
        self.sequenceDelaySpinBox = self.teach_panel.sequenceDelaySpinBox

        # TERMINAL mode widgets
        self.ConsoleInput = self.terminal_panel.ConsoleInput
        self.ConsoleButtonSend = self.terminal_panel.ConsoleButtonSend
        self.ConsoleOutput = self.terminal_panel.ConsoleOutput
        self.ConsoleShowVerbosecheckBox = self.terminal_panel.ConsoleShowVerbosecheckBox
        self.ConsoleShowOkRespcheckBox = self.terminal_panel.ConsoleShowOkRespcheckBox
        self.ConsoleClearButton = self.terminal_panel.ConsoleClearButton
        self.QuickM114Button = self.terminal_panel.QuickM114Button
        self.QuickM119Button = self.terminal_panel.QuickM119Button
        self.QuickG28Button = self.terminal_panel.QuickG28Button
