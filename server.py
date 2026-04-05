"""
Family website static file server.
Handles one special route:
  GET /refresh  → runs Yi_HW_Dashboard/fetch_assignments.py, then redirects back
All other requests are served as static files.
"""

import socket
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).parent


class DualStackServer(HTTPServer):
    """Binds to both IPv4 and IPv6 so localhost works on Windows 11."""
    address_family = socket.AF_INET6
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/refresh":
            script = ROOT / "Yi_HW_Dashboard" / "fetch_assignments.py"
            subprocess.run(["python", str(script)], cwd=str(ROOT / "Yi_HW_Dashboard"))
            self.send_response(302)
            self.send_header("Location", "/Yi_HW_Dashboard/assignments.html")
            self.end_headers()
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass  # suppress per-request noise


if __name__ == "__main__":
    server = DualStackServer(("::", 3000), Handler)
    print("Family website running at http://localhost:3000")
    server.serve_forever()
