import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from codeproof.config import CheckConfig, Config
from codeproof.core import scan
from codeproof.models import CheckResult, Finding, Status
from codeproof.reporting import sarif, write
from codeproof.workspace import ScanRequest, Workspace, make_server, selected_policy


def wait_for(workspace):
    end = time.monotonic() + 5
    while workspace.active and time.monotonic() < end:
        time.sleep(0.01)
    assert not workspace.active


@pytest.fixture
def root(tmp_path):
    (tmp_path / ".codeproof.yml").write_text(
        "required_tools: []\nsource_paths: [src]\nchecks:\n  mypy: {enabled: false}\n  ruff: {enabled: false}\n  pytest: {enabled: false}\n"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("x = 1")
    return tmp_path


def test_policy_profiles_preserve_required_disabled_tools(tmp_path):
    (tmp_path / ".codeproof.yml").write_text("checks:\n  pytest: {enabled: false}")
    cfg = selected_policy(tmp_path, ScanRequest(profile="quick"))
    assert "pytest" in cfg.required_tools
    assert not cfg.checks["pytest"].enabled
    assert cfg.checks["syntax"].enabled
    assert cfg.checks["ruff"].weight == 15


def test_durable_run_and_restart(root):
    workspace = Workspace(root)
    id_ = workspace.start(ScanRequest(profile="quick"))
    wait_for(workspace)
    assert workspace.history()[0]["score"] == 100
    assert workspace.report(id_).policy_passed
    restored = Workspace(root)
    assert restored.report(id_).results[0].name == "syntax"
    with restored.connect() as db:
        db.execute(
            "INSERT INTO runs(id,created,status,profile) VALUES('interrupted','9999','running','quick')"
        )
    assert Workspace(root).history()[0]["status"] == "interrupted"


def test_single_scan_admission_and_errors(root, monkeypatch):
    started, release = threading.Event(), threading.Event()

    def slow(*args):
        started.set()
        release.wait(5)
        raise ValueError("scan failed")

    monkeypatch.setattr("codeproof.workspace.scan", slow)
    workspace = Workspace(root)
    workspace.start(ScanRequest(profile="quick"))
    assert started.wait(1)
    with pytest.raises(RuntimeError, match="already running"):
        workspace.start(ScanRequest(profile="quick"))
    release.set()
    wait_for(workspace)
    assert workspace.history()[0]["status"] == "error"
    assert workspace.history()[0]["error"] == "scan failed"


def test_history_retention(root):
    workspace = Workspace(root)
    with workspace.connect() as db:
        db.executemany(
            "INSERT INTO runs(id,created,status,profile) VALUES(?,?,?,?)",
            [(str(i), f"2000-{i:03}", "error", "quick") for i in range(60)],
        )
    workspace.start(ScanRequest(profile="quick"))
    wait_for(workspace)
    with workspace.connect() as db:
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 50
    assert len(workspace.history()) == 50


def test_execution_and_network_opt_ins(tmp_path):
    workspace = Workspace(tmp_path)
    with pytest.raises(ValueError, match="executes"):
        workspace.start(ScanRequest(profile="quality"))
    with pytest.raises(ValueError, match="network"):
        workspace.start(ScanRequest(profile="security", allow_execution=True))
    with pytest.raises(ValueError):
        ScanRequest.model_validate({"profile": "quick", "root": "/tmp"})
    # Remote Semgrep registry configurations also require network opt-in.
    (tmp_path / ".codeproof.yml").write_text("checks:\n  semgrep: {config: p/python}")
    assert workspace.metadata()["profiles"]["security"]["network"]


@pytest.fixture
def api_server(root):
    workspace = Workspace(root)
    server = make_server(workspace, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield workspace, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def call(base, path, payload=None, headers=None):
    request = Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers or {},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.read(), response.headers
    except HTTPError as response:
        return response.code, response.read(), response.headers


def test_http_host_token_origin_and_validation(api_server):
    workspace, base = api_server
    assert call(base, "/api/workspace", headers={"Host": "attacker.test"})[0] == 403
    assert call(base, "/api/scan", {"profile": "quick"})[0] == 403
    headers = {"X-CodeProof-Token": workspace.token, "Origin": "https://attacker.test"}
    assert call(base, "/api/scan", {"profile": "quick"}, headers)[0] == 403
    headers.pop("Origin")
    assert call(base, "/api/scan", {"jobs": 9}, headers)[0] == 400
    assert call(base, "/api/scan", {"root": "/etc"}, headers)[0] == 400
    assert call(base, "/../pyproject.toml")[0] == 404
    assert call(base, "/api/runs/missing")[0] == 404


def test_http_run_exports_and_assets(api_server):
    workspace, base = api_server
    status, data, _ = call(
        base, "/api/scan", {"profile": "quick"}, {"X-CodeProof-Token": workspace.token}
    )
    assert status == 202
    id_ = json.loads(data)["id"]
    wait_for(workspace)
    assert json.loads(call(base, f"/api/runs/{id_}")[1])["score"] == 100
    for format_ in ("json", "html", "markdown", "sarif"):
        status, data, headers = call(base, f"/api/runs/{id_}/{format_}")
        assert status == 200 and data
        assert "attachment" in headers["Content-Disposition"]
    for asset in ("/", "/app.js", "/app.css"):
        status, data, headers = call(base, asset)
        assert status == 200 and data
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["Cache-Control"] == "no-store"


def test_sarif_locations_rules_and_all_compatibility(tmp_path):
    report = scan(
        tmp_path,
        Config(required_tools=[], checks={"syntax": CheckConfig(enabled=False)}),
    )
    report.results = [
        CheckResult(
            name="ruff",
            status=Status.failed,
            findings=[
                Finding(
                    message="first",
                    rule="F401",
                    path=str(tmp_path / "src/a b.py"),
                    line=3,
                ),
                Finding(message="second", rule="F401", path="../secret.py"),
                Finding(message="third", path="/outside.py", line=-1),
            ],
        )
    ]
    data = sarif(report)
    assert data["version"] == "2.1.0"
    run = data["runs"][0]
    assert len(run["tool"]["driver"]["rules"]) == 2
    assert (
        run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        == "src/a%20b.py"
    )
    assert "locations" not in run["results"][1]
    assert "locations" not in run["results"][2]
    assert len(write(report, tmp_path / "reports", "all")) == 3
    assert len(write(report, tmp_path / "reports", "sarif")) == 1
