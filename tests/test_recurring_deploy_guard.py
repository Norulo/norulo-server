"""Preview-only background execution configuration cannot bleed into production."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
from deployment_config_fixture import configured_runtime

ROOT = Path(__file__).resolve().parents[1]


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
    for kind in ("high_frequency", "extra_cron", "disabled", "no_upgrade", "uncoordinated", "paused", "no_cron"):
        config = copy.deepcopy(original)
        if kind == "high_frequency":
            config["triggers"]["crons"] = ["* * * * *"]
        elif kind == "extra_cron":
            config["triggers"]["crons"].append("30 * * * *")
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
            config["triggers"] = {"crons": ["0 * * * *"]}
        path.write_text(json.dumps(config))
        with pytest.raises(ValueError):
            module.validate_config("production", False)
