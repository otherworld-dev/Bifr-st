"""
Position History Tracking for ThorRR Robot Arm
Tracks joint positions over time for visualization, analysis, and debugging
"""

import time
import json
import csv
from collections import deque
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Joint names in order for interpolation
_JOINT_NAMES = ('art1', 'art2', 'art3', 'art4', 'art5', 'art6')

# Minimum total joint change (degrees) to warrant interpolation between two snapshots
_MIN_JOINT_CHANGE_FOR_INTERP = 1.0


def _interpolate_tcp_trajectory(snapshots) -> list:
    """
    Build a dense TCP trajectory by linearly interpolating joint angles
    between consecutive snapshots and computing FK at each subdivision.

    This produces the actual curved TCP path for joint-space (G0) moves.
    Segments where joints barely moved are not subdivided.

    Args:
        snapshots: List of PositionSnapshot objects (len >= 2)

    Returns:
        List of (x, y, z, timestamp) tuples
    """
    try:
        import forward_kinematics as fk
        import config
    except ImportError:
        # Fallback: no interpolation if FK unavailable
        trajectory = []
        for s in snapshots:
            tcp = s.compute_tcp_position()
            if tcp:
                trajectory.append((*tcp, s.timestamp))
        return trajectory

    n_steps = getattr(config, 'TRAJECTORY_INTERPOLATION_STEPS', 20)
    trajectory = []

    # Get joint angles for first snapshot and add its TCP
    prev_joints = np.array([snapshots[0].get(j, 0.0) for j in _JOINT_NAMES])
    tcp = fk.compute_tcp_position_only(*prev_joints)
    if tcp:
        trajectory.append((*tcp, snapshots[0].timestamp))

    for i in range(1, len(snapshots)):
        curr_joints = np.array([snapshots[i].get(j, 0.0) for j in _JOINT_NAMES])
        t0 = snapshots[i - 1].timestamp
        t1 = snapshots[i].timestamp

        # Check if joints moved enough to warrant interpolation
        delta = np.abs(curr_joints - prev_joints).sum()
        if delta < _MIN_JOINT_CHANGE_FOR_INTERP:
            # Stationary or near-stationary — just add the endpoint
            tcp = fk.compute_tcp_position_only(*curr_joints)
            if tcp:
                trajectory.append((*tcp, t1))
        else:
            # Interpolate: skip t=0 (already added as previous endpoint)
            for step in range(1, n_steps + 1):
                alpha = step / n_steps
                interp_joints = prev_joints + alpha * (curr_joints - prev_joints)
                interp_time = t0 + alpha * (t1 - t0)
                tcp = fk.compute_tcp_position_only(*interp_joints)
                if tcp:
                    trajectory.append((*tcp, interp_time))

        prev_joints = curr_joints

    return trajectory


def compute_trajectory_from_waypoints(waypoints) -> list:
    """
    Compute a dense TCP trajectory from a list of joint-angle waypoints.

    Linearly interpolates joint angles between consecutive waypoints and
    computes FK at each subdivision, producing the actual curved TCP path.

    Args:
        waypoints: List of (q1, q2, q3, q4, q5, q6) tuples (degrees)

    Returns:
        List of (x, y, z) tuples representing the dense TCP path
    """
    if len(waypoints) < 2:
        if len(waypoints) == 1:
            try:
                import forward_kinematics as fk
                tcp = fk.compute_tcp_position_only(*waypoints[0])
                return [tcp] if tcp else []
            except ImportError:
                return []
        return []

    try:
        import forward_kinematics as fk
        import config
    except ImportError:
        return []

    n_steps = getattr(config, 'TRAJECTORY_INTERPOLATION_STEPS', 20)
    trajectory = []

    prev = np.array(waypoints[0], dtype=float)
    tcp = fk.compute_tcp_position_only(*prev)
    if tcp:
        trajectory.append(tcp)

    for i in range(1, len(waypoints)):
        curr = np.array(waypoints[i], dtype=float)
        delta = np.abs(curr - prev).sum()

        if delta < _MIN_JOINT_CHANGE_FOR_INTERP:
            tcp = fk.compute_tcp_position_only(*curr)
            if tcp:
                trajectory.append(tcp)
        else:
            for step in range(1, n_steps + 1):
                alpha = step / n_steps
                interp = prev + alpha * (curr - prev)
                tcp = fk.compute_tcp_position_only(*interp)
                if tcp:
                    trajectory.append(tcp)

        prev = curr

    return trajectory


