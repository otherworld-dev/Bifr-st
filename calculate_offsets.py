"""
Calculate calibration offsets based on actual firmware readings
"""
import forward_kinematics as fk

print("="*70)
print("CALIBRATION OFFSET CALCULATION")
print("="*70)
print()

print("KNOWN FACTS:")
print("-"*70)
print("1. After homing (G28), robot is physically UPRIGHT")
print("   Firmware reports: Y=-90°, Z=-90°")
print()
print("2. From FK testing, these angles show UPRIGHT:")
print("   - Art2=0°, Art3=0°")
print("   - Art2=90°, Art3=-90°")
print("   - Art2=-90°, Art3=90°")
print()

print("TESTING CALIBRATION OPTIONS:")
print("-"*70)
print()

# Option 1: Convert firmware (-90, -90) to FK (0, 0)
print("Option 1: Convert firmware (-90, -90) to FK (0, 0)")
print("  Art2 offset = 0 - (-90) = +90°")
print("  Art3 offset = 0 - (-90) = +90°")
print()
print("  Test: When you move to G0 Y0 Z0 (bent position):")
print("    Firmware Y=0, Z=0")
print("    FK would receive: Art2 = 0+90 = 90°, Art3 = 0+90 = 90°")

# Test if Art2=90, Art3=90 shows bent
positions = fk.compute_all_joint_positions(0, 90, 90, 0, 0, 0)
tcp = positions[-1]
j2 = positions[2]
print(f"    TCP: ({tcp[0]:7.1f}, {tcp[1]:7.1f}, {tcp[2]:7.1f})")
print(f"    J2:  ({j2[0]:7.1f}, {j2[1]:7.1f}, {j2[2]:7.1f})")
x_offset = abs(tcp[0] - j2[0])
is_upright = (x_offset < 100 and (tcp[2] - j2[2]) > 200)
print(f"    Shows: {'UPRIGHT (WRONG!)' if is_upright else 'BENT (CORRECT!)'}")
print()

# Option 2: Convert firmware (-90, -90) to FK (90, -90)
print("Option 2: Convert firmware (-90, -90) to FK (90, -90)")
print("  Art2 offset = 90 - (-90) = +180°")
print("  Art3 offset = -90 - (-90) = 0°")
print()
print("  Test: When you move to G0 Y0 Z0 (bent position):")
print("    Firmware Y=0, Z=0")
print("    FK would receive: Art2 = 0+180 = 180°, Art3 = 0+0 = 0°")

positions = fk.compute_all_joint_positions(0, 180, 0, 0, 0, 0)
tcp = positions[-1]
j2 = positions[2]
print(f"    TCP: ({tcp[0]:7.1f}, {tcp[1]:7.1f}, {tcp[2]:7.1f})")
print(f"    J2:  ({j2[0]:7.1f}, {j2[1]:7.1f}, {j2[2]:7.1f})")
x_offset = abs(tcp[0] - j2[0])
is_upright = (x_offset < 100 and (tcp[2] - j2[2]) > 200)
print(f"    Shows: {'UPRIGHT (WRONG!)' if is_upright else 'BENT (CORRECT!)'}")
print()

# Option 3: Convert firmware (-90, -90) to FK (-90, 90)
print("Option 3: Convert firmware (-90, -90) to FK (-90, 90)")
print("  Art2 offset = -90 - (-90) = 0°")
print("  Art3 offset = 90 - (-90) = +180°")
print()
print("  Test: When you move to G0 Y0 Z0 (bent position):")
print("    Firmware Y=0, Z=0")
print("    FK would receive: Art2 = 0+0 = 0°, Art3 = 0+180 = 180°")

positions = fk.compute_all_joint_positions(0, 0, 180, 0, 0, 0)
tcp = positions[-1]
j2 = positions[2]
print(f"    TCP: ({tcp[0]:7.1f}, {tcp[1]:7.1f}, {tcp[2]:7.1f})")
print(f"    J2:  ({j2[0]:7.1f}, {j2[1]:7.1f}, {j2[2]:7.1f})")
x_offset = abs(tcp[0] - j2[0])
is_upright = (x_offset < 100 and (tcp[2] - j2[2]) > 200)
print(f"    Shows: {'UPRIGHT (WRONG!)' if is_upright else 'BENT (CORRECT!)'}")
print()

print("="*70)
print("RECOMMENDATION:")
print("="*70)
print("Use the option where bent position (Y=0, Z=0) shows bent in FK.")
print()
