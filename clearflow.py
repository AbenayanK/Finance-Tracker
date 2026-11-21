"""Run ClearFlow in an operating-system webview with local ledger storage."""

import json
import os
import secrets
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4

from filelock import FileLock
from platformdirs import user_data_path

MAX_REQUEST = 64 * 1024 * 1024
HTML_PATH = Path(__file__).with_name("ClearFlow.html")


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_file(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


class Ledger:
    def __init__(self, directory):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / "ledger.json"
        self.previous = directory / "ledger.previous.json"
        self.theme = directory / "theme.txt"
        self.lock = FileLock(str(directory / "ledger.lock"), timeout=3)
        self.last_read = None

    def load(self):
        with self.lock:
            self.last_read = read_file(self.path)
            return self.text(self.last_read)

    @staticmethod
    def text(data):
        return data.decode("utf-8", errors="replace") if data is not None else None

    def save(self, next_text, recover):
        next_bytes = next_text.encode("utf-8")
        with self.lock:
            current = read_file(self.path)
            if current != self.last_read:
                raise RuntimeError("Ledger changed in another window")
            if current == next_bytes:
                return
            if current is not None:
                if recover:
                    archive = self.path.with_name(f"ledger.unreadable-{uuid4().hex}.json")
                    atomic_write(archive, current)
                else:
                    atomic_write(self.previous, current)
            atomic_write(self.path, next_bytes)
            self.last_read = next_bytes


def create_server(ledger):
    prefix = "/" + secrets.token_urlsafe(32)
    html = HTML_PATH.read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body=b"", content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'unsafe-inline'; img-src data:; connect-src 'self'; "
                "form-action 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def json_response(self, data):
            self.respond(200, json.dumps(data).encode())

        def local_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.local_host():
                self.respond(403)
                return
            try:
                if self.path == prefix + "/":
                    config = json.dumps({
                        "prefix": prefix,
                        "path": str(ledger.path),
                        "theme": Ledger.text(read_file(ledger.theme)),
                    }).replace("<", "\\u003c")
                    page = html.replace("<head>", f"<head><script>window.clearFlowDesktop={config};</script>", 1)
                    self.respond(200, page.encode(), "text/html; charset=utf-8")
                elif self.path == prefix + "/ledger":
                    self.json_response(ledger.load())
                elif self.path == prefix + "/previous":
                    self.json_response(Ledger.text(read_file(ledger.previous)))
                else:
                    self.respond(404)
            except OSError:
                self.respond(500)

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.local_host() or self.headers.get("Origin") != origin:
                self.respond(403)
                return
            if self.path not in {prefix + "/ledger", prefix + "/theme"}:
                self.respond(404)
                return
            if self.headers.get_content_type() != "application/json":
                self.respond(415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_REQUEST:
                    self.respond(413)
                    return
                data = json.loads(self.rfile.read(length))
                if self.path == prefix + "/theme":
                    if data not in ("dark", "light"):
                        raise ValueError("Invalid theme")
                    atomic_write(ledger.theme, data.encode())
                else:
                    if not isinstance(data, dict) or not isinstance(data.get("recover"), bool):
                        raise ValueError("Invalid request")
                    ledger_data = json.loads(data["next"])
                    if not isinstance(ledger_data.get("transactions"), list) or not isinstance(ledger_data.get("settings"), dict):
                        raise ValueError("Invalid ledger")
                    ledger.save(data["next"], data["recover"])
                self.json_response(True)
            except (ValueError, TypeError, KeyError, AttributeError):
                self.respond(400)
            except RuntimeError:
                self.respond(409)
            except OSError:
                self.respond(500)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}{prefix}/"
    return server, url


class ExportDialog:
    def export_file(self, suggested_name, content):
        import webview

        save_dialog = webview.FileDialog.SAVE if hasattr(webview, "FileDialog") else webview.SAVE_DIALOG
        path = self.window.create_file_dialog(save_dialog, save_filename=suggested_name)
        if not path:
            return False
        target = Path(path[0] if isinstance(path, (list, tuple)) else path)
        if target.resolve().is_relative_to(self.data_directory.resolve()):
            raise ValueError("Choose a location outside ClearFlow's data folder")
        atomic_write(target, content.encode("utf-8"))
        return True


def main():
    import webview

    directory = user_data_path("ClearFlow Finance", appauthor=False)
    server, url = create_server(Ledger(directory))
    Thread(target=server.serve_forever, daemon=True).start()
    api = ExportDialog()
    api.data_directory = directory
    api.window = webview.create_window(
        "ClearFlow Finance", url, js_api=api, width=1280, height=850, min_size=(720, 600)
    )
    try:
        webview.start(gui="gtk" if os.sys.platform.startswith("linux") else None)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
