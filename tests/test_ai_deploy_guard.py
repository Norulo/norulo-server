"""Offline AI activation and secret/resource fences; never dispatch a provider."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from deployment_config_fixture import configured_runtime


ROOT = Path(__file__).resolve().parents[1]
ENABLED = "NORULO_JEV_SUGGESTIONS_ENABLED"
EVALUATED = "NORULO_JEV_SUGGESTIONS_EVALUATED"
SECRET = "TYPESAFE_API_KEY"
OVERLAYS = (
    "NORULO_D1_ACCESS_ENABLED:1", "NORULO_EMAIL_AUTH_ENABLED:1",
    ENABLED + ":1", EVALUATED + ":1",
)


@pytest.fixture
def checker(tmp_path):
    spec = importlib.util.spec_from_file_location("ai_config_checker", ROOT / "scripts/check-ledger-s01.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SERVER = tmp_path
    (tmp_path / "src").mkdir()
    (tmp_path / "src/entry.py").touch()
    return module


def validate(checker, config, environment="production", *, allow_placeholders=False,
             activate_production=False, activate_email_auth=False, activate_ai_suggestions=False):
    path = checker.SERVER / f"wrangler.{environment}.jsonc"
    before = json.dumps(config, indent=2)
    path.write_text(before)
    try:
        checker.validate_config(environment, allow_placeholders, activate_production,
                                activate_email_auth, activate_ai_suggestions)
    finally:
        assert path.read_text() == before


def enabled_production():
    config = configured_runtime("production")
    config["vars"].update({"NORULO_D1_ACCESS_ENABLED": "1", "NORULO_EMAIL_AUTH_ENABLED": "1",
                           ENABLED: "1", EVALUATED: "1"})
    return config


def test_checked_in_secret_retention_preserves_all_existing_names_and_paused_flags(checker):
    config = json.loads((ROOT / "cloudflare/server/wrangler.production.jsonc").read_text())
    assert config["secrets"]["required"] == [
        "NORULO_GITHUB_CLIENT_SECRET", "NORULO_GITHUB_TOKEN_KEY",
        "NORULO_EMAIL_CODE_SECRET", SECRET,
    ]
    assert all(config["vars"][flag] == "0" for flag in (
        "NORULO_D1_ACCESS_ENABLED", "NORULO_EMAIL_AUTH_ENABLED", ENABLED, EVALUATED))
    assert SECRET not in config["vars"]
    validate(checker, config)


@pytest.mark.parametrize("flag", [ENABLED, EVALUATED])
@pytest.mark.parametrize("value", [None, 0, 1, True, False, "", "true", [], {}])
@pytest.mark.parametrize("activate", [False, True])
def test_raw_ai_flags_reject_non_string_zero_or_one_even_with_activation(checker, flag, value, activate):
    config = configured_runtime("production")
    config["vars"][flag] = value
    with pytest.raises(ValueError, match="explicit string 0 or 1"):
        validate(checker, config, activate_production=activate, activate_email_auth=activate,
                 activate_ai_suggestions=activate)


@pytest.mark.parametrize("flag", [ENABLED, EVALUATED])
def test_ai_flags_cannot_be_missing(checker, flag):
    config = configured_runtime("production")
    config["vars"].pop(flag)
    with pytest.raises(ValueError, match="explicit string 0 or 1"):
        validate(checker, config, activate_production=True, activate_email_auth=True,
                 activate_ai_suggestions=True)


@pytest.mark.parametrize("values", [("0", "1"), ("1", "0")])
@pytest.mark.parametrize("activate", [False, True])
def test_activation_cannot_hide_mismatched_ai_controls(checker, values, activate):
    config = configured_runtime("production")
    config["vars"][ENABLED], config["vars"][EVALUATED] = values
    with pytest.raises(ValueError, match="must match"):
        validate(checker, config, activate_production=activate, activate_email_auth=activate,
                 activate_ai_suggestions=activate)


@pytest.mark.parametrize("value", ["", "synthetic-not-a-real-credential"])
@pytest.mark.parametrize("enabled", [False, True])
def test_typesafe_secret_cannot_be_plaintext_vars_even_when_disabled(checker, value, enabled):
    config = enabled_production() if enabled else configured_runtime("production")
    config["vars"][SECRET] = value
    with pytest.raises(ValueError, match="secrets must not appear"):
        validate(checker, config)


@pytest.mark.parametrize("required", [None, SECRET, {SECRET: True}, [], ["PREFIX_" + SECRET], [SECRET, 1]])
def test_enabled_production_requires_exact_worker_secret_list_member(checker, required):
    config = enabled_production()
    config["secrets"]["required"] = required
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY Worker secret"):
        validate(checker, config)


@pytest.mark.parametrize("value", [None, 0, True, "invalid", [], {}])
def test_ai_activation_cannot_repair_a_polluted_raw_d1_switch(checker, value):
    config = configured_runtime("production")
    config["vars"]["NORULO_D1_ACCESS_ENABLED"] = value
    with pytest.raises(ValueError, match="D1 access must be an explicit"):
        validate(checker, config, activate_production=True, activate_email_auth=True,
                 activate_ai_suggestions=True)


def test_enabled_production_requires_active_d1(checker):
    config = enabled_production()
    config["vars"]["NORULO_D1_ACCESS_ENABLED"] = "0"
    with pytest.raises(ValueError, match="enabled AI suggestions require D1 access"):
        validate(checker, config)


@pytest.mark.parametrize("email", [None, "0", 1, True])
def test_active_production_ai_cannot_pause_or_omit_email_authentication(checker, email):
    config = enabled_production()
    if email is None:
        config["vars"].pop("NORULO_EMAIL_AUTH_ENABLED")
    else:
        config["vars"]["NORULO_EMAIL_AUTH_ENABLED"] = email
    with pytest.raises(ValueError, match="production AI suggestions require enabled email authentication"):
        validate(checker, config)


@pytest.mark.parametrize("email", ["0", "1"])
def test_ai_activation_requires_email_overlay_regardless_of_source_email_flag(checker, email):
    config = configured_runtime("production")
    config["vars"]["NORULO_EMAIL_AUTH_ENABLED"] = email
    with pytest.raises(ValueError, match="production D1 and email authentication activation"):
        validate(checker, config, activate_production=True, activate_ai_suggestions=True)


@pytest.mark.parametrize("case", [
    "host", "app", "callback", "provider", "coordinator", "preview_flag", "source_database",
    "uppercase_source_database", "shared_database", "mixed_case_shared_database", "placeholder_database",
])
def test_ai_activation_preserves_production_hosts_and_independent_resources(checker, case):
    config = configured_runtime("production")
    if case == "host":
        config["routes"][0]["pattern"] = "preview-api.norulo.com"
    elif case == "app":
        config["vars"]["NORULO_APP_URL"] = config["vars"]["NORULO_ALLOWED_ORIGINS"] = "https://preview.norulo.com"
    elif case == "callback":
        config["vars"]["NORULO_GITHUB_CALLBACK_URL"] = "https://preview.norulo.com/api/auth/github/callback"
    elif case == "provider":
        config["vars"]["NORULO_CREEM_API_BASE_URL"] = "https://test-api.creem.io"
    elif case == "coordinator":
        config["durable_objects"]["bindings"] = [{"name": "VALIDATION_BUDGET", "class_name": "ValidationBudget"}]
    elif case == "preview_flag":
        config["vars"]["NORULO_PREVIEW_PRODUCT_ENABLED"] = "1"
    elif case in {"source_database", "uppercase_source_database"}:
        source_id = next(iter(checker.SOURCE_DATABASE_IDS))
        config["d1_databases"][0]["database_id"] = source_id.upper() if case.startswith("uppercase") else source_id
    elif case in {"shared_database", "mixed_case_shared_database"}:
        preview = configured_runtime("preview")
        shared_id = "abcdefab-1111-4111-8111-abcdefabcdef"
        preview["d1_databases"][0]["database_id"] = shared_id
        config["d1_databases"][0]["database_id"] = shared_id.upper() if case.startswith("mixed") else shared_id
        (checker.SERVER / "wrangler.preview.jsonc").write_text(json.dumps(preview))
    else:
        config["d1_databases"][0]["database_id"] = checker.PLACEHOLDER_ID
    with pytest.raises(ValueError):
        validate(checker, config, allow_placeholders=True, activate_production=True, activate_email_auth=True,
                 activate_ai_suggestions=True)


def test_existing_fourth_email_argument_and_new_fifth_ai_argument_are_independent(checker):
    config = configured_runtime("production")
    config["secrets"]["required"].remove(SECRET)
    path = checker.SERVER / "wrangler.production.jsonc"
    before = json.dumps(config)
    path.write_text(before)
    checker.validate_config("production", False, True, True)
    assert path.read_text() == before
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY Worker secret"):
        checker.validate_config("production", False, True, True, True)
    assert path.read_text() == before
    config["secrets"]["required"].append(SECRET)
    before = json.dumps(config)
    path.write_text(before)
    with pytest.raises(ValueError, match="production D1 and email authentication activation"):
        checker.validate_config("production", False, True, False, True)
    assert path.read_text() == before
    checker.validate_config("production", False, True, True, True)
    assert path.read_text() == before


def test_disabled_ai_preserves_offline_placeholder_dry_runs(checker):
    config = configured_runtime("production")
    config["d1_databases"][0]["database_id"] = checker.PLACEHOLDER_ID
    validate(checker, config, allow_placeholders=True, activate_production=True)


def test_existing_coordinated_preview_can_validate_ai_without_production_cli_activation(checker):
    config = configured_runtime("preview")
    config["vars"].update({ENABLED: "1", EVALUATED: "1"})
    validate(checker, config, "preview")
    for mutation in ("paused", "uncoordinated"):
        invalid = copy.deepcopy(config)
        invalid["vars"]["NORULO_D1_ACCESS_ENABLED" if mutation == "paused" else "NORULO_PREVIEW_PRODUCT_ENABLED"] = "0"
        with pytest.raises(ValueError):
            validate(checker, invalid, "preview")


@pytest.mark.parametrize("cli", [
    [shutil.which("bash") or "bash", "scripts/deploy-cloudflare.sh"],
    [sys.executable, "scripts/check-ledger-s01.py"],
])
@pytest.mark.parametrize("args", [
    [], ["--environment", "production"], ["--environment", "preview"],
    ["--environment", "preview", "--activate-production"], ["--activate-production"],
    ["--environment", "production", "--activate-production"],
    ["--environment", "production", "--activate-email-auth"],
])
def test_ai_cli_option_requires_explicit_production_d1_and_email_activation(cli, args):
    result = subprocess.run([*cli, *args, "--activate-ai-suggestions"], cwd=ROOT,
        text=True, capture_output=True, check=False,
        env={**os.environ, "NORULO_PYTHON": sys.executable})
    assert result.returncode != 0
    assert "Dry run only" not in result.stdout
    assert "S01 static checks passed" not in result.stdout
    if args == ["--environment", "production", "--activate-production"]:
        assert "--activate-email-auth" in result.stderr


@pytest.mark.parametrize("email,ai", [(False, False), (True, False), (True, True)])
def test_production_dry_run_proposes_only_requested_overlays_without_mutation(email, ai):
    path = ROOT / "cloudflare/server/wrangler.production.jsonc"
    before = path.read_bytes()
    args = [shutil.which("bash") or "bash", "scripts/deploy-cloudflare.sh", "--environment", "production", "--activate-production"]
    if email:
        args.append("--activate-email-auth")
    if ai:
        args.append("--activate-ai-suggestions")
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False,
        env={**os.environ, "NORULO_PYTHON": sys.executable})
    assert result.returncode == 0, result.stderr
    assert "Dry run only" in result.stdout
    assert f"--var {OVERLAYS[0]}" in result.stdout
    assert (f"--var {OVERLAYS[1]}" in result.stdout) is email
    assert (f"--var {OVERLAYS[2]}" in result.stdout) is ai
    assert (f"--var {OVERLAYS[3]}" in result.stdout) is ai
    assert "d1 migrations apply" not in result.stdout
    assert path.read_bytes() == before
