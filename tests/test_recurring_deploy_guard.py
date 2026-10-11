"""Isolated production recurrence needs explicit activation and an exact cron."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from deployment_config_fixture import configured_runtime
from norulo_server.cloudflare_recurring_scheduler import PRODUCTION_RECURRING_CRON

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ("NORULO_D1_ACCESS_ENABLED", "NORULO_EMAIL_AUTH_ENABLED", "NORULO_JEV_SUGGESTIONS_ENABLED",
         "NORULO_JEV_SUGGESTIONS_EVALUATED", "NORULO_RECURRING_EXPENSES_ENABLED")
ACTIVATION = ("--environment", "production", "--activate-production", "--activate-email-auth",
              "--activate-ai-suggestions", "--activate-recurring-expenses")


def checker(tmp_path):
    spec = importlib.util.spec_from_file_location("recurring_config_checker", ROOT / "scripts/check-ledger-s01.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SERVER = tmp_path
    (tmp_path / "src").mkdir()
    (tmp_path / "src/entry.py").touch()
    return module


def test_only_exact_hourly_coordinated_preview_schedule_is_allowed(tmp_path):
    module = checker(tmp_path)
    original = configured_runtime("preview", recurring=True)
    path = tmp_path / "wrangler.preview.jsonc"
    path.write_text(json.dumps(original))
    module.validate_config("preview", False)
    for kind in ("high_frequency", "extra_cron", "daily", "disabled", "no_upgrade", "uncoordinated", "paused", "no_cron"):
        config = copy.deepcopy(original)
        if kind == "high_frequency":
            config["triggers"]["crons"] = ["* * * * *"]
        elif kind == "extra_cron":
            config["triggers"]["crons"].append("30 * * * *")
        elif kind == "daily":
            config["triggers"]["crons"] = [PRODUCTION_RECURRING_CRON]
        elif kind == "no_cron":
            config.pop("triggers")
        else:
            flag = {"disabled": "NORULO_RECURRING_EXPENSES_ENABLED", "no_upgrade": "NORULO_PREVIEW_SCHEMA_V7_UPGRADE_ENABLED",
                    "uncoordinated": "NORULO_PREVIEW_PRODUCT_ENABLED", "paused": "NORULO_D1_ACCESS_ENABLED"}[kind]
            config["vars"][flag] = "0"
        path.write_text(json.dumps(config))
        with pytest.raises(ValueError):
            module.validate_config("preview", False)


def test_production_remains_paused_and_has_no_background_activation(tmp_path):
    module = checker(tmp_path)
    original = configured_runtime("production")
    assert original["limits"] == {"cpu_ms": 300000, "subrequests": 9000}
    assert original["vars"]["NORULO_D1_ACCESS_ENABLED"] == "0"
    assert not original.get("triggers", {}).get("crons")
    assert original["vars"].get("NORULO_RECURRING_EXPENSES_ENABLED", "0") == "0"
    path = tmp_path / "wrangler.production.jsonc"
    path.write_text(json.dumps(original))
    module.validate_config("production", False)
    for key in ("flag", "cron", "both"):
        config = copy.deepcopy(original)
        if key in {"flag", "both"}:
            config["vars"]["NORULO_RECURRING_EXPENSES_ENABLED"] = "1"
        if key in {"cron", "both"}:
            config["triggers"] = {"crons": [PRODUCTION_RECURRING_CRON]}
        path.write_text(json.dumps(config))
        with pytest.raises(ValueError):
            module.validate_config("production", False)


def validate(module, config, *, activate=False):
    path = module.SERVER / "wrangler.production.jsonc"
    before = json.dumps(config, indent=2)
    path.write_text(before)
    try:
        assert module.validate_config("production", False, activate, activate, activate, activate) is None
    finally:
        assert path.read_text() == before


def active_production():
    config = configured_runtime("production")
    config["vars"].update({flag: "1" for flag in FLAGS})
    config["triggers"] = {"crons": [PRODUCTION_RECURRING_CRON]}
    return config


def test_production_recurrence_accepts_only_its_independent_scheduler_without_preview_upgrades(tmp_path):
    module = checker(tmp_path)
    config = active_production()
    assert config["durable_objects"]["bindings"] == module.PRODUCTION_BINDINGS
    assert config["migrations"] == module.PRODUCTION_MIGRATIONS
    assert config["vars"].get("NORULO_PREVIEW_SCHEMA_V7_UPGRADE_ENABLED", "0") == "0"
    validate(module, config)
    validate(module, configured_runtime("production"), activate=True)


def test_production_cron_is_daily_at_beijing_ten_minutes_past_midnight_and_preview_stays_hourly(tmp_path):
    module = checker(tmp_path)
    assert PRODUCTION_RECURRING_CRON == "10 16 * * *"
    assert module.PRODUCTION_CRONS == [PRODUCTION_RECURRING_CRON]
    assert module.PREVIEW_CRONS == ["0 * * * *"]
    minute, hour, *calendar = PRODUCTION_RECURRING_CRON.split()
    assert calendar == ["*", "*", "*"]
    beijing = datetime(2026, 10, 11, int(hour), int(minute), tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=8)))
    assert (beijing.day, beijing.hour, beijing.minute) == (12, 0, 10)


@pytest.mark.parametrize("limits", [None, {}, 300000,
    {"cpu_ms": 300000}, {"subrequests": 9000},
    {"cpu_ms": "300000", "subrequests": 9000}, {"cpu_ms": 300000.0, "subrequests": 9000},
    {"cpu_ms": True, "subrequests": 9000}, {"cpu_ms": 299999, "subrequests": 9000},
    {"cpu_ms": 300001, "subrequests": 9000},
    {"cpu_ms": 300000, "subrequests": "9000"}, {"cpu_ms": 300000, "subrequests": 9000.0},
    {"cpu_ms": 300000, "subrequests": True}, {"cpu_ms": 300000, "subrequests": 8999},
    {"cpu_ms": 300000, "subrequests": 9001}, {"cpu_ms": 300000, "subrequests": 10000000},
    {"cpu_ms": 300000, "subrequests": 9000, "extra": 1}])
@pytest.mark.parametrize("activate", [False, True])
def test_production_runtime_limits_cannot_be_missing_changed_or_broadened(tmp_path, limits, activate):
    module = checker(tmp_path)
    config = configured_runtime("production")
    config["limits"] = limits
    with pytest.raises(ValueError, match="exactly the reviewed 300000 ms CPU and 9000 subrequest limits"):
        validate(module, config, activate=activate)


def test_preview_validation_does_not_require_the_production_cpu_setting(tmp_path):
    module = checker(tmp_path)
    config = configured_runtime("preview", recurring=True)
    assert "limits" not in config
    (tmp_path / "wrangler.preview.jsonc").write_text(json.dumps(config))
    module.validate_config("preview", False)


@pytest.mark.parametrize("flag", FLAGS)
def test_production_cron_cannot_drop_any_accepted_runtime_feature(tmp_path, flag):
    module = checker(tmp_path)
    config = active_production()
    config["vars"][flag] = "0"
    with pytest.raises(ValueError):
        validate(module, config)


@pytest.mark.parametrize("value", [None, 0, 1, True, False, "", "true", [], {}])
@pytest.mark.parametrize("activate", [False, True])
def test_recurring_overlay_cannot_repair_a_polluted_raw_switch(tmp_path, value, activate):
    module = checker(tmp_path)
    config = configured_runtime("production")
    config["vars"][FLAGS[-1]] = value
    with pytest.raises(ValueError, match="explicit string 0 or 1"):
        validate(module, config, activate=activate)


@pytest.mark.parametrize("crons", [None, PRODUCTION_RECURRING_CRON, [None], ["* * * * *"],
    ["0 * * * *"], ["0 16 * * *"], ["10 0 * * *"], [PRODUCTION_RECURRING_CRON, "30 * * * *"]])
@pytest.mark.parametrize("activate", [False, True])
def test_recurring_overlay_cannot_mask_an_invalid_or_extra_cron(tmp_path, crons, activate):
    module = checker(tmp_path)
    config = active_production()
    config["triggers"]["crons"] = crons
    with pytest.raises(ValueError):
        validate(module, config, activate=activate)


@pytest.mark.parametrize("activate", [False, True])
@pytest.mark.parametrize("partial", ["cron_only", "flag_only"])
def test_recurring_overlay_cannot_hide_partial_source_activation(tmp_path, activate, partial):
    module = checker(tmp_path)
    config = configured_runtime("production")
    if partial == "cron_only":
        config["triggers"] = {"crons": [PRODUCTION_RECURRING_CRON]}
    else:
        config["vars"][FLAGS[-1]] = "1"
    with pytest.raises(ValueError, match="matching activation"):
        validate(module, config, activate=activate)


@pytest.mark.parametrize("case", ["partial_binding", "partial_migration", "missing_email", "foreign_worker",
    "namespace_id", "extra_binding", "duplicate_binding", "extra_class", "non_sqlite", "wrong_tag",
    "reversed_history", "deleted_classes", "renamed_classes", "transferred_classes"])
@pytest.mark.parametrize("activate", [False, True])
def test_independent_namespace_history_rejects_contamination_even_while_paused(tmp_path, case, activate):
    module = checker(tmp_path)
    config = configured_runtime("production")
    binding = config["durable_objects"]["bindings"][-1]
    migration = config["migrations"][-1]
    if case == "partial_binding":
        config["durable_objects"]["bindings"].pop()
    elif case == "partial_migration":
        config["migrations"].pop()
    elif case == "missing_email":
        config["durable_objects"]["bindings"].pop(0)
        config["migrations"].pop(0)
    elif case == "foreign_worker":
        binding["script_name"] = "norulo-server-preview"
    elif case == "namespace_id":
        binding["namespace_id"] = "synthetic-source-namespace"
    elif case == "extra_binding":
        config["durable_objects"]["bindings"].append({"name": "VALIDATION_BUDGET", "class_name": "ValidationBudget"})
    elif case == "duplicate_binding":
        config["durable_objects"]["bindings"].append(copy.deepcopy(binding))
    elif case == "extra_class":
        migration["new_sqlite_classes"].append("ValidationBudget")
    elif case == "non_sqlite":
        migration["new_classes"] = migration.pop("new_sqlite_classes")
    elif case == "wrong_tag":
        migration["tag"] = "norulo-email-admission-v1"
    elif case == "reversed_history":
        config["migrations"].reverse()
    else:
        migration[case] = ["EmailAdmission"]
    with pytest.raises(ValueError, match="independent SQLite admission namespace"):
        validate(module, config, activate=activate)


def test_legacy_email_namespace_cannot_enable_a_production_cron(tmp_path):
    module = checker(tmp_path)
    config = configured_runtime("production")
    config["durable_objects"]["bindings"] = config["durable_objects"]["bindings"][:1]
    config["migrations"] = config["migrations"][:1]
    validate(module, config)
    with pytest.raises(ValueError, match="independent scheduler"):
        validate(module, config, activate=True)


@pytest.mark.parametrize("index", [2, 3, 4])
def test_recurring_api_requires_every_explicit_preservation_overlay(tmp_path, index):
    module = checker(tmp_path)
    config = active_production()
    path = tmp_path / "wrangler.production.jsonc"
    path.write_text(json.dumps(config))
    arguments = ["production", False, True, True, True, True]
    arguments[index] = False
    with pytest.raises(ValueError):
        module.validate_config(*arguments)


@pytest.mark.parametrize("cli", [[shutil.which("bash") or "bash", "scripts/deploy-cloudflare.sh"],
                                 [sys.executable, "scripts/check-ledger-s01.py"]])
@pytest.mark.parametrize("args", [[], ["--environment", "production"],
    ["--environment", "production", "--activate-production"],
    ["--environment", "production", "--activate-production", "--activate-email-auth"],
    ["--environment", "preview", "--activate-production", "--activate-email-auth", "--activate-ai-suggestions"]])
def test_recurring_cli_cannot_disable_accepted_features_or_activate_preview(cli, args):
    result = subprocess.run([*cli, *args, "--activate-recurring-expenses"], cwd=ROOT,
        text=True, capture_output=True, check=False, env={**os.environ, "NORULO_PYTHON": sys.executable})
    assert result.returncode != 0
    assert "Dry run only" not in result.stdout
    assert "S01 static checks passed" not in result.stdout


def test_recurring_dry_run_validates_daily_overlay_and_removes_private_config_without_mutation():
    worker = ROOT / "cloudflare/server"
    before = (worker / "wrangler.production.jsonc").read_bytes()
    files = set(worker.glob(".norulo-recurring-deploy.*.jsonc"))
    result = subprocess.run([shutil.which("bash") or "bash", "scripts/deploy-cloudflare.sh", *ACTIVATION],
        cwd=ROOT, text=True, capture_output=True, check=False,
        env={**os.environ, "NORULO_PYTHON": sys.executable})
    assert result.returncode == 0, result.stderr
    assert PRODUCTION_RECURRING_CRON in result.stdout
    assert "daily UTC cron" in result.stdout
    assert "execution regenerates and validates it" in result.stdout
    assert all(f"{flag}:1" in result.stdout for flag in FLAGS)
    assert "d1 migrations apply" not in result.stdout
    assert (worker / "wrangler.production.jsonc").read_bytes() == before
    assert set(worker.glob(".norulo-recurring-deploy.*.jsonc")) == files


@pytest.fixture
def release_fixture(tmp_path):
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    worker = repo / "cloudflare/server"
    scripts.mkdir(parents=True)
    (worker / "src").mkdir(parents=True)
    (worker / "src/entry.py").touch()
    for filename in ("deploy-cloudflare.sh", "check-ledger-s01.py"):
        shutil.copyfile(ROOT / "scripts" / filename, scripts / filename)
    for environment in ("preview", "production"):
        shutil.copyfile(ROOT / f"cloudflare/server/wrangler.{environment}.jsonc",
                        worker / f"wrangler.{environment}.jsonc")
    (repo / "openapi").symlink_to(ROOT / "openapi", target_is_directory=True)
    (repo / "norulo_server").symlink_to(ROOT / "norulo_server", target_is_directory=True)
    (worker / "migrations").symlink_to(ROOT / "cloudflare/server/migrations", target_is_directory=True)
    (worker / "sync_server_modules.py").write_text("print('Fixture source sync')\n")
    cli = worker / "node_modules/wrangler/wrangler-dist/cli.js"
    cli.parent.mkdir(parents=True)
    cli.touch()
    capture = tmp_path / "builder.json"
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(f"#!{sys.executable}\n" + '''import json, os, signal, sys
from pathlib import Path
args = sys.argv[1:]
path = Path(args[args.index("--config") + 1])
Path(os.environ["BUILDER_CAPTURE"]).write_text(json.dumps({"args": args,
    "cwd": str(Path.cwd()), "path": str(path), "mode": path.stat().st_mode & 0o777,
    "config": json.loads(path.read_text())}))
requested_signal = os.environ.get("BUILDER_SIGNAL")
if requested_signal in ("HUP", "INT", "TERM"):
    os.kill(os.getppid(), getattr(signal, "SIG" + requested_signal))
sys.exit(int(os.environ.get("BUILDER_EXIT", "0")))
''')
    fake_uv.chmod(0o755)
    return repo, worker, capture, {
        **os.environ, "NORULO_PYTHON": sys.executable, "BUILDER_CAPTURE": str(capture),
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
    }


@pytest.mark.parametrize("builder_exit,terminate,expected", [
    ("0", "", 0), ("17", "", 17), ("0", "HUP", 129), ("0", "INT", 130), ("0", "TERM", 143)])
def test_actual_builder_receives_complete_validated_config_and_cleanup_on_every_outcome(
        release_fixture, builder_exit, terminate, expected):
    repo, worker, capture, environment = release_fixture
    canonical = worker / "wrangler.production.jsonc"
    before = canonical.read_bytes()
    result = subprocess.run([shutil.which("bash") or "bash", "scripts/deploy-cloudflare.sh", *ACTIVATION,
        "--execute", "--local-checks-passed"], cwd=repo, text=True, capture_output=True, check=False,
        env={**environment, "BUILDER_EXIT": builder_exit, "BUILDER_SIGNAL": terminate})
    assert result.returncode == expected, result.stderr
    built = json.loads(capture.read_text())
    path = Path(built["path"])
    assert path.parent == worker
    assert path.name.startswith(".norulo-recurring-deploy.")
    assert built["cwd"] == str(worker)
    assert built["mode"] == 0o600
    assert built["args"][:6] == ["run", "--frozen", "--python", "3.14.2", "pywrangler", "deploy"]
    assert all(f"{flag}:1" in built["args"] for flag in FLAGS)
    config = built["config"]
    assert all(config["vars"][flag] == "1" for flag in FLAGS)
    assert config["triggers"]["crons"] == [PRODUCTION_RECURRING_CRON]
    original = json.loads(before)
    for key in ("main", "$schema", "limits", "d1_databases", "durable_objects", "migrations", "secrets"):
        assert config[key] == original[key]
    assert len(config["secrets"]["required"]) == 4
    assert config["durable_objects"]["bindings"][0]["class_name"] == "EmailAdmission"
    assert config["migrations"][0]["tag"] == "norulo-email-admission-v1"
    assert not path.exists()
    assert not list(worker.glob(".norulo-recurring-deploy.*.jsonc"))
    assert canonical.read_bytes() == before


def test_checker_failure_removes_empty_config_before_sync_or_builder(release_fixture):
    repo, worker, capture, environment = release_fixture
    canonical = worker / "wrangler.production.jsonc"
    config = json.loads(canonical.read_text())
    config["vars"][FLAGS[-1]] = "bad-switch"
    canonical.write_text(json.dumps(config))
    before = canonical.read_bytes()
    result = subprocess.run([shutil.which("bash") or "bash", "scripts/deploy-cloudflare.sh", *ACTIVATION,
        "--execute", "--local-checks-passed"], cwd=repo, text=True, capture_output=True, check=False, env=environment)
    assert result.returncode != 0
    assert "explicit string 0 or 1" in result.stderr
    assert "Fixture source sync" not in result.stdout
    assert not capture.exists()
    assert not list(worker.glob(".norulo-recurring-deploy.*.jsonc"))
    assert canonical.read_bytes() == before


@pytest.mark.parametrize("case", ["canonical", "foreign_directory", "wrong_name", "missing", "symlink",
                                 "nonempty", "not_private", "hardlink", "directory"])
def test_generated_config_cannot_overwrite_an_untrusted_path(tmp_path, case):
    module = checker(tmp_path)
    config = configured_runtime("production")
    path = tmp_path / ".norulo-recurring-deploy.Abc123.jsonc"
    existing = tmp_path / "user-file.jsonc"
    existing.write_text("retain this user file")
    if case == "canonical":
        path = tmp_path / "wrangler.production.jsonc"
        path.write_text(json.dumps(config))
    elif case == "foreign_directory":
        path = tmp_path / "elsewhere" / path.name
        path.parent.mkdir()
        path.touch(mode=0o600)
    elif case == "wrong_name":
        path = existing
    elif case == "symlink":
        path.symlink_to(existing)
    elif case == "nonempty":
        path.write_text("do not overwrite")
        path.chmod(0o600)
    elif case == "not_private":
        path.touch(mode=0o644)
        path.chmod(0o644)
    elif case == "hardlink":
        existing.write_text("")
        existing.chmod(0o600)
        path.hardlink_to(existing)
    elif case == "directory":
        path.mkdir(mode=0o700)
    before = existing.read_bytes()
    before_target = path.read_bytes() if path.is_file() else None
    with pytest.raises((ValueError, OSError)):
        module.write_deploy_config(path, config)
    assert existing.read_bytes() == before
    if before_target is not None:
        assert path.read_bytes() == before_target


def test_checker_cli_only_writes_a_validated_full_recurring_overlay(release_fixture):
    repo, worker, _, environment = release_fixture
    path = worker / ".norulo-recurring-deploy.Abc123.jsonc"
    path.touch(mode=0o600)
    before = (worker / "wrangler.production.jsonc").read_bytes()
    result = subprocess.run([sys.executable, str(repo / "scripts/check-ledger-s01.py"), *ACTIVATION,
        "--write-deploy-config", str(path)], cwd=repo.parent, text=True, capture_output=True, check=False,
        env=environment)
    assert result.returncode == 0, result.stderr
    assert all(json.loads(path.read_text())["vars"][flag] == "1" for flag in FLAGS)
    assert (worker / "wrangler.production.jsonc").read_bytes() == before
    result = subprocess.run([sys.executable, str(repo / "scripts/check-ledger-s01.py"), *ACTIVATION,
        "--write-deploy-config", str(path)], cwd=repo, text=True, capture_output=True, check=False,
        env=environment)
    assert result.returncode != 0
    assert "private empty mktemp file" in result.stderr


@pytest.mark.parametrize("failure", ["activation", "config", "contract"])
def test_checker_keeps_temporary_file_empty_until_every_validation_passes(release_fixture, failure):
    repo, worker, _, environment = release_fixture
    path = worker / ".norulo-recurring-deploy.Abc123.jsonc"
    path.touch(mode=0o600)
    arguments = list(ACTIVATION)
    if failure == "activation":
        arguments.remove("--activate-ai-suggestions")
    elif failure == "config":
        canonical = worker / "wrangler.production.jsonc"
        config = json.loads(canonical.read_text())
        config["vars"]["NORULO_JEV_SUGGESTIONS_EVALUATED"] = "1"
        canonical.write_text(json.dumps(config))
    else:
        # Replace only this fixture's link; never edit the shared source contract.
        (repo / "openapi").unlink()
        (repo / "openapi").mkdir()
        (repo / "openapi/ledger-v1.yaml").write_text("openapi: 3.0.0\n")
    result = subprocess.run([sys.executable, str(repo / "scripts/check-ledger-s01.py"), *arguments,
        "--write-deploy-config", str(path)], cwd=repo, text=True, capture_output=True, check=False,
        env=environment)
    assert result.returncode != 0
    assert path.read_bytes() == b""
