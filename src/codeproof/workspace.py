"""A repository-scoped local workspace with bounded, durable scan history."""

import json
import secrets
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .config import TOOL_INFO, CheckConfig, load
from .core import scan
from .models import ScanReport
from .reporting import html, markdown, sarif

PROFILES = {
    "quality": {
        "label": "Code quality",
        "description": "Lint, types, tests and security before you commit.",
        "tools": ["syntax", "ruff", "mypy", "pytest", "bandit"],
    },
    "quick": {
        "label": "Fast feedback",
        "description": "Static checks plus your required policy gates.",
        "tools": ["syntax", "ruff", "mypy"],
    },
    "security": {
        "label": "Security review",
        "description": "Security patterns and dependency vulnerabilities.",
        "tools": ["syntax", "bandit", "semgrep", "pip-audit"],
    },
    "policy": {
        "label": "Repository policy",
        "description": "Run every enabled check in your policy.",
        "tools": [],
    },
}


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal["quality", "quick", "security", "policy"] = "quality"
    fail_under: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    jobs: int = Field(default=1, ge=1, le=8)
    allow_execution: bool = False
    allow_network: bool = False


def selected_policy(root: Path, request: ScanRequest):
    cfg = load(root)
    if request.profile != "policy":
        selected = set(PROFILES[request.profile]["tools"]) | set(cfg.required_tools)
        for name in PROFILES[request.profile]["tools"]:
            if name not in cfg.checks:
                cfg.checks[name] = CheckConfig(weight=10)
        for name, check in cfg.checks.items():
            check.enabled = check.enabled and name in selected
    cfg.jobs = request.jobs
    if request.fail_under is not None:
        cfg.fail_under = request.fail_under
    return cfg


def capabilities(cfg, root: Path):
    enabled = [name for name, check in cfg.checks.items() if check.enabled]
    execution = bool(set(enabled) & {"pytest", "imports", "pip-audit", "mypy"})
    semgrep_config = (
        cfg.checks["semgrep"].config or "auto" if "semgrep" in cfg.checks else "auto"
    )
    network = "pip-audit" in enabled or (
        "semgrep" in enabled
        and (semgrep_config == "auto" or not (root / semgrep_config).exists())
    )
    return enabled, execution, network


class Workspace:
    def __init__(self, root: Path, retention: int = 50):
        if retention < 1:
            raise ValueError("retention must be at least 1")
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ValueError("Repository directory does not exist")
        self.retention = retention
        self.directory = self.root / ".codeproof" / "workspace"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / "history.sqlite3"
        self.lock = threading.Lock()
        self.active: str | None = None
        self.token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT NOT NULL, status TEXT NOT NULL, profile TEXT NOT NULL, report TEXT, error TEXT, score REAL, passed INTEGER, findings INTEGER)"
            )
            db.execute(
                "UPDATE runs SET status='interrupted', error='Workspace stopped before this scan completed' WHERE status='running'"
            )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def metadata(self):
        cfg = load(self.root)
        profiles = {}
        for key, info in PROFILES.items():
            selected = selected_policy(self.root, ScanRequest(profile=key))
            enabled, execution, network = capabilities(selected, self.root)
            profiles[key] = {
                **info,
                "tools": enabled,
                "execution": execution,
                "network": network,
            }
        return {
            "project": self.root.name,
            "target": str(self.root),
            "token": self.token,
            "policy": cfg.model_dump(mode="json"),
            "policy_yaml": yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False),
            "profiles": profiles,
            "tools": [
                {
                    "id": name,
                    "label": info[0],
                    "description": info[1],
                    "available": info[2] is None or bool(shutil.which(name)),
                    "install": f"pip install 'codeproof-ai[{info[2]}]'"
                    if info[2]
                    else "Included",
                }
                for name, info in TOOL_INFO.items()
            ],
        }

    def history(self):
        with self.connect() as db:
            rows = db.execute(
                f"SELECT id,created,status,profile,score,passed,findings,error FROM runs ORDER BY created DESC LIMIT {self.retention}"
            ).fetchall()
        summaries = []
        for id_, created, status, profile, score, passed, findings, error in rows:
            summaries.append(
                {
                    "id": id_,
                    "created": created,
                    "status": status,
                    "profile": profile,
                    "score": score,
                    "policy_passed": bool(passed) if passed is not None else None,
                    "findings": findings or 0,
                    "error": error,
                }
            )
        return summaries

    def report(self, id_: str):
        with self.connect() as db:
            row = db.execute("SELECT report FROM runs WHERE id=?", (id_,)).fetchone()
        if not row or row[0] is None:
            raise KeyError("Completed report not found")
        return ScanReport.model_validate_json(row[0])

    def start(self, request: ScanRequest):
        cfg = selected_policy(self.root, request)
        _, execution, network = capabilities(cfg, self.root)
        if execution and not request.allow_execution:
            raise ValueError(
                "This profile executes repository or package code. Enable execution to continue."
            )
        if network and not request.allow_network:
            raise ValueError(
                "This profile uses network services. Enable network access to continue."
            )
        with self.lock:
            if self.active:
                raise RuntimeError("A scan is already running. Wait for it to finish.")
            id_ = uuid4().hex
            with self.connect() as db:
                db.execute(
                    "INSERT INTO runs(id,created,status,profile) VALUES(?,?,?,?)",
                    (
                        id_,
                        datetime.now(timezone.utc).isoformat(),
                        "running",
                        request.profile,
                    ),
                )
                db.execute(
                    f"DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY created DESC LIMIT {self.retention})"
                )
            self.active = id_
            threading.Thread(target=self._execute, args=(id_, cfg), daemon=True).start()
        return id_

    def _execute(self, id_, cfg):
        try:
            report = scan(self.root, cfg)
            with self.connect() as db:
                db.execute(
                    "UPDATE runs SET status='complete',report=?,score=?,passed=?,findings=? WHERE id=?",
                    (
                        report.model_dump_json(),
                        report.score,
                        int(report.policy_passed),
                        sum(len(r.findings) for r in report.results),
                        id_,
                    ),
                )
        except Exception as exc:
            with self.connect() as db:
                db.execute(
                    "UPDATE runs SET status='error',error=? WHERE id=?", (str(exc), id_)
                )
        finally:
            with self.lock:
                self.active = None


