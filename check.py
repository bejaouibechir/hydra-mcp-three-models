"""Checks outputs/revenue_by_country.csv of a workspace against the expected result.

    python check.py                    # the reference expected values, computed from data/shop.db
    python check.py runs/claude        # checks the output of a run
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLUMNS = ["country", "orders", "revenue"]


def expected(db: Path = ROOT / "data" / "shop.db") -> list[tuple[str, int, float]]:
    """The answer, computed in plain SQL from the same database."""
    con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT c.country, COUNT(*), ROUND(SUM(CAST(o.amount AS REAL)), 2) AS revenue "
        "FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
        "WHERE o.status = 'paid' GROUP BY c.country ORDER BY revenue DESC").fetchall()
    con.close()
    return [(c, int(n), float(r)) for c, n, r in rows]


def check(workspace: Path) -> tuple[bool, list[str]]:
    """Returns (ok, lines explaining every difference)."""
    out = workspace / "outputs" / "revenue_by_country.csv"
    if not out.exists():
        return False, [f"missing: {out.relative_to(workspace)}"]
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return False, ["the file is empty"]
    problems: list[str] = []
    header, data = [h.strip() for h in rows[0]], rows[1:]
    if header != COLUMNS:
        problems.append(f"columns are {header}, expected {COLUMNS}")
        return False, problems
    want = expected()
    if len(data) != len(want):
        problems.append(f"{len(data)} rows, expected {len(want)}")
    for i, (row, (country, n, rev)) in enumerate(zip(data, want), start=1):
        try:
            got = (row[0], int(float(row[1])), float(row[2]))
        except (ValueError, IndexError):
            problems.append(f"row {i}: cannot read {row}")
            continue
        if got[0] != country:
            problems.append(f"row {i}: country {got[0]!r}, expected {country!r} (order or content)")
        if got[1] != n:
            problems.append(f"row {i} ({country}): orders {got[1]}, expected {n}")
        if abs(got[2] - rev) > 0.005:
            problems.append(f"row {i} ({country}): revenue {row[2]}, expected {rev:.2f}")
        elif "." in row[2] and len(row[2].strip().split(".")[1]) > 2:
            problems.append(f"row {i} ({country}): revenue {row[2]} is not rounded to 2 decimals")
    return not problems, problems


def main() -> int:
    if len(sys.argv) < 2:
        print(f"{'country':<10} {'orders':>6} {'revenue':>12}")
        for c, n, r in expected():
            print(f"{c:<10} {n:>6} {r:>12.2f}")
        return 0
    ws = Path(sys.argv[1]).resolve()
    ok, problems = check(ws)
    if ok:
        print("CHECK OK: 8 countries, paid orders only, rounded, sorted, exact columns.")
        return 0
    print("CHECK FAILED:")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())
