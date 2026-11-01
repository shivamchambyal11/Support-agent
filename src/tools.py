import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mock.db"

# KB docs ke numbers yahi hain
RETURN_WINDOW_DAYS = {"standard": 7, "gold": 10, "premium": 14}
DAMAGED_WINDOW_DAYS = 15
HUMAN_APPROVAL_LIMIT = 5000  # isse bada refund human approve karega


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _err(code, message):
    return {"ok": False, "error": code, "message": message}


# ---------- read tools ----------

def get_customer(customer_id):
    with _conn() as con:
        row = con.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not row:
        return _err("not_found", f"Customer {customer_id} not found")
    return {"ok": True, **dict(row)}


def get_order(order_id):
    with _conn() as con:
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            return _err("not_found", f"Order {order_id} not found")
        rows = con.execute(
            "SELECT product, qty, price FROM order_items WHERE order_id=?", (order_id,)
        ).fetchall()
    items = [dict(r) for r in rows]
    return {"ok": True, **dict(order), "items": items}


def check_return_eligibility(order_id, damaged=False):
    order = get_order(order_id)
    if not order["ok"]:
        return order

    if order["status"] != "delivered":
        return {"ok": True, "eligible": False, "reason": "not_delivered",
                "message": f"Order status is '{order['status']}', only delivered orders can be returned"}

    customer = get_customer(order["customer_id"])
    tier = customer.get("tier", "standard")

    if damaged:
        window = DAMAGED_WINDOW_DAYS
    else:
        window = RETURN_WINDOW_DAYS.get(tier, 7)

    delivered_on = datetime.fromisoformat(order["delivered_at"])
    days_since = (datetime.now() - delivered_on).days

    if days_since > window:
        return {"ok": True, "eligible": False, "reason": "window_expired",
                "days_since_delivery": days_since, "window_days": window,
                "message": f"Delivered {days_since} days ago, window is {window} days"}

    return {"ok": True, "eligible": True,
            "days_since_delivery": days_since, "window_days": window,
            "message": f"Within {window}-day window"}


# ---------- write tools (checks andar hi hain) ----------

def cancel_order(order_id):
    order = get_order(order_id)
    if not order["ok"]:
        return order

    if order["status"] == "cancelled":
        return _err("already_cancelled", "Order is already cancelled")
    if order["status"] != "placed":
        return _err("not_cancellable",
                    f"Order is '{order['status']}'. Only 'placed' orders can be cancelled")

    with _conn() as con:
        con.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))

    return {"ok": True, "order_id": order_id, "new_status": "cancelled",
            "message": "Order cancelled. Prepaid refund in 3-5 working days"}


def initiate_refund(order_id, amount, damaged=False):
    elig = check_return_eligibility(order_id, damaged)
    if not elig["ok"]:
        return elig
    if not elig["eligible"]:
        return _err("not_eligible", elig["message"])

    if amount <= 0:
        return _err("invalid_amount", "Refund amount must be positive")

    order = get_order(order_id)

    with _conn() as con:
        row = con.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM refunds WHERE order_id=?", (order_id,)
        ).fetchone()
        already_refunded = row[0]
        remaining = order["total"] - already_refunded

        if amount > remaining + 1e-9:
            return _err("exceeds_total", f"Max refundable now is {remaining:.2f}")

        if amount > HUMAN_APPROVAL_LIMIT:
            status = "pending_human_approval"
            message = "Amount is above Rs 5000, sent for human approval"
        else:
            status = "processed"
            message = "Refund will reach in 5-7 working days"

        cur = con.execute(
            "INSERT INTO refunds(order_id, amount, status) VALUES(?,?,?)",
            (order_id, amount, status),
        )

    return {"ok": True, "refund_id": cur.lastrowid, "order_id": order_id,
            "amount": amount, "status": status, "message": message}