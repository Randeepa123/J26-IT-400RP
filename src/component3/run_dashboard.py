"""
run_dashboard.py - Starts the local web API server and opens the Live Dashboard in the browser.
Completely standalone: No Docker required!
"""
import sys
import time
import webbrowser
import threading
from pathlib import Path

# Add src/component3 to sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import paths
import uvicorn
from api_server import app, _engine
from build_dashboard_html import build_standalone_dashboard

def check_server(host, port):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def open_browser():
    time.sleep(1.2)
    url = f"http://{paths.API_HOST}:{paths.API_PORT}/"
    print(f"\n=======================================================")
    print(f"🚀 Kukule Ganga Hydro Optimizer - Live Dashboard")
    print(f"📍 Opening Dashboard at: {url}")
    print(f"📁 Self-contained file: {paths.RUN_COMPONENT3_DIR / 'dashboard.html'}")
    print(f"   (Press Ctrl+C to stop the dashboard server)")
    print(f"=======================================================\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Could not automatically open browser: {e}")

def main():
    # 1. Ensure standalone outputs/run_component3/dashboard.html is up-to-date
    build_standalone_dashboard()

    # 2. Check if server already running
    if check_server(paths.API_HOST, paths.API_PORT):
        print(f"API Server already active on port {paths.API_PORT}.")
        webbrowser.open(f"http://{paths.API_HOST}:{paths.API_PORT}/")
        return

    # 3. Preload models and inputs
    print("Preloading hydrological models & 15-day forecast inputs...")
    _engine()

    # 4. Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # 5. Start Uvicorn server
    uvicorn.run(app, host=paths.API_HOST, port=paths.API_PORT, log_level="warning")

if __name__ == "__main__":
    main()