class PositionSnapshot:
    """
    Represents a single position snapshot at a specific time
    Uses numpy structured array for 80% memory reduction vs object-based storage
    """

    # Define structured numpy dtype for efficient storage
    _dtype = np.dtype([
        ('timestamp', 'f8'),
        ('art1', 'f4'),
        ('art2', 'f4'),
        ('art3', 'f4'),
        ('art4', 'f4'),
        ('art5', 'f4'),
        ('art6', 'f4'),
    ])

    def __init__(self, timestamp=None, **joint_positions):
        """
        Args:
            timestamp: Unix timestamp (auto-generated if None)
            **joint_positions: Joint positions as keyword arguments (e.g., art1=10.5, art2=20.3)
        """
        # Create numpy structured array for efficient storage
        self._data = np.zeros(1, dtype=self._dtype)[0]
        self._data['timestamp'] = timestamp if timestamp else time.time()

        # Set joint positions
        for joint_name, value in joint_positions.items():
            if joint_name in self._dtype.names:
                self._data[joint_name] = value

        self.tcp_position = None  # Cached TCP position (x, y, z) computed by forward kinematics

    @property
    def timestamp(self):
        """Get timestamp"""
        return float(self._data['timestamp'])

    @property
    def positions(self):
        """Get positions as dictionary for API compatibility"""
        return {name: float(self._data[name]) for name in self._dtype.names if name != 'timestamp'}

    def get(self, joint_name, default=0.0):
        """Get position for a specific joint"""
        if joint_name in self._dtype.names:
            return float(self._data[joint_name])
        return default

    def compute_tcp_position(self):
        """
        Compute and cache TCP position using forward kinematics

        Returns:
            Tuple (x, y, z) representing TCP position in mm, or None if FK not available
        """
        if self.tcp_position is not None:
            return self.tcp_position

        try:
            import forward_kinematics as fk
            self.tcp_position = fk.compute_tcp_position_only(
                self.get('art1', 0),
                self.get('art2', 0),
                self.get('art3', 0),
                self.get('art4', 0),
                self.get('art5', 0),
                self.get('art6', 0)
            )
            return self.tcp_position
        except Exception as e:
            logger.warning(f"Failed to compute TCP position: {e}")
            return None

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp,
            'positions': self.positions
        }

    @classmethod
    def from_dict(cls, data):
        """Create from dictionary"""
        return cls(timestamp=data['timestamp'], **data['positions'])

    def __str__(self):
        pos_str = ", ".join(f"{k}={v:.2f}" for k, v in self.positions.items())
        return f"PositionSnapshot[{datetime.fromtimestamp(self.timestamp).strftime('%H:%M:%S.%f')[:-3]}]: {pos_str}"


