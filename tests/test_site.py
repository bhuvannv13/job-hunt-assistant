"""The website runs the same Python modules in the browser (Pyodide); keep the copies in sync."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROWSER_MODULES = ["__init__.py", "models.py", "skills.py", "match.py", "cv.py", "tracker.py", "tailor.py"]


def test_browser_copies_match_package():
    for name in BROWSER_MODULES:
        assert (ROOT / "docs" / "py" / "jobhunt" / name).read_text() == (ROOT / "jobhunt" / name).read_text(), \
            f"docs/py/jobhunt/{name} is out of date: run tools/sync_site.sh"


def test_browser_modules_avoid_heavy_imports():
    # sklearn, yaml and requests are not loaded in the browser, so they must only be imported inside functions.
    for name in BROWSER_MODULES:
        top = [l for l in (ROOT / "jobhunt" / name).read_text().splitlines() if l.startswith(("import ", "from "))]
        assert not any(m in l for l in top for m in ("sklearn", "yaml", "requests", "pdfplumber")), name


def test_skill_patterns_compile_in_javascript_syntax():
    from jobhunt.pipeline import write_skills
    path = ROOT / "tests" / "_skills.json"
    write_skills(path)
    data = json.loads(path.read_text())
    path.unlink()
    assert "Python" in data and data["R"]["flags"] == "" and data["Python"]["flags"] == "i"
    for spec in data.values():
        assert "(?P<" not in spec["source"] and "(?i" not in spec["source"]
