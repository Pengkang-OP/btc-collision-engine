import time
import os
import sys

def decode_content(data):
    encodings = ['utf-8', 'gbk', 'gb2312', 'cp936']
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            if all(ord(c) < 0xFFFF for c in text):
                return text
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')

def monitor_log(log_file):
    print("\n" + "=" * 50)
    print("   BTC Engine - Log Monitor")
    print("=" * 50)
    print(f"\nMonitoring: {log_file}")
    print("Press Ctrl+C to exit\n")
    
    last_size = 0
    
    while True:
        try:
            if os.path.exists(log_file):
                try:
                    current_size = os.path.getsize(log_file)
                    
                    if current_size > last_size:
                        try:
                            with open(log_file, 'rb') as f:
                                if last_size > 0:
                                    f.seek(last_size)
                                new_content = f.read()
                                if new_content:
                                    text = decode_content(new_content)
                                    print(text, end='', flush=True)
                        except Exception:
                            pass
                        last_size = current_size
                except Exception:
                    pass
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n[INFO] Log monitor exiting...")
            break

if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        log_file = os.path.join(os.path.dirname(__file__), 'logs', 'wizard.log')
    
    monitor_log(log_file)