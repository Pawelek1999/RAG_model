import re

TEST_SEQUENCE_PATTERN = re.compile(
    r"\b(?:[A-Za-z0-9]+_)?(?P<test_number>\d{5})\.(?P<step_number>\d{3})\b"
)
TEST_NUMBER_PATTERN = re.compile(r"\b(?P<test_number>\d{5})\b")
BUG_NUMBER_PATTERN = re.compile(r"\bBUG(?:\s*NB)?\s*[:#-]?\s*(?P<bug_number>\d+)\b", re.IGNORECASE)
ERROR_KEYWORDS = ("not ok", "nok", "bug", "failed", "fail", "error", "ok")

LIST_BUGS_HINTS = (
    "list bugs",
    "wypisz bug",
    "wypisz wszystkie bug",
    "lista bug",
    "all bugs",
)

BUG_LOCATION_HINTS = (
    "where bug",
    "gdzie bug",
    "w ktorym tescie",
    "w ktorym kroku",
    "in which test",
    "in which step",
)

AFFECTED_TEST_HINTS = (
    "show complete test",
    "pelny test",
    "kompletny test",
    "all steps from",
    "powiazany test",
    "pelna sekwencje",
    "full sequence",
)

TEST_STEPS_HINTS = (
    "show test steps",
    "pokaz kroki",
    "test steps",
    "kroki testu",
)
