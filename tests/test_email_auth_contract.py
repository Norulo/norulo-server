"""Offline email auth contract and enabled-provider configuration guards."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from norulo_server.cloudflare_github_identity_http import session_payload
from deployment_config_fixture import configured_runtime

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def checker():
    spec = importlib.util.spec_from_file_location("email_auth_checker", ROOT / "scripts/check-ledger-s01.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def preview():
    return configured_runtime("preview", email=True)


def validate_fixture(checker, monkeypatch, tmp_path, config, environment="preview"):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src/entry.py").touch()
    (tmp_path / f"wrangler.{environment}.jsonc").write_text(json.dumps(config))
    monkeypatch.setattr(checker, "SERVER", tmp_path)
    checker.validate_config(environment, allow_placeholders=False)


def test_enabled_email_configuration_has_a_fixed_sender_and_no_recipient_restriction(checker, preview, monkeypatch, tmp_path):
    assert preview["vars"]["NORULO_EMAIL_AUTH_ENABLED"] == "1"
    validate_fixture(checker, monkeypatch, tmp_path, preview)


@pytest.mark.parametrize("case", [
    "missing_sender", "other_sender", "binding_absent", "wrong_binding", "sender_absent",
    "sender_mismatch", "extra_sender", "destination", "allowed_destinations", "allowed_recipients",
    "duplicate_binding", "missing_coordinator", "paused_access",
])
def test_enabled_email_rejects_missing_or_broadened_provider_controls(checker, preview, monkeypatch, tmp_path, case):
    config = copy.deepcopy(preview)
    binding = config["send_email"][0]
    if case == "missing_sender":
        config["vars"].pop("NORULO_EMAIL_FROM")
    elif case == "other_sender":
        config["vars"]["NORULO_EMAIL_FROM"] = "other@auth.norulo.com"
    elif case == "binding_absent":
        config.pop("send_email")
    elif case == "wrong_binding":
        binding["name"] = "OTHER_EMAIL"
    elif case == "sender_absent":
        binding.pop("allowed_sender_addresses")
    elif case == "sender_mismatch":
        binding["allowed_sender_addresses"] = ["other@auth.norulo.com"]
    elif case == "extra_sender":
        binding["allowed_sender_addresses"].append("other@auth.norulo.com")
    elif case == "destination":
        binding["destination_address"] = "one-recipient@example.test"
    elif case == "allowed_destinations":
        binding["allowed_destination_addresses"] = ["one-recipient@example.test"]
    elif case == "allowed_recipients":
        binding["allowed_recipient_addresses"] = ["one-recipient@example.test"]
    elif case == "duplicate_binding":
        config["send_email"].append(copy.deepcopy(binding))
    elif case == "missing_coordinator":
        config["durable_objects"]["bindings"] = []
    else:
        config["vars"]["NORULO_D1_ACCESS_ENABLED"] = "0"
    with pytest.raises(ValueError):
        validate_fixture(checker, monkeypatch, tmp_path, config)


@pytest.mark.parametrize("flag", [None, 0, 1, "true", ""])
def test_email_enable_flag_accepts_only_string_zero_or_one(checker, preview, monkeypatch, tmp_path, flag):
    preview["vars"]["NORULO_EMAIL_AUTH_ENABLED"] = flag
    with pytest.raises(ValueError):
        validate_fixture(checker, monkeypatch, tmp_path, preview)


def test_legacy_configs_without_an_email_flag_remain_disabled(checker, preview, monkeypatch, tmp_path):
    preview["vars"].pop("NORULO_EMAIL_AUTH_ENABLED")
    preview["vars"].pop("NORULO_EMAIL_FROM")
    preview.pop("send_email")
    validate_fixture(checker, monkeypatch, tmp_path, preview)


def test_email_work_cannot_activate_production(checker, monkeypatch, tmp_path):
    config = configured_runtime("production")
    assert config["vars"]["NORULO_D1_ACCESS_ENABLED"] == "0"
    assert config["vars"]["NORULO_EMAIL_AUTH_ENABLED"] == "0"
    validate_fixture(checker, monkeypatch, tmp_path, config, "production")
    config["vars"].update(NORULO_EMAIL_AUTH_ENABLED="1", NORULO_EMAIL_FROM=checker.EMAIL_SENDER)
    config["send_email"] = [{"name": "EMAIL", "allowed_sender_addresses": [checker.EMAIL_SENDER]}]
    with pytest.raises(ValueError):
        validate_fixture(checker, monkeypatch, tmp_path, config, "production")


def enabled_production():
    config = configured_runtime("production", email=True)
    config["vars"]["NORULO_D1_ACCESS_ENABLED"] = "1"
    return config


def test_production_email_requires_its_independent_sqlite_admission(checker, monkeypatch, tmp_path):
    config = enabled_production()
    assert config["durable_objects"]["bindings"] == [
        {"name": "EMAIL_ADMISSION", "class_name": "EmailAdmission"},
        {"name": "RECURRING_SCHEDULER", "class_name": "RecurringScheduler"}]
    assert config["migrations"] == [
        {"tag": "norulo-email-admission-v1", "new_sqlite_classes": ["EmailAdmission"]},
        {"tag": "norulo-recurring-scheduler-v1", "new_sqlite_classes": ["RecurringScheduler"]}]
    validate_fixture(checker, monkeypatch, tmp_path, config, "production")


def test_legacy_email_only_production_namespace_remains_valid(checker, monkeypatch, tmp_path):
    config = enabled_production()
    config["durable_objects"]["bindings"] = config["durable_objects"]["bindings"][:1]
    config["migrations"] = config["migrations"][:1]
    validate_fixture(checker, monkeypatch, tmp_path, config, "production")


@pytest.mark.parametrize("case", [
    "no_namespace", "wrong_name", "preview_class", "foreign_worker", "duplicate_binding",
    "preview_coordinator", "no_migration", "preview_migration", "non_sqlite_class", "wrong_tag",
    "code_secret_missing", "preview_host", "preview_app", "preview_callback", "source_database",
    "paused_database", "missing_sender", "restricted_recipient", "extra_sender",
])
def test_production_email_rejects_missing_or_contaminated_controls(checker, monkeypatch, tmp_path, case):
    config = enabled_production()
    binding = config["durable_objects"]["bindings"][0]
    if case == "no_namespace":
        config.pop("durable_objects")
    elif case == "wrong_name":
        binding["name"] = "VALIDATION_BUDGET"
    elif case == "preview_class":
        binding["class_name"] = "ValidationBudget"
    elif case == "foreign_worker":
        binding["script_name"] = "norulo-server-preview"
    elif case == "duplicate_binding":
        config["durable_objects"]["bindings"].append(copy.deepcopy(binding))
    elif case == "preview_coordinator":
        config["durable_objects"]["bindings"].append({"name": "VALIDATION_BUDGET", "class_name": "ValidationBudget"})
    elif case == "no_migration":
        config.pop("migrations")
    elif case == "preview_migration":
        config["migrations"][0]["new_sqlite_classes"].append("ValidationBudget")
    elif case == "non_sqlite_class":
        config["migrations"][0]["new_classes"] = config["migrations"][0].pop("new_sqlite_classes")
    elif case == "wrong_tag":
        config["migrations"][0]["tag"] = "preview-v1"
    elif case == "code_secret_missing":
        config["secrets"]["required"].remove("NORULO_EMAIL_CODE_SECRET")
    elif case == "preview_host":
        config["routes"][0]["pattern"] = "preview-api.norulo.com"
    elif case == "preview_app":
        config["vars"]["NORULO_APP_URL"] = config["vars"]["NORULO_ALLOWED_ORIGINS"] = "https://preview.norulo.com"
    elif case == "preview_callback":
        config["vars"]["NORULO_GITHUB_CALLBACK_URL"] = "https://preview.norulo.com/api/auth/github/callback"
    elif case == "source_database":
        config["d1_databases"][0]["database_id"] = next(iter(checker.SOURCE_DATABASE_IDS))
    elif case == "paused_database":
        config["vars"]["NORULO_D1_ACCESS_ENABLED"] = "0"
    elif case == "missing_sender":
        config.pop("send_email")
    elif case == "restricted_recipient":
        config["send_email"][0]["allowed_destination_addresses"] = ["alice@example.test"]
    else:
        config["send_email"][0]["allowed_sender_addresses"].append("other@auth.norulo.com")
    with pytest.raises(ValueError):
        validate_fixture(checker, monkeypatch, tmp_path, config, "production")


def test_auth_operations_do_not_inherit_ledger_api_key_authority(checker):
    checker.validate_contract()
    contract = yaml.safe_load((ROOT / "openapi/ledger-v1.yaml").read_text())
    expected = {"/auth/session": "get", "/auth/sign-out": "post",
        "/auth/email/request-code": "post", "/auth/email/verify-code": "post",
        "/auth/github/authorize": "get", "/auth/github/callback": "get"}
    for path, method in expected.items():
        operation = contract["paths"][path][method]
        assert operation["security"] == [] and operation["x-norulo-scope"] == "account:auth"
    schemas = contract["components"]["schemas"]
    assert schemas["EmailCodeRequest"]["additionalProperties"] is False
    assert set(schemas["EmailCodeRequest"]["required"]) == {"email", "purpose"}
    assert schemas["EmailCodeRequest"]["properties"]["purpose"]["enum"] == ["login", "link"]
    assert set(schemas["EmailCodeVerification"]["required"]) == {"email", "challengeId", "code"}
    assert schemas["EmailCodeVerification"]["additionalProperties"] is False
    assert schemas["EmailCodeVerification"]["properties"]["code"]["pattern"] == "^[0-9]{6}$"
    assert set(schemas["EmailCodeChallenge"]["properties"]) == {"challengeId", "expiresIn", "retryAfter"}
    assert schemas["EmailCodeChallenge"]["properties"]["expiresIn"]["const"] == 600
    assert schemas["EmailCodeChallenge"]["properties"]["retryAfter"]["const"] == 60


def test_email_link_preflight_contract_keeps_public_login_non_enumeration():
    contract = yaml.safe_load((ROOT / "openapi/ledger-v1.yaml").read_text())
    request = contract["paths"]["/auth/email/request-code"]["post"]
    assert "does not disclose account existence" in request["description"]
    assert "checked only for authenticated linking" in request["description"]
    assert "rechecked at verification" in request["description"]
    conflict = request["responses"]["409"]["description"]
    assert "EMAIL_ALREADY_LINKED" in conflict and "EMAIL_CHANGE_NOT_SUPPORTED" in conflict
    assert "before code sending or cooldown" in conflict


def test_session_contract_matches_email_github_and_signed_out_dtos():
    contract = yaml.safe_load((ROOT / "openapi/ledger-v1.yaml").read_text())
    schemas = contract["components"]["schemas"]
    users = [None, {"id": "email-user", "name": "Alice", "email": "alice@example.test",
        "providers": ["email"], "emailVerifiedAt": 1},
        {"id": "github-user", "githubAccessToken": "sealed-fixture", "email": "unverified@example.test",
         "providers": ["github"]}]
    for user in users:
        payload = session_payload(user)
        assert set(payload) == set(schemas["AccountSession"]["required"])
        assert set(payload["github"]) == set(schemas["AccountSession"]["properties"]["github"]["required"])
        if user is None:
            assert payload["authenticated"] is False and payload["user"] is None
        else:
            assert set(payload["user"]) == set(schemas["SessionUser"]["required"])
            assert payload["user"]["emailVerified"] is ("email" in user["providers"])
            assert payload["user"]["email"] == (user["email"] if "email" in user["providers"] else None)
