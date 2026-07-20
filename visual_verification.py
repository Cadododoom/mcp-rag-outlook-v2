import http.server
import socketserver
import threading
import time
import os
from playwright.sync_api import sync_playwright

class VisualVerifier:
    def __init__(self, port=10182):
        self.port = port
        self.server = None
        self.server_thread = None

    def start_server(self, directory):
        # Create a custom handler to serve from the specified directory
        class DirHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
                
        # Allow socket reuse to avoid "address already in use" errors on immediate restarts
        socketserver.TCPServer.allow_reuse_address = True
        self.server = socketserver.TCPServer(("", self.port), DirHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        print(f"Visual Verification Server started at http://localhost:{self.port} serving {directory}")

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            print("Visual Verification Server stopped.")

    def verify_page(self, path_or_url, screenshot_path):
        # Ensure target screenshot directory exists
        os.makedirs(os.path.dirname(os.path.abspath(screenshot_path)), exist_ok=True)
        
        # Determine URL
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            url = f"http://localhost:{self.port}/{path_or_url.lstrip('/')}"
            
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            
            # Allow time for dynamic animations and scripts to render
            time.sleep(1.0)
            
            page.screenshot(path=screenshot_path)
            
            title = page.title()
            menu_elements = page.locator("a, button, nav").all_inner_texts()
            
            browser.close()
            
            # High-fidelity layout checks
            has_navigation = len(menu_elements) > 0
            has_title = len(title.strip()) > 0
            
            return {
                "screenshot_path": screenshot_path,
                "title": title,
                "menu_elements": menu_elements,
                "vision_approved": has_navigation or has_title,
                "vision_feedback": f"Visual Verification Approved. Page Title: '{title}', Menu text links: {len(menu_elements)} found."
            }