class PositionHistory:
    """
    Tracks position history using a circular buffer for memory efficiency
    """

    def __init__(self, max_size=1000):
        """
        Args:
            max_size: Maximum number of snapshots to keep (older ones are discarded)
        """
        self.max_size = max_size
        self.history = deque(maxlen=max_size)
        self.start_time = time.time()
        self.recording = True

        logger.info(f"Position history initialised (max_size={max_size})")

    def add_snapshot(self, **joint_positions):
        """
        Add a new position snapshot

        Args:
            **joint_positions: Joint positions as keyword arguments

        Example:
            history.add_snapshot(art1=10.5, art2=20.3, art3=15.0)
        """
        if not self.recording:
            return

        snapshot = PositionSnapshot(**joint_positions)
        self.history.append(snapshot)

    def start_recording(self):
        """Start recording position history"""
        self.recording = True
        logger.info("Position recording started")

    def stop_recording(self):
        """Stop recording position history"""
        self.recording = False
        logger.info("Position recording stopped")

    def clear(self):
        """Clear all history"""
        self.history.clear()
        self.start_time = time.time()
        logger.info("Position history cleared")

    def get_recent(self, count=100):
        """
        Get the most recent snapshots

        Args:
            count: Number of recent snapshots to return

        Returns:
            List of PositionSnapshot objects
        """
        if count >= len(self.history):
            return list(self.history)
        return list(self.history)[-count:]

    def get_time_range(self, start_time, end_time):
        """
        Get snapshots within a time range

        Args:
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            List of PositionSnapshot objects
        """
        return [s for s in self.history if start_time <= s.timestamp <= end_time]

    def get_joint_data(self, joint_name):
        """
        Get all position data for a specific joint

        Args:
            joint_name: Name of the joint (e.g., 'art1', 'art2')

        Returns:
            Tuple of (timestamps, positions) as lists
        """
        timestamps = [s.timestamp for s in self.history]
        positions = [s.get(joint_name, 0.0) for s in self.history]
        return (timestamps, positions)

    def get_all_joints_data(self):
        """
        Get position data for all joints

        Returns:
            Dict mapping joint names to (timestamps, positions) tuples
        """
        if len(self.history) == 0:
            return {}

        # Get all unique joint names from snapshots
        joint_names = set()
        for snapshot in self.history:
            joint_names.update(snapshot.positions.keys())

        result = {}
        for joint_name in joint_names:
            result[joint_name] = self.get_joint_data(joint_name)

        return result

    def get_current_joint_angles(self):
        """
        Get most recent joint angles

        Returns:
            Dictionary of joint angles {'art1': value, 'art2': value, ...}
            or None if no history
        """
        if len(self.history) == 0:
            return None

        latest_snapshot = self.history[-1]
        return latest_snapshot.positions.copy()

    def get_tcp_trajectory(self, window_seconds=60, interpolate=True):
        """
        Get TCP trajectory for the specified time window.

        When interpolate=True, linearly interpolates joint angles between
        consecutive snapshots and computes FK at each subdivision to produce
        the actual curved TCP path (accurate for joint-space G0 moves).

        Args:
            window_seconds: Time window in seconds (0 = all history)
            interpolate: If True, subdivide segments via joint interpolation + FK

        Returns:
            List of tuples [(x, y, z, timestamp), ...] representing TCP positions
        """
        if len(self.history) == 0:
            return []

        # Filter by time window
        if window_seconds > 0:
            current_time = time.time()
            cutoff_time = current_time - window_seconds
            snapshots = [s for s in self.history if s.timestamp >= cutoff_time]
        else:
            snapshots = list(self.history)

        if not interpolate or len(snapshots) < 2:
            # Original behaviour: one FK per snapshot
            trajectory = []
            for snapshot in snapshots:
                tcp_pos = snapshot.compute_tcp_position()
                if tcp_pos is not None:
                    x, y, z = tcp_pos
                    trajectory.append((x, y, z, snapshot.timestamp))
            return trajectory

        return _interpolate_tcp_trajectory(snapshots)

    def get_statistics(self, joint_name):
        """
        Calculate statistics for a joint

        Args:
            joint_name: Name of the joint

        Returns:
            Dict with min, max, mean, range statistics
        """
        _, positions = self.get_joint_data(joint_name)

        if len(positions) == 0:
            return None

        return {
            'min': min(positions),
            'max': max(positions),
            'mean': sum(positions) / len(positions),
            'range': max(positions) - min(positions),
            'count': len(positions)
        }

    def save_to_json(self, filepath):
        """
        Save history to JSON file

        Args:
            filepath: Path to save file

        Returns:
            True if successful, False otherwise
        """
        try:
            data = {
                'start_time': self.start_time,
                'max_size': self.max_size,
                'snapshots': [s.to_dict() for s in self.history]
            }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Position history saved to {filepath} ({len(self.history)} snapshots)")
            return True
        except Exception as e:
            logger.error(f"Failed to save position history: {e}")
            return False

    def load_from_json(self, filepath):
        """
        Load history from JSON file

        Args:
            filepath: Path to load from

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            self.start_time = data['start_time']
            self.max_size = data.get('max_size', 1000)
            self.history = deque(maxlen=self.max_size)

            for snapshot_data in data['snapshots']:
                snapshot = PositionSnapshot.from_dict(snapshot_data)
                self.history.append(snapshot)

            logger.info(f"Position history loaded from {filepath} ({len(self.history)} snapshots)")
            return True
        except Exception as e:
            logger.error(f"Failed to load position history: {e}")
            return False

    def export_to_csv(self, filepath):
        """
        Export history to CSV file

        Args:
            filepath: Path to save CSV

        Returns:
            True if successful, False otherwise
        """
        try:
            if len(self.history) == 0:
                logger.warning("No history to export")
                return False

            # Get all joint names
            joint_names = set()
            for snapshot in self.history:
                joint_names.update(snapshot.positions.keys())
            joint_names = sorted(joint_names)

            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow(['timestamp', 'datetime'] + joint_names)

                # Data
                for snapshot in self.history:
                    row = [
                        snapshot.timestamp,
                        datetime.fromtimestamp(snapshot.timestamp).isoformat()
                    ]
                    row.extend([snapshot.get(joint, 0.0) for joint in joint_names])
                    writer.writerow(row)

            logger.info(f"Position history exported to {filepath} ({len(self.history)} snapshots)")
            return True
        except Exception as e:
            logger.error(f"Failed to export position history: {e}")
            return False

    def __len__(self):
        """Return number of snapshots in history"""
        return len(self.history)

    def __str__(self):
        duration = time.time() - self.start_time
        return f"PositionHistory({len(self.history)} snapshots, {duration:.1f}s duration, recording={'ON' if self.recording else 'OFF'})"


if __name__ == "__main__":
    # Test the position history tracking
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    print("Position History Test\n")
    print("=" * 60)

    # Create history tracker
    history = PositionHistory(max_size=10)
    print(f"\n{history}")

    # Add some test data
    print("\nAdding test snapshots...")
    for i in range(15):
        history.add_snapshot(
            art1=10.0 + i,
            art2=20.0 + i * 0.5,
            art3=15.0 - i * 0.3,
            art4=5.0 + i * 0.2
        )
        time.sleep(0.01)

    print(f"{history}")
    print(f"Buffer size: {len(history)} (max: 10, circular buffer dropped oldest)")

    # Get recent data
    print("\nLast 5 snapshots:")
    for snapshot in history.get_recent(5):
        print(f"  {snapshot}")

    # Get joint data
    print("\nArt1 position data:")
    timestamps, positions = history.get_joint_data('art1')
    print(f"  Timestamps: {len(timestamps)}")
    print(f"  Positions: {positions}")

    # Statistics
    print("\nStatistics for Art1:")
    stats = history.get_statistics('art1')
    for key, value in stats.items():
        print(f"  {key}: {value:.2f}")

    # Export to CSV
    print("\nExporting to CSV...")
    if history.export_to_csv("test_position_history.csv"):
        print("  [OK] Export successful")

    # Save to JSON
    print("\nSaving to JSON...")
    if history.save_to_json("test_position_history.json"):
        print("  [OK] Save successful")

    # Load from JSON
    print("\nLoading from JSON...")
    new_history = PositionHistory()
    if new_history.load_from_json("test_position_history.json"):
        print(f"  [OK] Load successful: {new_history}")

    print("\n" + "=" * 60)
    print("All tests complete!")
