"""
Frame Teaching Module for Thor Robot Arm

Provides 3-point teaching method for defining workpiece frames:
1. Point 1 (Origin): Defines frame origin
2. Point 2 (X-axis): Defines positive X direction
3. Point 3 (XY-plane): Defines the XY plane (Z = X cross (P3-P1))

Uses Gram-Schmidt orthogonalization to ensure orthonormal frame.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, List

import numpy as np

from coordinate_frames import (
    CoordinateFrame,
    FrameType,
    FrameManager,
    transform_from_xyz_rpy
)

logger = logging.getLogger(__name__)


class TeachingState(Enum):
    """Current state of frame teaching process"""
    IDLE = "idle"
    WAITING_POINT_1 = "waiting_point_1"  # Origin
    WAITING_POINT_2 = "waiting_point_2"  # X-axis direction
    WAITING_POINT_3 = "waiting_point_3"  # XY-plane point
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class TeachingProgress:
    """Status of frame teaching process"""
    state: TeachingState
    frame_name: str
    points_recorded: int
    total_points: int = 3
    message: str = ""
    point_1: Optional[np.ndarray] = None
    point_2: Optional[np.ndarray] = None
    point_3: Optional[np.ndarray] = None

    @property
    def is_complete(self) -> bool:
        return self.state == TeachingState.COMPLETE

    @property
    def is_teaching(self) -> bool:
        return self.state in [
            TeachingState.WAITING_POINT_1,
            TeachingState.WAITING_POINT_2,
            TeachingState.WAITING_POINT_3
        ]

    @property
    def progress_percent(self) -> float:
        return (self.points_recorded / self.total_points) * 100


class FrameTeacher:
    """
    Handles 3-point frame teaching process.

    Teaching method (3-point):
    1. Move TCP to desired frame origin -> record Point 1
    2. Move TCP along desired X-axis direction -> record Point 2
    3. Move TCP to any point in desired XY plane -> record Point 3

    The frame is computed using Gram-Schmidt orthogonalization:
    - X-axis: normalized(P2 - P1)
    - Z-axis: normalized(X cross (P3 - P1))
    - Y-axis: Z cross X
    - Origin: P1
    """

    # Minimum distance between points to ensure valid frame (mm)
    MIN_POINT_DISTANCE = 5.0

    def __init__(self, frame_manager: FrameManager):
        """
        Initialize frame teacher.

        Args:
            frame_manager: FrameManager to add taught frames to
        """
        self.frame_manager = frame_manager
        self._reset()

    def _reset(self):
        """Reset teaching state"""
        self._state = TeachingState.IDLE
        self._frame_name = ""
        self._frame_description = ""
        self._point_1: Optional[np.ndarray] = None
        self._point_2: Optional[np.ndarray] = None
        self._point_3: Optional[np.ndarray] = None
        self._error_msg = ""

    @property
    def is_teaching(self) -> bool:
        """Check if currently in teaching mode"""
        return self._state in [
            TeachingState.WAITING_POINT_1,
            TeachingState.WAITING_POINT_2,
            TeachingState.WAITING_POINT_3
        ]

    @property
    def progress(self) -> TeachingProgress:
        """Get current teaching progress"""
        points_recorded = sum([
            self._point_1 is not None,
            self._point_2 is not None,
            self._point_3 is not None
        ])

        messages = {
            TeachingState.IDLE: "Not teaching",
            TeachingState.WAITING_POINT_1: "Move TCP to frame ORIGIN, then record point",
            TeachingState.WAITING_POINT_2: "Move TCP along +X direction, then record point",
            TeachingState.WAITING_POINT_3: "Move TCP to any point in XY plane, then record point",
            TeachingState.COMPLETE: "Frame teaching complete!",
            TeachingState.ERROR: self._error_msg
        }

        return TeachingProgress(
            state=self._state,
            frame_name=self._frame_name,
            points_recorded=points_recorded,
            message=messages.get(self._state, ""),
            point_1=self._point_1.copy() if self._point_1 is not None else None,
            point_2=self._point_2.copy() if self._point_2 is not None else None,
            point_3=self._point_3.copy() if self._point_3 is not None else None
        )

    def start_teaching(self, frame_name: str, description: str = "") -> TeachingProgress:
        """
        Begin 3-point teaching for a new workpiece frame.

        Args:
            frame_name: Name for the new frame
            description: Optional description

        Returns:
            TeachingProgress with current state
        """
        if not frame_name:
            self._state = TeachingState.ERROR
            self._error_msg = "Frame name cannot be empty"
            return self.progress

        if frame_name in ["world", "base", "tcp"]:
            self._state = TeachingState.ERROR
            self._error_msg = f"Cannot use reserved name: {frame_name}"
            return self.progress

        self._reset()
        self._frame_name = frame_name
        self._frame_description = description
        self._state = TeachingState.WAITING_POINT_1

        logger.info(f"Started frame teaching for: {frame_name}")
        return self.progress

    def record_point(self, tcp_position: np.ndarray) -> TeachingProgress:
        """
        Record current TCP position as the next teaching point.

        Args:
            tcp_position: Current TCP position (x, y, z) in base frame

        Returns:
            Updated TeachingProgress
        """
        tcp_position = np.asarray(tcp_position, dtype=np.float64)

        if tcp_position.shape != (3,):
            self._state = TeachingState.ERROR
            self._error_msg = f"Invalid position shape: {tcp_position.shape}"
            return self.progress

        if self._state == TeachingState.WAITING_POINT_1:
            self._point_1 = tcp_position.copy()
            self._state = TeachingState.WAITING_POINT_2
            logger.info(f"Point 1 (Origin) recorded: {tcp_position}")

        elif self._state == TeachingState.WAITING_POINT_2:
            # Validate distance from point 1
            dist = np.linalg.norm(tcp_position - self._point_1)
            if dist < self.MIN_POINT_DISTANCE:
                self._state = TeachingState.ERROR
                self._error_msg = f"Point 2 too close to Point 1 ({dist:.1f}mm < {self.MIN_POINT_DISTANCE}mm)"
                return self.progress

            self._point_2 = tcp_position.copy()
            self._state = TeachingState.WAITING_POINT_3
            logger.info(f"Point 2 (X-axis) recorded: {tcp_position}")

        elif self._state == TeachingState.WAITING_POINT_3:
            # Validate not collinear with points 1-2
            valid, error = self._validate_point_3(tcp_position)
            if not valid:
                self._state = TeachingState.ERROR
                self._error_msg = error
                return self.progress

            self._point_3 = tcp_position.copy()
            self._state = TeachingState.COMPLETE
            logger.info(f"Point 3 (XY-plane) recorded: {tcp_position}")

        else:
            logger.warning(f"record_point called in invalid state: {self._state}")

        return self.progress

    def _validate_point_3(self, point_3: np.ndarray) -> Tuple[bool, str]:
        """
        Validate that point 3 defines a valid XY plane (not collinear).

        Args:
            point_3: Candidate third point

        Returns:
            Tuple (is_valid, error_message)
        """
        if self._point_1 is None or self._point_2 is None:
            return False, "Points 1 and 2 must be recorded first"

        # Vector from P1 to P2 (X direction)
        v1 = self._point_2 - self._point_1
        # Vector from P1 to P3
        v2 = point_3 - self._point_1

        # Check distance from P1
        dist_from_origin = np.linalg.norm(v2)
        if dist_from_origin < self.MIN_POINT_DISTANCE:
            return False, f"Point 3 too close to origin ({dist_from_origin:.1f}mm)"

        # Check collinearity using cross product magnitude
        cross = np.cross(v1, v2)
        cross_mag = np.linalg.norm(cross)

        # Normalize by the product of vector lengths to get sin(angle)
        v1_mag = np.linalg.norm(v1)
        v2_mag = np.linalg.norm(v2)
        sin_angle = cross_mag / (v1_mag * v2_mag)

        # If sin(angle) is too small, points are nearly collinear
        if sin_angle < 0.1:  # Less than ~6 degrees
            return False, "Point 3 is nearly collinear with points 1-2 (move further from X-axis)"

        return True, ""

    def compute_frame(self) -> Optional[CoordinateFrame]:
        """
        Compute frame from 3 taught points using Gram-Schmidt orthogonalization.

        Returns:
            CoordinateFrame if teaching is complete, None otherwise
        """
        if self._state != TeachingState.COMPLETE:
            logger.warning("Cannot compute frame: teaching not complete")
            return None

        if self._point_1 is None or self._point_2 is None or self._point_3 is None:
            logger.error("Cannot compute frame: missing points")
            return None

        # Compute orthonormal frame using Gram-Schmidt
        # X-axis: normalized(P2 - P1)
        x_axis = self._point_2 - self._point_1
        x_axis = x_axis / np.linalg.norm(x_axis)

        # Temp Y: P3 - P1 (not orthogonal yet)
        temp_y = self._point_3 - self._point_1

        # Z-axis: X cross temp_Y (perpendicular to XY plane)
        z_axis = np.cross(x_axis, temp_y)
        z_axis = z_axis / np.linalg.norm(z_axis)

        # Y-axis: Z cross X (ensures right-handed orthonormal frame)
        y_axis = np.cross(z_axis, x_axis)
        y_axis = y_axis / np.linalg.norm(y_axis)

        # Build rotation matrix [X Y Z] as columns
        rotation = np.column_stack([x_axis, y_axis, z_axis])

        # Build 4x4 transform
        transform = np.eye(4)
        transform[:3, :3] = rotation
        transform[:3, 3] = self._point_1  # Origin at point 1

        # Create coordinate frame
        frame = CoordinateFrame(
            name=self._frame_name,
            frame_type=FrameType.WORKPIECE,
            transform=transform,
            parent_frame="base",
            description=self._frame_description
        )

        logger.info(f"Computed frame '{self._frame_name}':")
        logger.info(f"  Origin: {self._point_1}")
        logger.info(f"  X-axis: {x_axis}")
        logger.info(f"  Y-axis: {y_axis}")
        logger.info(f"  Z-axis: {z_axis}")

        return frame

    def finish_teaching(self) -> Optional[CoordinateFrame]:
        """
        Complete teaching and add frame to manager.

        Returns:
            Created CoordinateFrame if successful, None otherwise
        """
        frame = self.compute_frame()
        if frame is not None:
            self.frame_manager.add_frame(frame)
            logger.info(f"Added taught frame: {frame.name}")

        self._reset()
        return frame

    def cancel_teaching(self) -> None:
        """Cancel current teaching session"""
        if self.is_teaching:
            logger.info(f"Cancelled frame teaching for: {self._frame_name}")
        self._reset()

    def get_taught_points(self) -> List[Optional[np.ndarray]]:
        """
        Get list of taught points (for visualization).

        Returns:
            List [point_1, point_2, point_3] with None for unrecorded points
        """
        return [
            self._point_1.copy() if self._point_1 is not None else None,
            self._point_2.copy() if self._point_2 is not None else None,
            self._point_3.copy() if self._point_3 is not None else None
        ]


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.DEBUG)

    print("Frame Teaching Module Test")
    print("=" * 50)

    # Create manager and teacher
    fm = FrameManager()
    teacher = FrameTeacher(fm)

    # Start teaching
    print("\nStarting frame teaching for 'test_frame'...")
    progress = teacher.start_teaching("test_frame", "Test workpiece frame")
    print(f"  State: {progress.state.value}")
    print(f"  Message: {progress.message}")

    # Record point 1 (origin)
    print("\nRecording Point 1 (Origin) at (100, 50, 0)...")
    progress = teacher.record_point(np.array([100, 50, 0]))
    print(f"  State: {progress.state.value}")
    print(f"  Message: {progress.message}")

    # Record point 2 (X direction)
    print("\nRecording Point 2 (X-axis) at (200, 50, 0)...")
    progress = teacher.record_point(np.array([200, 50, 0]))
    print(f"  State: {progress.state.value}")
    print(f"  Message: {progress.message}")

    # Record point 3 (XY plane)
    print("\nRecording Point 3 (XY-plane) at (100, 150, 0)...")
    progress = teacher.record_point(np.array([100, 150, 0]))
    print(f"  State: {progress.state.value}")
    print(f"  Message: {progress.message}")

    # Finish teaching
    print("\nFinishing teaching...")
    frame = teacher.finish_teaching()
    if frame:
        print(f"  Created frame: {frame.name}")
        print(f"  Origin: {frame.position}")
        print(f"  Euler (deg): {frame.euler_degrees}")

    # Verify frame was added
    print(f"\nFrames in manager: {fm.list_frames()}")

    # Test error case: collinear points
    print("\n" + "=" * 50)
    print("Testing error case: collinear points")

    progress = teacher.start_teaching("bad_frame")
    teacher.record_point(np.array([0, 0, 0]))
    teacher.record_point(np.array([100, 0, 0]))
    progress = teacher.record_point(np.array([50, 0, 0]))  # Collinear!
    print(f"  State: {progress.state.value}")
    print(f"  Error: {progress.message}")

    print("\nAll tests completed!")
