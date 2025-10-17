#!/usr/bin/env python3
"""
Quick Schwab auth - keeps process alive for immediate URL input
"""

import subprocess
import sys
import time

def main():
    if len(sys.argv) < 2:
        # Step 1: Start the auth process and show URL
        print("Starting Schwab OAuth process...")
        proc = subprocess.Popen(
            ['python', 'schwab_manual_auth.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Read output until we see the auth URL
        auth_url = None
        for line in iter(proc.stdout.readline, ''):
            print(line, end='')
            if 'state=' in line and 'api.schwabapi.com' in line:
                auth_url = line.strip()
        
        if auth_url:
            print(f"\n✅ COPY THIS URL: {auth_url}")
            print("\nAfter authorization, run:")
            print(f"python quick_auth.py 'PASTE_REDIRECT_URL_HERE'")
        
        proc.terminate()
        return 0
    
    else:
        # Step 2: Feed the redirect URL to a fresh auth process
        redirect_url = sys.argv[1]
        print(f"Completing OAuth with: {redirect_url[:80]}...")
        
        proc = subprocess.Popen(
            ['python', 'schwab_manual_auth.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Wait a moment for the prompt
        time.sleep(2)
        
        # Send the redirect URL
        proc.stdin.write(redirect_url + '\n')
        proc.stdin.flush()
        proc.stdin.close()
        
        # Show output
        for line in proc.stdout:
            print(line, end='')
        
        return proc.wait()

if __name__ == "__main__":
    sys.exit(main())
