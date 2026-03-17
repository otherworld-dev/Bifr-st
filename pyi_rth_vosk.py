"""PyInstaller runtime hook for vosk.

vosk.__init__.open_dll() needs libvosk.dll and its MinGW dependencies
in the vosk/ package directory. In onefile mode that directory doesn't
exist on disk. This hook finds the DLLs wherever PyInstaller put them
and makes them available to vosk.
"""
import os
import sys
import shutil

if getattr(sys, 'frozen', False):
    meipass = sys._MEIPASS
    vosk_dir = os.path.join(meipass, 'vosk')
    os.makedirs(vosk_dir, exist_ok=True)

    # DLLs that vosk needs — libvosk + its MinGW runtime dependencies
    needed = {'libvosk.dll', 'libgcc_s_seh-1.dll',
              'libstdc++-6.dll', 'libwinpthread-1.dll'}

    # Search ALL of _MEIPASS (recursively) for the needed DLLs
    found = {}
    for root, dirs, files in os.walk(meipass):
        for f in files:
            if f.lower() in {n.lower() for n in needed}:
                found[f] = os.path.join(root, f)

    # Copy found DLLs into vosk/ where open_dll() expects them
    for name in needed:
        dst = os.path.join(vosk_dir, name)
        if name in found and not os.path.exists(dst):
            shutil.copy2(found[name], dst)

    # Register as DLL search directories
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(meipass)
        os.add_dll_directory(vosk_dir)

    # Also add to PATH for legacy DLL resolution
    os.environ['PATH'] = vosk_dir + os.pathsep + meipass + os.pathsep + os.environ.get('PATH', '')
