import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from config import HEALTH_PORT

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_health_server():
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    server.serve_forever()

def start_health_thread():
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()
    return thread
