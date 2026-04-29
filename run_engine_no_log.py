import subprocess
import sys
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    env = os.environ.copy()
    env['DISABLE_CONSOLE_LOG'] = '1'
    
    process = subprocess.Popen(
        [sys.executable, 'key_collision_cli.py', '--quick-start'],
        cwd=script_dir,
        env=env
    )
    
    process.wait()
    sys.exit(process.returncode)

if __name__ == "__main__":
    main()