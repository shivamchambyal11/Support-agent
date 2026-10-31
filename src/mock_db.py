import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "mock.db"


def init(path=DB_PATH):
    """DB ko scratch se banata hai. Har run pe same data aata hai (seed fixed)."""
    random.seed(42)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
    DROP TABLE IF EXISTS refunds;
    DROP TABLE IF EXISTS order_items;
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS customers;
    CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, email TEXT, tier TEXT);
    CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INT, status TEXT,
        total REAL, placed_at TEXT, delivered_at TEXT);
    CREATE TABLE order_items(order_id INT, product TEXT, qty INT, price REAL);
    CREATE TABLE refunds(id INTEGER PRIMARY KEY, order_id INT, amount REAL, status TEXT);
    """)

    tiers = ["standard", "standard", "gold", "premium"]
    for i in range(1, 11):
        con.execute("INSERT INTO customers VALUES(?,?,?,?)",
                    (i, f"Customer {i}", f"c{i}@mail.com", random.choice(tiers)))

    now = datetime.now()
    products = ["Shoes", "Headphones", "T-shirt", "Mixer"]

    # Fixed edge-case orders: (id, customer, status, days_since_delivery, total)
    edge_cases = [
        (1, 1, "delivered", 2, 1999.0),     # return window ke andar
        (2, 2, "delivered", 20, 2499.0),    # return window ke bahar
        (3, 3, "shipped", None, 999.0),     # abhi raaste mein
        (4, 4, "cancelled", None, 1499.0),  # already cancelled
        (5, 5, "placed", None, 799.0),      # cancel ho sakta hai
    ]
    for oid, cust, status, days, total in edge_cases:
        placed = now - timedelta(days=(days or 1) + 3)
        delivered = (now - timedelta(days=days)).isoformat() if status == "delivered" else None
        con.execute("INSERT INTO orders VALUES(?,?,?,?,?,?)",
                    (oid, cust, status, total, placed.isoformat(), delivered))
        con.execute("INSERT INTO order_items VALUES(?,?,?,?)",
                    (oid, random.choice(products), 1, total))

    # Baaki random orders
    statuses = ["placed", "shipped", "delivered", "delivered", "cancelled"]
    for oid in range(6, 26):
        st = random.choice(statuses)
        placed = now - timedelta(days=random.randint(5, 30))
        delivered = (placed + timedelta(days=3)).isoformat() if st == "delivered" else None
        total = round(random.uniform(300, 5000), 2)
        con.execute("INSERT INTO orders VALUES(?,?,?,?,?,?)",
                    (oid, random.randint(1, 10), st, total, placed.isoformat(), delivered))
        con.execute("INSERT INTO order_items VALUES(?,?,?,?)",
                    (oid, random.choice(products), 1, total))

    con.commit()
    con.close()
    print("Mock DB ready:", path)


if __name__ == "__main__":
    init()