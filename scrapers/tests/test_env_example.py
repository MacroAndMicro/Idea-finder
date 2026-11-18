"""IF-79: every environment variable the code reads is listed in .env.example.

Scans scrapers/ (AST: get_env / require_env / os.getenv / os.environ.get / os.environ[...]
with a string literal, plus the module-level env-name tables) and every ``${VAR}``
placeholder in the backend application.yaml. Commented-out lines in .env.example count,
so optional variables can stay documented but unset. Names only; never values.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scrapers.adapters import reddit
from scrapers.ingest import SOURCE_LISTS
from scrapers.pipeline import SOURCE_SECRETS

SCRAPERS = Path(__file__).resolve().parents[1]
REPO = SCRAPERS.parent
ENV_EXAMPLE = REPO / ".env.example"
APPLICATION_YAML = REPO / "backend" / "src" / "main" / "resources" / "application.yaml"

ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
ENV_CALLS = {"get_env", "require_env", "getenv"}

#: Names read by code that must NOT be documented in .env.example, as name -> reason.
#: Empty today: every variable the code reads is safe to list by name.
ALLOWLIST: dict[str, str] = {}


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        # os.environ.get(...) -> "environ.get"
        if func.attr == "get" and isinstance(func.value, ast.Attribute) and (
            func.value.attr == "environ"
        ):
            return "environ.get"
        return func.attr
    return None


def _is_environ(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "environ"


def _literal_name(node: ast.expr | None) -> str | None:
    if (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and ENV_NAME.match(node.value)):
        return node.value
    return None


def names_read_by_scrapers() -> set[str]:
    names: set[str] = set()
    for path in SCRAPERS.rglob("*.py"):
        if "tests" in path.relative_to(SCRAPERS).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Call) and node.args and (
                _call_name(node.func) in ENV_CALLS | {"environ.get"}
            ):
                name = _literal_name(node.args[0])
            elif isinstance(node, ast.Subscript) and _is_environ(node.value):
                name = _literal_name(node.slice)
            if name:
                names.add(name)
    # Env names held in tables and read through a variable.
    for lists in SOURCE_LISTS.values():
        names.update(env for _kwarg, env in lists.values())
    for secrets in SOURCE_SECRETS.values():
        names.update(secrets)
    names.update(reddit.REQUIRED_VARS)
    return names


def names_in_application_yaml() -> set[str]:
    text = APPLICATION_YAML.read_text(encoding="utf-8")
    return set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", text))


def documented_names() -> set[str]:
    names: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=", line)
        if m:
            names.add(m.group(1))
    return names


def test_scanner_finds_known_reads():
    # Guards against the scan silently matching nothing.
    found = names_read_by_scrapers()
    assert {"SUPABASE_URL", "LLM_PROVIDER", "GITHUB_TOKEN", "SCRAPER_USER_AGENT",
            "REDDIT_SUBREDDITS"} <= found
    assert {"DATABASE_URL", "FRONTEND_ORIGIN"} <= names_in_application_yaml()


def test_every_env_var_read_is_in_env_example():
    required = (names_read_by_scrapers() | names_in_application_yaml()) - set(ALLOWLIST)
    missing = sorted(required - documented_names())
    assert not missing, f".env.example is missing: {', '.join(missing)}"


def test_documented_name_parser_counts_commented_lines():
    assert "DB_POOL_MAX_SIZE" in documented_names()  # commented-out optional line


def test_env_example_has_no_real_looking_secrets():
    secret_names = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD)$")
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z][A-Z0-9_]*)=(.*)$", line)
        if m and secret_names.search(m.group(1)):
            value = m.group(2).strip()
            assert value == "" or "your_" in value, f"{m.group(1)} must not carry a value"
