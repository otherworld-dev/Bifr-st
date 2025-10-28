# Tomorrow's Refactoring Session Plan

## 📅 Session Date: [Next Day]

---

## 🎯 **Current Status Summary**

### ✅ **Completed Today**
- ✅ Phase 1: Foundation & Type Hints (100% complete)
  - All modules have type hints
  - Configuration consolidated
  - Regex patterns centralized
  - Dead code removed

- ✅ Phase 2.1: RobotController Extraction (100% complete)
  - Created `robot_controller.py` (395 lines)
  - Fully integrated into `bifrost.py`
  - 450+ lines extracted from god class
  - All tests passing
  - 11 commits pushed to GitHub

### 📊 **Current Metrics**
- **bifrost.py**: 1752 lines (down from 1797)
- **Lines Extracted**: 450+
- **New Modules**: 3 (parsing_patterns.py, robot_controller.py, REFACTORING_PROGRESS.md)
- **Type Hints Added**: 100+
- **Overall Progress**: ~30% of full refactoring

---

## 🎯 **Tomorrow's Goals**

### **Primary Goal: Phase 2.2 - Extract SerialCommunicationManager**

**Time Estimate:** 1.5-2 hours

**Objective:** Extract all serial communication logic from bifrost.py into a dedicated, testable SerialCommunicationManager class.

---

## 📋 **Step-by-Step Plan for Tomorrow**

### **Phase 2.2: SerialCommunicationManager Extraction**

#### **Step 1: Test Current Changes (15 minutes)**
Before making new changes, verify everything works:

```bash
# 1. Pull latest changes (if working from different machine)
git pull origin main

# 2. Run the application
python bifrost.py

# 3. Test these features:
- Application starts without errors ✓
- Connect to robot ✓
- Move Art1-4 (simple joints) ✓
- Move Art5/Art6 (differential joints) ✓
- Position feedback updates ✓
- Disconnect works ✓
```

**If any issues:** Stop and debug before continuing.
**If all works:** Commit checkpoint: "Pre-Phase-2.2: All tests passing"

---

#### **Step 2: Analyze SerialManager & SerialThreadClass (15 minutes)**

**Read these sections in bifrost.py:**
- `class SerialManager` (lines ~42-132)
- `class SerialThreadClass` (lines ~1616-1755)
- Connection methods in `BifrostGUI`:
  - `connectSerial()` (line ~1144)
  - `disconnectSerial()` (line ~1257)
  - `_onConnectionSuccess()` (line ~1220)
  - `_onConnectionError()` (line ~1242)

**Take notes on:**
- What state does SerialManager track?
- What does SerialThreadClass do?
- How do they interact?
- What dependencies exist?

---

#### **Step 3: Create SerialCommunicationManager Module (45 minutes)**

**Create file:** `serial_communication_manager.py`

**Class Structure:**
```python
"""
Serial Communication Manager
Handles all serial port communication, threading, and command queuing
"""

from typing import Callable, Optional, List
import threading
import queue  # Use queue.Queue instead of manual list+lock
import serial
import time
import logging
from PyQt5.QtCore import QThread, pyqtSignal

class SerialCommunicationManager:
    """
    Manages serial port connection, command queue, and background thread

    Improvements over old SerialManager:
    - Uses queue.Queue instead of manual locking
    - Better error handling
    - Cleaner state management
    - Observable events (on_connected, on_disconnected, on_data)
    """

    def __init__(self, port: str = None, baudrate: int = 115200):
        # Serial port
        self.port = port
        self.baudrate = baudrate
        self.serial_port = None

        # Thread-safe command queue
        self.command_queue = queue.Queue()

        # State
        self.is_connected = False

        # Background thread
        self.worker_thread = None

        # Event callbacks
        self.on_data_received: Optional[Callable[[str], None]] = None
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    def connect(self, port: str, baudrate: int) -> bool:
        """Connect to serial port and start worker thread"""
        pass

    def disconnect(self) -> None:
        """Disconnect and stop worker thread"""
        pass

    def send_command(self, command: str, priority: bool = False) -> bool:
        """Add command to queue (or priority queue)"""
        pass

    def is_open(self) -> bool:
        """Check if serial port is open"""
        pass
```

