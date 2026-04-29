import subprocess
import sys
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    log_file = os.path.join(log_dir, 'wizard.log')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    with open(log_file, 'wb') as f:
        f.write(b'')
    
    process = subprocess.Popen(
        [sys.executable, 'key_collision_cli.py', '--quick-start'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        cwd=script_dir
    )
    
    while True:
        chunk = process.stdout.read(4096)
        if not chunk:
            break
        
        sys.stdout.buffer.write(chunk)
        sys.stdout.flush()
        
        with open(log_file, 'ab') as f:
            f.write(chunk)

if __name__ == "__main__":
    main()