def make_server(
    workspace: Workspace, host="127.0.0.1", port=8765, allowed_host: str | None = None
):
    assets = Path(__file__).with_name("web")
    allowed = {"localhost", "127.0.0.1", "::1"}
    if allowed_host:
        allowed.add(allowed_host.lower())

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *args):
            pass

        def respond(
            self, data, status=200, content_type="application/json", attachment=None
        ):
            body = (
                json.dumps(data).encode()
                if content_type == "application/json"
                else data.encode()
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            if attachment:
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{attachment}"'
                )
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            try:
                return (
                    urlsplit("http://" + self.headers.get("Host", "")).hostname
                    in allowed
                )
            except ValueError:
                return False

        def do_GET(self):
            if not self.valid_host():
                self.respond({"error": "Host is not allowed"}, 403)
                return
            path = urlsplit(self.path).path
            try:
                if path == "/api/workspace":
                    self.respond(workspace.metadata())
                elif path == "/api/runs":
                    self.respond(workspace.history())
                elif path.startswith("/api/runs/"):
                    parts = path.split("/")
                    if len(parts) not in (4, 5):
                        raise KeyError("Not found")
                    report = workspace.report(parts[3])
                    if len(parts) == 4:
                        self.respond(report.model_dump(mode="json"))
                    else:
                        exports = {
                            "json": (
                                report.model_dump_json(indent=2),
                                "application/json",
                            ),
                            "html": (html(report), "text/html"),
                            "markdown": (markdown(report), "text/markdown"),
                            "sarif": (
                                json.dumps(sarif(report), indent=2),
                                "application/sarif+json",
                            ),
                        }
                        if parts[4] not in exports:
                            raise KeyError("Unknown export")
                        content, kind = exports[parts[4]]
                        # Download documents rather than render tool output under the workspace origin.
                        self.respond(
                            content,
                            content_type=kind
                            if kind != "application/json"
                            else "application/octet-stream",
                            attachment=f"codeproof-{parts[3]}.{ {'markdown': 'md'}.get(parts[4], parts[4]) }",
                        )
                elif path in ("/", "/app.css", "/app.js"):
                    filename = {
                        "/": "index.html",
                        "/app.css": "app.css",
                        "/app.js": "app.js",
                    }[path]
                    kind = {
                        "/": "text/html",
                        "/app.css": "text/css",
                        "/app.js": "text/javascript",
                    }[path]
                    self.respond(
                        (assets / filename).read_text(encoding="utf-8"),
                        content_type=kind,
                    )
                else:
                    self.respond({"error": "Not found"}, 404)
            except KeyError:
                self.respond({"error": "Report not found"}, 404)
            except (ValueError, TypeError, OSError, yaml.YAMLError) as exc:
                self.respond({"error": str(exc)}, 400)

        def do_POST(self):
            if not self.valid_host() or not secrets.compare_digest(
                self.headers.get("X-CodeProof-Token", ""), workspace.token
            ):
                self.respond({"error": "Invalid workspace session"}, 403)
                return
            origin = self.headers.get("Origin")
            if origin and origin not in (
                "http://" + self.headers.get("Host", ""),
                "https://" + self.headers.get("Host", ""),
            ):
                self.respond({"error": "Origin is not allowed"}, 403)
                return
            if self.path != "/api/scan":
                self.respond({"error": "Not found"}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 65536:
                    raise ValueError("Request must contain 1–65536 bytes")
                request = ScanRequest.model_validate_json(self.rfile.read(length))
                self.respond({"id": workspace.start(request)}, 202)
            except RuntimeError as exc:
                self.respond({"error": str(exc)}, 409)
            except (ValueError, TypeError, OSError, yaml.YAMLError) as exc:
                self.respond({"error": str(exc)}, 400)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
