from __future__ import annotations
import json, mimetypes, os, shutil, subprocess, sys, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from . import __version__

GUI_DIR = Path(__file__).resolve().parent / "gui"


def _json(handler: BaseHTTPRequestHandler, status: int, payload):
    body = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)

def _read_json(handler: BaseHTTPRequestHandler):
    n = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(n) if n else b"{}"
    return json.loads(raw.decode("utf-8") or "{}")

def _target(path: str | None, default: Path) -> Path:
    p = Path(path).expanduser() if path else default
    return p.resolve()

class Handler(BaseHTTPRequestHandler):
    server_version = f"CodeProofGUI/{__version__}"
    default_target = Path.cwd()

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[gui] {self.address_string()} - {fmt % args}\n")

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path in ("/", "/index.html"):
                return self._serve_file(GUI_DIR / "index.html")
            if parsed.path.startswith("/static/"):
                rel = parsed.path.removeprefix("/static/").replace("/", os.sep)
                return self._serve_file((GUI_DIR / rel).resolve())
            if parsed.path == "/api/info":
                return _json(self, 200, {"version": __version__, "default_target": str(self.default_target)})
            if parsed.path == "/api/doctor":
                tools = []
                for n in ["ruff", "mypy", "pytest", "bandit", "semgrep"]:
                    p = shutil.which(n)
                    tools.append({"name": n, "available": bool(p), "path": p})
                return _json(self, 200, {"tools": tools})
            if parsed.path == "/api/policy":
                from .config import load
                qs = parse_qs(parsed.query)
                root = _target((qs.get("path") or [None])[0], self.default_target)
                cfg = load(root)
                return _json(self, 200, cfg.model_dump(mode="json"))
            if parsed.path == "/api/inventory":
                from .config import load
                from .discovery import symbols
                qs = parse_qs(parsed.query)
                root = _target((qs.get("path") or [None])[0], self.default_target)
                cfg = load(root)
                data = [{"name": n, "file": str(p), "line": l} for n, p, l in symbols(root, cfg.source_paths)]
                return _json(self, 200, {"root": str(root), "count": len(data), "symbols": data})
            if parsed.path == "/api/history":
                qs = parse_qs(parsed.query)
                root = _target((qs.get("path") or [None])[0], self.default_target)
                reports_dir = root / ".codeproof" / "reports"
                items = []
                if reports_dir.exists():
                    for p in sorted(reports_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
                        try:
                            d = json.loads(p.read_text(encoding="utf-8"))
                            items.append({"file": p.name, "generated_at": d.get("generated_at"), "project": d.get("project"),
                                          "score": d.get("score"), "grade": d.get("grade"), "policy_passed": d.get("policy_passed")})
                        except Exception:
                            continue
                return _json(self, 200, {"root": str(root), "reports": items})
            if parsed.path == "/api/report":
                qs = parse_qs(parsed.query)
                root = _target((qs.get("path") or [None])[0], self.default_target)
                name = (qs.get("file") or [""])[0]
                p = (root / ".codeproof" / "reports" / name).resolve()
                if not name or p.parent != (root / ".codeproof" / "reports").resolve() or not p.exists():
                    return _json(self, 404, {"error": "report not found"})
                return _json(self, 200, json.loads(p.read_text(encoding="utf-8")))
            return _json(self, 404, {"error": "not found"})
        except Exception as e:
            return _json(self, 500, {"error": str(e)})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/scan":
                from .config import load
                from .core import scan as run_scan
                from .reporting import write as write_reports
                data = _read_json(self)
                root = _target(data.get("path"), self.default_target)
                if not root.exists():
                    return _json(self, 400, {"error": f"target does not exist: {root}"})
                cfg = load(root)
                report = run_scan(root, cfg, data.get("fail_under"))
                write_reports(report, root / ".codeproof" / "reports", "all")
                return _json(self, 200, report.model_dump(mode="json"))
            if parsed.path == "/api/open-reports":
                data = _read_json(self)
                root = _target(data.get("path"), self.default_target)
                out = root / ".codeproof" / "reports"
                out.mkdir(parents=True, exist_ok=True)
                if sys.platform.startswith("win"):
                    os.startfile(out)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(out)])
                else:
                    subprocess.Popen(["xdg-open", str(out)])
                return _json(self, 200, {"ok": True, "path": str(out)})
            return _json(self, 404, {"error": "not found"})
        except Exception as e:
            return _json(self, 500, {"error": str(e)})

    def _serve_file(self, path: Path):
        if GUI_DIR not in path.parents and path != GUI_DIR / "index.html":
            return _json(self, 403, {"error": "forbidden"})
        if not path.exists() or not path.is_file():
            return _json(self, 404, {"error": "not found"})
        body = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

def serve(host: str = "127.0.0.1", port: int = 8787, target: Path | None = None, open_browser: bool = True):
    Handler.default_target = (target or Path.cwd()).resolve()
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"CodeProof GUI running at {url}")
    print(f"Default target: {Handler.default_target}")
    if open_browser:
        try: webbrowser.open(url)
        except Exception: pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
