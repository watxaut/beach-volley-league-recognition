"""Guard: STATUS.md stays LEAN (owner directive 2026-10-06, session #86).

The lean convention (STATUS.md header) sets hard budgets so the cross-session
memory never grows back to its 2465-line size. This test fails when a budget
is exceeded -- the fix is ALWAYS the same: move the verbatim text to
docs/history/status_log_archive.md (old Where-we-are blocks ->
status_where_we_are_archive.md), then shrink. Never delete history, never
relax the budgets without an owner decision.
"""

from pathlib import Path

import pytest

STATUS = Path(__file__).resolve().parents[1] / "STATUS.md"

# (header, max lines) -- budgets as ratified 2026-10-06, with a little room.
SECTION_BUDGETS = {
    "## Where we are": 80,
    "## Active next": 25,
    "## Next task cards": 10,
    "## Open points": 115,
    "## Learnings": 140,
    "## Session index": 100,
}

CANONICAL_ORDER = [
    "## North-star goals",
    "## Where we are",
    "## Active next",
    "## Next task cards",
    "## Open points",
    "## Learnings",
    "## Session index",
    "## Log",
]

MAX_TOTAL_LINES = 600
MAX_LOG_SESSIONS = 3
MAX_INDEX_LINE_CHARS = 240


def _sections() -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "(header)"
    sections[current] = []
    for line in STATUS.read_text().splitlines():
        if line.startswith("## "):
            current = line
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return sections


def test_status_exists():
    assert STATUS.is_file(), "STATUS.md missing"


def test_total_lines():
    n = len(STATUS.read_text().splitlines())
    assert n <= MAX_TOTAL_LINES, (
        f"STATUS.md is {n} lines (budget {MAX_TOTAL_LINES}). Archive verbatim "
        "text to docs/history/ and shrink -- see the lean convention header."
    )


def test_canonical_sections_present_and_ordered():
    lines = [l.strip() for l in STATUS.read_text().splitlines()]
    found: list[str] = []
    for line in lines:
        for header in CANONICAL_ORDER:
            if line.startswith(header) and not any(
                f.startswith(header) for f in found
            ):
                found.append(header)
    assert found == CANONICAL_ORDER, f"Canonical headers missing/out of order: {found}"


@pytest.mark.parametrize("header,budget", sorted(SECTION_BUDGETS.items()))
def test_section_budgets(header, budget):
    sections = _sections()
    matches = [h for h in sections if h.startswith(header)]
    assert matches, f"Section {header!r} not found"
    n = len(sections[matches[0]])
    assert n <= budget, (
        f"Section {header} is {n} lines (budget {budget}). Move verbatim text "
        "to docs/history/ and shrink -- see the lean convention header."
    )


def test_log_holds_at_most_three_sessions():
    sections = _sections()
    log = sections.get("## Log (newest first)", [])
    sessions = [l for l in log if l.startswith("### ")]
    assert len(sessions) <= MAX_LOG_SESSIONS, (
        f"Log holds {len(sessions)} sessions (max {MAX_LOG_SESSIONS}). Move "
        "the oldest verbatim to docs/history/status_log_archive.md."
    )


def test_session_index_one_line_per_session():
    sections = _sections()
    idx = sections.get("## Session index (one line each)", [])
    for line in idx:
        if not line.strip():
            continue
        assert line.startswith("- "), f"Index entry not a bullet: {line[:60]!r}"
        assert len(line) <= MAX_INDEX_LINE_CHARS, (
            f"Index entry too long ({len(line)} chars): {line[:80]!r}... "
            "Compress it; the full story belongs in the Log or docs/."
        )


def test_task_cards_hold_no_done_cards():
    """A DONE/REFUTED card must be archived, not kept here (the old file kept
    ~700 lines of finished cards)."""
    sections = _sections()
    for header, body in sections.items():
        if header.startswith("## Next task cards"):
            card_lines = [
                (i, l)
                for i, l in enumerate(body)
                if l.startswith("### CARD")
            ]
            for (i, card_line) in card_lines:
                card_text = card_line + "\n" + "\n".join(
                    body[i + 1 :][: next(
                        (j for j, l in enumerate(body[i + 1 :], i + 1) if l.startswith("### ")),
                        len(body),
                    ) - (i + 1) :]
                )
                assert "DONE" not in card_text and "REFUTED" not in card_text, (
                    f"Finished card left in STATUS.md: {card_line!r} -- archive it "
                    "verbatim under its session date in docs/history/"
                    "status_log_archive.md and delete it from STATUS.md."
                )
            return
    pytest.fail("## Next task cards section not found")
