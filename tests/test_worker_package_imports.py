"""Worker packaging must include imports reached only through the real entry."""
import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def packager():
    spec = importlib.util.spec_from_file_location("worker_package_sync",
        ROOT / "cloudflare/server/sync_server_modules.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_worker_entry_and_all_transitive_dependencies_are_packaged(packager):
    packager.check_package_imports(ROOT / "norulo_server", ROOT / "cloudflare/server/src/entry.py")


def test_real_production_entry_cannot_ship_without_recurring_helper(packager, monkeypatch):
    monkeypatch.setattr(packager, "MODULES", tuple(name for name in packager.MODULES
        if name != "cloudflare_recurring_scheduler"))
    with pytest.raises(SystemExit, match=r"entry.py imports unpackaged modules: cloudflare_recurring_scheduler"):
        packager.check_package_imports(ROOT / "norulo_server", ROOT / "cloudflare/server/src/entry.py")


@pytest.fixture
def package_fixture(tmp_path, packager, monkeypatch):
    source = tmp_path / "norulo_server"
    source.mkdir()
    (source / "module.py").write_text("from .leaf import Example\n")
    (source / "leaf.py").write_text("class Example: pass\n")
    entry = tmp_path / "entry.py"
    entry.write_text("from norulo_server.module import Example\n")
    monkeypatch.setattr(packager, "MODULES", ("module", "leaf"))
    return source, entry


@pytest.mark.parametrize("imports", [
    "from norulo_server.module import Example\n",
    "import norulo_server.module as alias\n",
    "from norulo_server import module as alias, leaf\n",
    "import norulo_server\n",
])
def test_all_supported_absolute_entry_import_styles_resolve(package_fixture, packager, imports):
    source, entry = package_fixture
    entry.write_text(imports)
    packager.check_package_imports(source, entry)


@pytest.mark.parametrize("imports,missing", [
    ("from norulo_server.missing import Example\n", "missing"),
    ("import norulo_server.missing as alias\n", "missing"),
    ("from norulo_server import module, missing as alias\n", "missing"),
    ("from norulo_server.module.missing import Example\n", "module.missing"),
    ("import norulo_server.module.missing\n", "module.missing"),
    ("from norulo_server import __version__\n", "__version__"),
])
def test_unavailable_entry_modules_and_source_only_exports_fail_before_copy(
        package_fixture, packager, imports, missing):
    source, entry = package_fixture
    entry.write_text(imports)
    with pytest.raises(SystemExit) as error:
        packager.check_package_imports(source, entry)
    assert str(error.value) == "entry.py imports unpackaged modules: " + missing


@pytest.mark.parametrize("imports", [
    "from .missing import Example\n",
    "from . import missing as alias\n",
    "from norulo_server.missing import Example\n",
    "from norulo_server import missing as alias\n",
    "import norulo_server.missing\n",
])
def test_transitive_relative_and_absolute_module_dependencies_still_checked(
        package_fixture, packager, imports):
    source, entry = package_fixture
    (source / "leaf.py").write_text(imports)
    with pytest.raises(SystemExit, match="leaf imports unpackaged modules: missing"):
        packager.check_package_imports(source, entry)


def test_conditional_entry_import_is_not_silently_left_out(package_fixture, packager):
    source, entry = package_fixture
    entry.write_text("if False:\n    from norulo_server.missing import Example\n")
    with pytest.raises(SystemExit, match="entry.py imports unpackaged modules: missing"):
        packager.check_package_imports(source, entry)


def test_sync_emits_exact_dependency_files_and_blank_package_init(
        package_fixture, packager, monkeypatch):
    source, entry = package_fixture
    (source / "__init__.py").write_text("__version__ = 'source-only'\n")
    worker = source.parent / "cloudflare/server"
    (worker / "src").mkdir(parents=True)
    (worker / "src/entry.py").write_bytes(entry.read_bytes())
    monkeypatch.setattr(packager, "__file__", str(worker / "sync_server_modules.py"))
    monkeypatch.setattr(sys, "argv", ["sync_server_modules.py"])
    packager.main()
    target = worker / "src/norulo_server"
    assert (target / "__init__.py").read_bytes() == b""
    assert {path.stem for path in target.glob("*.py")} == {"module", "leaf", "__init__"}
    for name in ("module", "leaf"):
        assert (target / (name + ".py")).read_bytes() == (source / (name + ".py")).read_bytes()
    monkeypatch.setattr(sys, "argv", ["sync_server_modules.py", "--check"])
    packager.main()
    (target / "leaf.py").unlink()
    with pytest.raises(SystemExit, match="stale local Server module: leaf"):
        packager.main()
