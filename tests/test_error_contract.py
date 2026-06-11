import re
from pathlib import Path

import errors

APP_JS = Path(__file__).resolve().parent.parent / "static" / "app.js"


def frontend_catalog_keys():
    source = APP_JS.read_text(encoding="utf-8")
    match = re.search(r"const ERROR_MESSAGES = \{(.*?)\n\};", source, re.DOTALL)
    assert match, "ERROR_MESSAGES catalog not found in app.js"
    return set(re.findall(r"^\s*(\w+):", match.group(1), re.MULTILINE))


def test_every_backend_code_has_frontend_message():
    keys = frontend_catalog_keys()
    missing = [code for code in errors.FRONTEND_CATALOG_CODES if code not in keys]
    assert not missing, f"app.js ERROR_MESSAGES missing: {missing}"


def test_catalog_list_matches_module_constants():
    declared = {
        value for name, value in vars(errors).items()
        if name.isupper() and isinstance(value, str) and not name.endswith("_PREFIX")
    }
    assert declared == set(errors.FRONTEND_CATALOG_CODES)