**Key Improvements:**
1. Use `queue.Queue` (thread-safe by design)
2. Use `queue.PriorityQueue` for priority commands
3. Cleaner callback system
4. Better error recovery
5. No PyQt dependencies in core class

---

#### **Step 4: Migrate SerialThreadClass (30 minutes)**

**Create:** `SerialWorkerThread` inside `serial_communication_manager.py`

**Key Changes:**
```python
class SerialWorkerThread(QThread):
    """
    Background thread for serial communication
    Improvements: Cleaner structure, better error handling
    """
    data_received = pyqtSignal(str)

    def __init__(self, manager: SerialCommunicationManager):
        super().__init__()
        self.manager = manager
        self.running = True

    def run(self):
        """Main thread loop - cleaner than original"""
        while self.running:
            # Process command queue
            # Read incoming data
            # Handle blocking commands
            pass
```

---

#### **Step 5: Integrate into bifrost.py (20 minutes)**

**In BifrostGUI.__init__():**
```python
# OLD:
# s0 = SerialManager()
# self.SerialThreadClass = SerialThreadClass(gui_instance=self)

# NEW:
from serial_communication_manager import SerialCommunicationManager

self.serial_manager = SerialCommunicationManager()
self.serial_manager.on_data_received = self.handleSerialData
self.serial_manager.on_connected = self._onConnectionSuccess
self.serial_manager.on_error = self._onConnectionError
```

**Update connection methods:**
```python
def connectSerial(self):
    # Simplified - manager handles threading
    success = self.serial_manager.connect(port, baudrate)

def disconnectSerial(self):
    self.serial_manager.disconnect()
```

---

#### **Step 6: Test & Commit (10 minutes)**

**Test Checklist:**
- [ ] Application starts
- [ ] Can connect to robot
- [ ] Commands are sent correctly
- [ ] Position feedback received
- [ ] Can disconnect cleanly
- [ ] No thread leaks

**Git Commit:**
```bash
git add serial_communication_manager.py bifrost.py
git commit -m "Phase 2.2 COMPLETE: Extract SerialCommunicationManager

- Created serial_communication_manager.py (300+ lines)
- Migrated SerialManager class
- Migrated SerialThreadClass
- Uses queue.Queue for thread safety
- Cleaner callback system
- Better error handling
- Fully integrated and tested"
```

---

## 🎯 **If Time Permits: Phase 2.3**

### **Phase 2.3: Extract PositionFeedbackProcessor (Optional, 1 hour)**

**Create:** `position_feedback_processor.py`

**Responsibilities:**
- Parse M114 responses
- Parse M119 responses
- Validate positions
- Update robot controller
- Update position history
- Trigger GUI updates
- Handle logging

**This is the "glue" between serial data and robot state.**

---

## 📦 **Files to Work With Tomorrow**

### **Read Before Starting:**
1. `bifrost.py` - Lines 42-132 (SerialManager)
2. `bifrost.py` - Lines 1616-1755 (SerialThreadClass)
3. `bifrost.py` - Lines 1144-1255 (Connection methods)

### **Will Create:**
1. `serial_communication_manager.py` (new, ~300 lines)

### **Will Modify:**
1. `bifrost.py` (replace SerialManager/Thread usage)
2. `REFACTORING_PROGRESS.md` (update status)

---

## ⚠️ **Common Pitfalls to Avoid**

1. **Thread Safety**
   - ❌ Don't use manual locks if queue.Queue available
   - ✅ Use queue.Queue (thread-safe by design)

2. **PyQt Signals**
   - ❌ Don't emit signals from non-Qt threads
   - ✅ Use callback functions or proper signal/slot

3. **Serial Port Cleanup**
   - ❌ Don't forget to close port on disconnect
   - ✅ Always close port + stop thread + join thread

4. **Backward Compatibility**
   - ❌ Don't break existing code
   - ✅ Keep same interface or provide adapters

5. **Testing**
   - ❌ Don't commit without testing
   - ✅ Test each feature after integration

---

## 🎓 **Learning Opportunities**

