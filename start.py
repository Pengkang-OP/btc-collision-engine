#!/usr/bin/env python3
"""Simple Python launcher for BTC Collision Engine"""
import os
import sys
import subprocess

def main():
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("=" * 65)
    print("  BTC Collision Engine")
    print("=" * 65)
    print()
    
    # Check if virtual environment exists
    venv_activate = os.path.join(script_dir, "venv", "Scripts", "activate.bat")
    venv_python = os.path.join(script_dir, "venv", "Scripts", "python.exe")
    
    if os.path.exists(venv_python):
        print("Using virtual environment...")
        python_exe = venv_python
    else:
        print("Using system Python...")
        python_exe = sys.executable
    
    print()
    print("Starting engine...")
    print()
    
    # Run the CLI
    try:
        subprocess.run([python_exe, "key_collision_cli.py"])
    except KeyboardInterrupt:
        print("\n\nEngine stopped by user.")
    except Exception as e:
        print(f"\nError: {e}")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
