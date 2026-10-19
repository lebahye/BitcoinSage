"""Simple HTTP server for the BitcoinSage Research page on port 8000."""
import http.server
import socketserver
import os
import sys

PORT = 8000

# Serve files from the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class ResearchHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.path = "/research.html"
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass  # quiet logs

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", PORT), ResearchHandler) as httpd:
    print(f"Research Server running on port {PORT}", flush=True)
    sys.stdout.flush()
    httpd.serve_forever()
