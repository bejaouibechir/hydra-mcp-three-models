"""Create data/shop.db: 300 customers and 2,000 orders (same rows on every machine).

The amounts were imported from a CSV export and are stored as TEXT, as often
happens: a pipeline must convert them before adding them up.
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shop.db"

COUNTRIES = ["France", "Germany", "Spain", "Italy", "Belgium", "Tunisia", "Morocco", "Canada"]
FIRST = ["Amel", "Bruno", "Chloe", "David", "Elena", "Farid", "Greta", "Hugo", "Ines", "Jonas",
         "Karim", "Lea", "Marco", "Nadia", "Omar", "Paula", "Rania", "Sven", "Tara", "Yanis"]
LAST = ["Martin", "Rossi", "Garcia", "Muller", "Haddad", "Dubois", "Bianchi", "Lopez",
        "Schmidt", "Benali", "Peeters", "Tremblay"]


def main() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    rnd = random.Random(42)
    conn = sqlite3.connect(DB)
    conn.executescript("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            country     TEXT NOT NULL
        );
        CREATE TABLE orders (
            order_id    INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
            ordered_at  TEXT NOT NULL,          -- ISO date
            amount      TEXT NOT NULL,          -- imported from a CSV export: text, not a number
            status      TEXT NOT NULL           -- paid, refunded or cancelled
        );
    """)
    customers = [(i, f"{rnd.choice(FIRST)} {rnd.choice(LAST)}", rnd.choice(COUNTRIES))
                 for i in range(1, 301)]
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", customers)
    start = date(2026, 1, 1)
    orders = []
    for i in range(1, 2001):
        status = rnd.choices(["paid", "refunded", "cancelled"], weights=[80, 12, 8])[0]
        amount = f"{rnd.uniform(5, 900):.2f}"
        day = start + timedelta(days=rnd.randrange(0, 304))
        orders.append((1000 + i, rnd.randrange(1, 301), day.isoformat(), amount, status))
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    conn.commit()
    conn.close()
    print(f"{DB.relative_to(ROOT)}: 300 customers, 2000 orders")


if __name__ == "__main__":
    main()
