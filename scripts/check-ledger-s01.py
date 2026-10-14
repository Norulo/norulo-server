#!/usr/bin/env python3
"""Static S01 checks. Never opens D1 or invokes Wrangler."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "cloudflare" / "server"
sys.path.insert(0, str(ROOT))
from norulo_server.cloudflare_recurring_scheduler import PRODUCTION_RECURRING_CRON

PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"
# The imported service's databases are historical evidence, never Norulo targets.
SOURCE_DATABASE_IDS = frozenset({
    "e9dc3b89-f81f-4fce-87ef-d8797d879fb4",
    "80a29a0d-5699-449f-9541-a01dc461ca9d",
})
EMAIL_SENDER = "login@auth.norulo.com"
PREVIEW_CRONS = ["0 * * * *"]
PRODUCTION_CRONS = [PRODUCTION_RECURRING_CRON]
PRODUCTION_CPU_MS = 300_000
PRODUCTION_SUBREQUESTS = 9_000
AUTH_RATE_LIMITS = [{"name": "AUTH_RATE_LIMIT", "namespace_id": "1576996832",
                     "simple": {"limit": 20, "period": 60}}]
# Per IPv4/IPv6-/64 network and per presented credential; 10-second burst and
# 60-second sustained windows. Namespaces are independent of AUTH_RATE_LIMIT.
API_RATE_LIMITS = [
    {"name": "API_IP_BURST_RATE_LIMIT", "namespace_id": "1744429548",
     "simple": {"limit": 300, "period": 10}},
    {"name": "API_IP_RATE_LIMIT", "namespace_id": "1820219268",
     "simple": {"limit": 1200, "period": 60}},
    {"name": "API_CREDENTIAL_BURST_RATE_LIMIT", "namespace_id": "1012765925",
     "simple": {"limit": 120, "period": 10}},
    {"name": "API_CREDENTIAL_RATE_LIMIT", "namespace_id": "1009527699",
     "simple": {"limit": 600, "period": 60}},
]
PRODUCTION_RATE_LIMITS = AUTH_RATE_LIMITS + API_RATE_LIMITS
EMAIL_BINDINGS = [{"name": "EMAIL_ADMISSION", "class_name": "EmailAdmission"}]
EMAIL_MIGRATIONS = [{"tag": "norulo-email-admission-v1", "new_sqlite_classes": ["EmailAdmission"]}]
PRODUCTION_BINDINGS = EMAIL_BINDINGS + [{"name": "RECURRING_SCHEDULER", "class_name": "RecurringScheduler"}]
PRODUCTION_MIGRATIONS = EMAIL_MIGRATIONS + [
    {"tag": "norulo-recurring-scheduler-v1", "new_sqlite_classes": ["RecurringScheduler"]}]


def _validated_config(environment: str, allow_placeholders: bool,
                    activate_production: bool = False,
                    activate_email_auth: bool = False,
                    activate_ai_suggestions: bool = False,
                    activate_recurring_expenses: bool = False) -> dict:
    if activate_email_auth and (environment != "production" or not activate_production):
        raise ValueError("email authentication activation requires production D1 activation")
    if activate_ai_suggestions and (environment != "production" or not activate_production
                                   or not activate_email_auth):
        raise ValueError("AI suggestions activation requires production D1 and email authentication activation")
    if activate_recurring_expenses and (environment != "production" or not activate_production
                                       or not activate_email_auth or not activate_ai_suggestions):
        raise ValueError("recurring expenses activation requires production D1, email authentication and AI activation")
    config_path = SERVER / f"wrangler.{environment}.jsonc"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("name") != f"norulo-server-{environment}":
        raise ValueError("Worker name does not match environment")
    if config.get("main") != "src/entry.py" or not (SERVER / "src" / "entry.py").is_file():
        raise ValueError("Server Worker entry is missing")
    if config.get("workers_dev") is not False or config.get("preview_urls") is not False:
        raise ValueError("unreviewed public Worker URL")
    if environment == "production":
        if config.get("ratelimits") != PRODUCTION_RATE_LIMITS:
            raise ValueError("production requires the isolated GitHub authorization and API rate limits")
        limits = config.get("limits")
        if (not isinstance(limits, dict) or set(limits) != {"cpu_ms", "subrequests"}
                or type(limits.get("cpu_ms")) is not int or limits["cpu_ms"] != PRODUCTION_CPU_MS
                or type(limits.get("subrequests")) is not int or limits["subrequests"] != PRODUCTION_SUBREQUESTS):
            raise ValueError("production requires exactly the reviewed 300000 ms CPU and 9000 subrequest limits")
    routes = config.get("routes", [])
    if len(routes) != 1:
        raise ValueError("one reviewed hostname is required")
    route = routes[0]
    pattern = route.get("pattern", "")
    host = pattern if route.get("custom_domain") is True else pattern.removesuffix("/*")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise ValueError("route must target one exact hostname")
    if route.get("custom_domain") is not True:
        zone = route.get("zone_name", "")
        if not pattern.endswith("/*") or not zone or not (host == zone or host.endswith("." + zone)):
            raise ValueError("reviewed zone route is required")
    vars_ = config.get("vars", {})
    ai_enabled = vars_.get("NORULO_JEV_SUGGESTIONS_ENABLED")
    ai_evaluated = vars_.get("NORULO_JEV_SUGGESTIONS_EVALUATED")
    if any(not isinstance(flag, str) or flag not in ("0", "1")
           for flag in (ai_enabled, ai_evaluated)):
        raise ValueError("AI suggestions flags must be explicit string 0 or 1")
    if ai_enabled != ai_evaluated:
        raise ValueError("AI suggestions enablement and evaluation flags must match")
    if (not isinstance(vars_.get("NORULO_D1_ACCESS_ENABLED"), str)
            or vars_["NORULO_D1_ACCESS_ENABLED"] not in ("0", "1")):
        raise ValueError("D1 access must be an explicit 0 or 1")
    recurring = vars_.get("NORULO_RECURRING_EXPENSES_ENABLED", "0" if environment == "preview" else None)
    if not isinstance(recurring, str) or recurring not in ("0", "1"):
        raise ValueError("recurring execution must be an explicit string 0 or 1")
    triggers = config.get("triggers", {})
    if not isinstance(triggers, dict):
        raise ValueError("cron triggers must be a configuration object")
    crons = triggers.get("crons", [])
    if not isinstance(crons, list) or any(not isinstance(cron, str) for cron in crons):
        raise ValueError("cron expressions must be an explicit list of strings")
    if environment == "production" and (crons or recurring == "1"):
        if recurring != "1" or crons != PRODUCTION_CRONS:
            raise ValueError("production recurrence requires matching activation and one exact daily cron")
    if activate_production:
        if environment != "production":
            raise ValueError("production activation requires the production environment")
        # Validate the explicit deploy overlay without changing the paused file.
        vars_["NORULO_D1_ACCESS_ENABLED"] = "1"
    if activate_email_auth:
        vars_["NORULO_EMAIL_AUTH_ENABLED"] = "1"
    if activate_ai_suggestions:
        vars_["NORULO_JEV_SUGGESTIONS_ENABLED"] = "1"
        vars_["NORULO_JEV_SUGGESTIONS_EVALUATED"] = "1"
    if activate_recurring_expenses:
        vars_["NORULO_RECURRING_EXPENSES_ENABLED"] = "1"
        config.setdefault("triggers", {})["crons"] = PRODUCTION_CRONS.copy()
    product_preview = (environment == "preview" and
                       vars_.get("NORULO_PREVIEW_PRODUCT_ENABLED") == "1")
    access = vars_.get("NORULO_D1_ACCESS_ENABLED")
    if access not in {"0", "1"}:
        raise ValueError("D1 access must be an explicit 0 or 1")
    if environment == "preview" and access == "1" and not product_preview:
        raise ValueError("enabled preview D1 requires the product budget coordinator")
    if product_preview:
        bindings = config.get("durable_objects", {}).get("bindings", [])
        if (config.get("name") != "norulo-server-preview" or len(bindings) != 1
                or bindings[0].get("name") != "VALIDATION_BUDGET"
                or bindings[0].get("class_name") != "ValidationBudget"
                or vars_.get("NORULO_CREEM_API_BASE_URL") != "https://test-api.creem.io"):
            raise ValueError("product preview requires the existing budget coordinator and test provider")
    if vars_["NORULO_JEV_SUGGESTIONS_ENABLED"] == "1":
        if access != "1" or (environment == "preview" and not product_preview):
            raise ValueError("enabled AI suggestions require D1 access and an isolated runtime")
        if environment == "production":
            if vars_.get("NORULO_EMAIL_AUTH_ENABLED") != "1":
                raise ValueError("production AI suggestions require enabled email authentication")
            required_secrets = config.get("secrets", {}).get("required", [])
            if (not isinstance(required_secrets, list)
                    or any(not isinstance(name, str) for name in required_secrets)
                    or "TYPESAFE_API_KEY" not in required_secrets):
                raise ValueError("production AI suggestions require the TYPESAFE_API_KEY Worker secret")
    removal_upgrade = vars_.get("NORULO_PREVIEW_SCHEMA_V10_UPGRADE_ENABLED", "0")
    if removal_upgrade not in {"0", "1"}:
        raise ValueError("project removal schema upgrade must be explicitly enabled or disabled")
    if removal_upgrade == "1" and not (product_preview and access == "1"):
        raise ValueError("project removal schema upgrade requires the existing coordinated preview")
    production_scheduler = False
    if environment == "production":
        bindings = config.get("durable_objects", {}).get("bindings", [])
        migrations = config.get("migrations", [])
        production_scheduler = bindings == PRODUCTION_BINDINGS and migrations == PRODUCTION_MIGRATIONS
        if not (production_scheduler or (bindings == EMAIL_BINDINGS and migrations == EMAIL_MIGRATIONS)):
            raise ValueError("production requires its independent SQLite admission namespace and reviewed migration history")
    email_auth = vars_.get("NORULO_EMAIL_AUTH_ENABLED", "0")
    if email_auth not in {"0", "1"}:
        raise ValueError("email authentication must be explicitly enabled or disabled")
    if email_auth == "1":
        email_bindings = config.get("send_email", [])
        if (not (product_preview or environment == "production") or access != "1"
                or vars_.get("NORULO_EMAIL_FROM") != EMAIL_SENDER
                or not isinstance(email_bindings, list) or len(email_bindings) != 1
                or not isinstance(email_bindings[0], dict)
                or email_bindings[0] != {"name": "EMAIL", "allowed_sender_addresses": [EMAIL_SENDER]}):
            raise ValueError("enabled email authentication requires D1 access and one fixed EMAIL sender without recipient restrictions")
        if environment == "production":
            if "NORULO_EMAIL_CODE_SECRET" not in config.get("secrets", {}).get("required", []):
                raise ValueError("production email authentication requires its independent SQLite admission namespace, migration and code secret")
    crons = config.get("triggers", {}).get("crons", [])
    recurring = vars_.get("NORULO_RECURRING_EXPENSES_ENABLED", "0")
    if crons or recurring == "1":
        if environment == "production":
            if not (access == "1" and email_auth == "1" and production_scheduler
                    and vars_["NORULO_JEV_SUGGESTIONS_ENABLED"] == "1"
                    and vars_["NORULO_JEV_SUGGESTIONS_EVALUATED"] == "1"
                    and recurring == "1" and crons == PRODUCTION_CRONS):
                raise ValueError("production recurrence requires its independent scheduler, D1, email and AI activation with one daily cron")
        elif not (product_preview and access == "1" and recurring == "1"
                  and vars_.get("NORULO_PREVIEW_SCHEMA_V7_UPGRADE_ENABLED") == "1"
                  and crons == PREVIEW_CRONS):
            raise ValueError("only coordinated hourly preview recurrence is allowed")
    app_url = vars_.get("NORULO_APP_URL", "")
    allowed = vars_.get("NORULO_ALLOWED_ORIGINS", "")
    parsed_app = urlparse(app_url)
    if not host or parsed_app.scheme != "https" or not parsed_app.hostname or allowed != app_url:
        raise ValueError("HTTPS app URL and matching allowed origin are required")
    if vars_.get("NORULO_MODE") != environment or vars_.get("NORULO_COOKIE_SAME_SITE") != "None":
        raise ValueError("environment or Cookie origin policy is missing")
    databases = config.get("d1_databases", [])
    if len(databases) != 1 or databases[0].get("binding") != "DB":
        raise ValueError("one DB binding is required")
    database = databases[0]
    if database.get("migrations_dir") != "migrations" or not database.get("database_name"):
        raise ValueError("D1 migration layout is missing")
    database_id = database.get("database_id", "")
    if (not isinstance(database_id, str)
            or not re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", database_id)):
        raise ValueError("D1 database ID must be a UUID")
    normalized_database_id = database_id.lower()
    if normalized_database_id in SOURCE_DATABASE_IDS:
        raise ValueError("source-service databases cannot be used by Norulo")
    if (environment == "production" and vars_["NORULO_JEV_SUGGESTIONS_ENABLED"] == "1"
            and normalized_database_id == PLACEHOLDER_ID):
        raise ValueError("production AI suggestions require an independent configured database")
    other_environment = "production" if environment == "preview" else "preview"
    other_config_path = SERVER / f"wrangler.{other_environment}.jsonc"
    if normalized_database_id != PLACEHOLDER_ID and other_config_path.is_file():
        other_config = json.loads(other_config_path.read_text(encoding="utf-8"))
        if any(isinstance(item.get("database_id"), str)
               and normalized_database_id == item["database_id"].lower()
               for item in other_config.get("d1_databases", [])):
            raise ValueError("preview and production require separate databases")
    if product_preview and (host != "preview-api.norulo.com"
                            or app_url != "https://preview.norulo.com"):
        raise ValueError("active preview must retain its isolated database and hosts")
    if environment == "production" and access == "1":
        if (host != "api.norulo.com" or app_url != "https://norulo.com"
                or vars_.get("NORULO_GITHUB_CALLBACK_URL") != "https://norulo.com/api/auth/github/callback"
                or vars_.get("NORULO_CREEM_API_BASE_URL") != "https://api.creem.io"
                or vars_.get("NORULO_PREVIEW_PRODUCT_ENABLED", "0") != "0"
                or any(binding.get("name") == "VALIDATION_BUDGET"
                       or binding.get("class_name") == "ValidationBudget"
                       for binding in config.get("durable_objects", {}).get("bindings", []))):
            raise ValueError("active production must use its isolated database, hosts and live provider without preview controls")
    if not allow_placeholders and (
        database_id == PLACEHOLDER_ID
        or ".invalid" in host
        or ".invalid" in parsed_app.hostname
    ):
        raise ValueError("placeholder database ID or domain remains")
    if any(key for key in vars_ if key == "TYPESAFE_API_KEY"
           or "SECRET" in key or "TOKEN" in key or "PRIVATE_KEY" in key):
        raise ValueError("secrets must not appear in Wrangler vars")
    return config


def validate_config(environment: str, allow_placeholders: bool,
                    activate_production: bool = False,
                    activate_email_auth: bool = False,
                    activate_ai_suggestions: bool = False,
                    activate_recurring_expenses: bool = False) -> None:
    _validated_config(environment, allow_placeholders, activate_production,
                      activate_email_auth, activate_ai_suggestions, activate_recurring_expenses)


def write_deploy_config(path: Path, config: dict) -> None:
    """Fill only a private, empty mktemp file beside the canonical configuration."""
    if (path.parent.resolve() != SERVER.resolve()
            or not re.fullmatch(r"\.norulo-recurring-deploy\.[A-Za-z0-9]{6}\.jsonc", path.name)
            or path.is_symlink()):
        raise ValueError("deployment config must be a fresh recurring mktemp file in the Worker directory")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "w", encoding="utf-8") as output:
        metadata = os.fstat(output.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size != 0 or metadata.st_nlink != 1
                or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise ValueError("deployment config must be a private empty mktemp file")
        output.write(json.dumps(config, indent=2) + "\n")


def validate_contract() -> None:
    import yaml

    contract = yaml.safe_load((ROOT / "openapi" / "ledger-v1.yaml").read_text(encoding="utf-8"))
    if contract.get("openapi") != "3.1.0":
        raise ValueError("ledger OpenAPI version missing")
    operations = [operation for path in contract["paths"].values() for method, operation in path.items()
                  if method in {"get", "post", "patch", "delete"}]
    ids = [operation["operationId"] for operation in operations]
    if len(ids) != len(set(ids)) or any("x-norulo-scope" not in op for op in operations):
        raise ValueError("operation IDs or scope declarations invalid")
    if not contract["components"]["securitySchemes"]["bearerKey"]["scheme"] == "bearer":
        raise ValueError("Bearer API key contract missing")

    def visit(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key == "$ref" and nested.startswith("#/components/"):
                    target = contract
                    for segment in nested[2:].split("/"):
                        target = target[segment]
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(contract)
    migrations = list((SERVER / "migrations").glob("*.sql"))
    if not migrations or any(not sqlite3.complete_statement(path.read_text(encoding="utf-8"))
                             for path in migrations):
        raise ValueError("ledger migration is absent or incomplete")
    for path in migrations:
        for pattern in re.findall(r"\bGLOB\s+'((?:''|[^'])*)'", path.read_text(encoding="utf-8"), re.I):
            if len(pattern.replace("''", "'").encode("utf-8")) > 50:
                raise ValueError("native D1 GLOB pattern exceeds 50 bytes: " + path.name)
    with sqlite3.connect(":memory:") as database:
        for path in sorted(migrations):
            database.executescript(path.read_text(encoding="utf-8"))
        required = {"ledger_projects", "expenses", "expense_events", "app_state",
                    "api_keys", "billing_webhook_receipts", "billing_public_catalog", "ledger_plan_usage",
                    "expense_recurring_rules", "expense_recurring_occurrences", "expense_recurring_pending", "ledger_activity_events"}
        actual = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= actual:
            raise ValueError("ledger runtime migration tables are missing")
        # Canonical migrations and packaged authority must describe the same
        # final schema. Frozen old authorities remain separate upgrade proofs.
        sys.path.insert(0, str(ROOT))
        from norulo_server.cloudflare_preview_schema import (
            SCHEMA_VERSION, SCHEMA_SQL, SCHEMA_OBJECTS, SCHEMA_FINGERPRINT, MIGRATIONS,
        )
        if SCHEMA_VERSION != 14 or len(SCHEMA_SQL) > 64:
            raise ValueError("recurring recovery schema authority or fresh batch bound is invalid")
        def objects(connection):
            return tuple((kind, name, table, " ".join(sql.split()) if sql else None)
                         for kind, name, table, sql in connection.execute(
                             "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"))
        canonical = objects(database)
        if canonical != SCHEMA_OBJECTS or hashlib.sha256(json.dumps(
                canonical, separators=(",", ":")).encode()).hexdigest() != SCHEMA_FINGERPRINT:
            raise ValueError("canonical migrations and recurring recovery schema authority disagree")
        declared = {item["name"]: item["sha256"] for item in MIGRATIONS}
        if declared != {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in migrations}:
            raise ValueError("canonical migration hashes disagree with packaged authority")
        with sqlite3.connect(":memory:") as compiled:
            for sql in SCHEMA_SQL:
                compiled.execute(sql)
            if objects(compiled) != canonical:
                raise ValueError("fresh recurring recovery schema differs from canonical migrations")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=("preview", "production"))
    parser.add_argument("--allow-placeholders", action="store_true")
    parser.add_argument("--activate-production", action="store_true",
                        help="Validate an explicit production D1 activation overlay; no remote actions")
    parser.add_argument("--activate-email-auth", action="store_true",
                        help="Validate production email activation with --activate-production; no remote actions")
    parser.add_argument("--activate-ai-suggestions", action="store_true",
                        help="Validate reviewed production AI activation with --activate-production and --activate-email-auth; no remote actions")
    parser.add_argument("--activate-recurring-expenses", action="store_true",
                        help="Validate production daily recurrence with D1, email and AI activation; no remote actions")
    parser.add_argument("--write-deploy-config", type=Path,
                        help="Write the validated recurrence overlay to a fresh local Worker mktemp file")
    args = parser.parse_args()
    if args.activate_production and args.environment != "production":
        parser.error("--activate-production requires --environment production")
    if args.activate_email_auth and (args.environment != "production" or not args.activate_production):
        parser.error("--activate-email-auth requires --environment production --activate-production")
    if args.activate_ai_suggestions and (args.environment != "production" or not args.activate_production
                                         or not args.activate_email_auth):
        parser.error("--activate-ai-suggestions requires --environment production --activate-production --activate-email-auth")
    if args.activate_recurring_expenses and (args.environment != "production" or not args.activate_production
                                           or not args.activate_email_auth or not args.activate_ai_suggestions):
        parser.error("--activate-recurring-expenses requires --environment production --activate-production --activate-email-auth --activate-ai-suggestions")
    if args.write_deploy_config is not None and not args.activate_recurring_expenses:
        parser.error("--write-deploy-config requires --activate-recurring-expenses")
    try:
        validated = {}
        for environment in ((args.environment,) if args.environment else ("preview", "production")):
            validated[environment] = _validated_config(environment, args.allow_placeholders, args.activate_production,
                args.activate_email_auth, args.activate_ai_suggestions, args.activate_recurring_expenses)
        validate_contract()
        if args.write_deploy_config is not None:
            write_deploy_config(args.write_deploy_config, validated["production"])
    except (ValueError, KeyError, OSError, ImportError) as exc:
        print(f"S01 check failed: {exc}", file=sys.stderr)
        return 1
    print("S01 static checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