Tomorrow's session will teach:
1. **Threading Best Practices** - Using queue.Queue properly
2. **Serial Communication** - Handling timeouts, buffering
3. **Event-Driven Architecture** - Callbacks vs signals
4. **State Management** - Connection states, error recovery

---

## 📈 **Success Criteria for Tomorrow**

### **Must Have:**
- ✅ SerialCommunicationManager class created
- ✅ SerialManager logic migrated
- ✅ SerialThreadClass migrated
- ✅ Integrated into bifrost.py
- ✅ Application connects and communicates
- ✅ All tests pass
- ✅ Committed and pushed to GitHub

### **Nice to Have:**
- ✅ PositionFeedbackProcessor extracted (Phase 2.3)
- ✅ Improved error messages
- ✅ Better timeout handling
- ✅ Unit tests for SerialCommunicationManager

---

## 🚀 **Quick Start for Tomorrow**

```bash
# 1. Navigate to project
cd "d:\OneDrive - Swansea University\Projects\Thor Robot\Bifrost"

# 2. Pull latest (if needed)
git pull origin main

# 3. Check current status
git log --oneline -5
git status

# 4. Open files in IDE
# - bifrost.py (read SerialManager, SerialThreadClass)
# - TOMORROW_PLAN.md (this file)
# - REFACTORING_PROGRESS.md (track progress)

# 5. Start with Step 1: Test current changes
python bifrost.py
```

---

## 📊 **Expected Progress After Tomorrow**

| Metric | Before | After Tomorrow |
|--------|--------|----------------|
| **bifrost.py lines** | 1752 | ~1450 (-300) |
| **Modules created** | 3 | 4 (+serial_communication_manager.py) |
| **Lines extracted** | 450 | 750 (+300) |
| **Phases complete** | 2 | 3 (Phase 2.2, maybe 2.3) |
| **Overall progress** | 30% | 40-45% |

---

## 💡 **Tips for Success**

1. **Start with testing** - Verify current code works
2. **Read before coding** - Understand existing code first
3. **Small commits** - Commit after each major step
4. **Test frequently** - Don't wait until the end
5. **Use REFACTORING_PROGRESS.md** - Track what you're doing
6. **Take breaks** - Better to be fresh than tired
7. **Ask for help** - Use me if you get stuck!

---

## 🎯 **Long-Term Vision**

After Phase 2.2 tomorrow, the architecture will look like:

```
bifrost.py (GUI only, ~400 lines target)
├── robot_controller.py ✅ (robot logic)
├── serial_communication_manager.py 🎯 (serial comms)
├── position_feedback_processor.py (data processing)
├── sequence_controller.py (sequence playback)
├── visualization_controller.py (3D display)
├── parsing_patterns.py ✅ (regex patterns)
└── config.py ✅ (configuration)
```

**Clean separation of concerns!** 🎉

---

## 📝 **Notes Section** (Fill in tomorrow)

### What Went Well:
-

### Challenges Faced:
-

### Lessons Learned:
-

### Time Spent:
-

### Next Session Priority:
-

---

## 🔗 **Useful References**

- **Python queue module**: https://docs.python.org/3/library/queue.html
- **PyQt5 QThread**: https://doc.qt.io/qtforpython/PySide2/QtCore/QThread.html
- **pyserial docs**: https://pyserial.readthedocs.io/
- **Git commit style**: https://www.conventionalcommits.org/

---

## ✅ **Pre-Session Checklist**

Before starting tomorrow:
- [ ] Read this entire document
- [ ] Pull latest changes from GitHub
- [ ] Test current code (run bifrost.py)
- [ ] Have IDE open with bifrost.py
- [ ] Have coffee/tea ready ☕
- [ ] Set timer for focused work (Pomodoro: 25 min work, 5 min break)
- [ ] Clear workspace of distractions

---

**Total Estimated Time:** 2-3 hours
**Recommended Breaks:** Every 25-30 minutes
**Goal:** Phase 2.2 complete, maybe start 2.3

**Good luck tomorrow! You've got this! 🚀**

---

*Last Updated: [Today's Date]*
*Status: Phase 2.1 Complete, Ready for Phase 2.2*
*Git Branch: main*
*Last Commit: "Update REFACTORING_PROGRESS.md - Phase 2.1 complete"*
