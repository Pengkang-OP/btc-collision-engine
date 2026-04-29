import subprocess
import sys
import os
import time

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    log_dir = os.path.join(script_dir, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'collision.log')
    if os.path.exists(log_file):
        os.remove(log_file)
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write('')
    
    python_exe = sys.executable
    
    if sys.platform == "win32":
        CREATE_NEW_CONSOLE = 0x00000010
    else:
        CREATE_NEW_CONSOLE = 0
    
    subprocess.Popen(
        [python_exe, 'log_monitor.py', log_file],
        creationflags=CREATE_NEW_CONSOLE,
        cwd=script_dir
    )
    
    time.sleep(1)
    
    subprocess.Popen(
        [python_exe, 'run_engine_no_log.py'],
        creationflags=CREATE_NEW_CONSOLE,
        cwd=script_dir
    )

if __name__ == "__main__":
    main()