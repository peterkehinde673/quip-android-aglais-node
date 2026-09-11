"""
Lightweight, zero-dependency local dashboard web server for Android phone browsers.
Serves mobile-friendly dark-mode UI at localhost:8080.
"""

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from quip_android.config.models import AppConfig
from quip_android.miner.controller import MinerController
from quip_android.utils.logging import get_logger

logger = get_logger("dashboard")

_CONTROLLER: Optional[MinerController] = None


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP handler serving REST API and local dashboard frontend.
    """

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging in console
        pass

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            tmpl_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
            try:
                with open(tmpl_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as err:
                self.send_error(500, f"Failed to load dashboard template: {err}")

        elif path == "/api/status":
            if _CONTROLLER:
                status = _CONTROLLER.get_status()
                self._send_json(200, status)
            else:
                self._send_json(503, {"error": "Controller not initialized"})

        elif path == "/api/health":
            self._send_json(200, {"status": "ok"})

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            body = json.loads(post_data) if post_data.strip() else {}
        except Exception:
            body = {}

        if path == "/api/start":
            if not _CONTROLLER:
                self._send_json(503, {"success": False, "message": "Controller not initialized"})
                return

            mode = body.get("mode")
            workers = body.get("workers")
            success, message = _CONTROLLER.start(mode=mode, custom_workers=workers)
            self._send_json(200 if success else 400, {"success": success, "message": message})

        elif path == "/api/stop":
            if not _CONTROLLER:
                self._send_json(503, {"success": False, "message": "Controller not initialized"})
                return

            success = _CONTROLLER.stop(reason="Dashboard stop button")
            self._send_json(200, {"success": success, "message": "Miner stopped successfully"})

        elif path == "/api/mode":
            mode = body.get("mode", "eco")
            if _CONTROLLER:
                _CONTROLLER.active_mode = mode
                self._send_json(200, {"success": True, "mode": mode})
            else:
                self._send_json(503, {"error": "Controller not initialized"})

        else:
            self.send_error(404, "Unknown action")


def start_local_dashboard(config: AppConfig, host: str = "127.0.0.1", port: int = 8080):
    """
    Launch HTTP server binding to host:port.
    """
    global _CONTROLLER
    _CONTROLLER = MinerController(config)

    server_address = (host, port)
    try:
        httpd = HTTPServer(server_address, DashboardRequestHandler)
        logger.info("Quip Android Dashboard listening at http://%s:%d/", host, port)
        print(f"Quip Android Dashboard live at http://{host}:{port}/")
        print("Press Ctrl+C to terminate dashboard.")
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard shutdown requested.")
        if _CONTROLLER:
            _CONTROLLER.stop("Dashboard shutdown")
    except Exception as err:
        logger.error("Dashboard server error: %s", err)
