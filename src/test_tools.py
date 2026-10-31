import sqlite3

from mock_db import init, DB_PATH
from tools import (get_order, check_return_eligibility, cancel_order, initiate_refund)

passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}")


init()  # fresh seeded DB

# Read tools
check("get_order(1) delivered", get_order(1)["status"] == "delivered")
check("get_order(999) not_found", get_order(999)["error"] == "not_found")

# Eligibility
check("order 1 eligible (delivered 2 days ago)", check_return_eligibility(1)["eligible"] is True)
check("order 2 not eligible (20 days)", check_return_eligibility(2)["reason"] == "window_expired")
check("order 2 damaged also expired (>15 days)", check_return_eligibility(2, damaged=True)["eligible"] is False)
check("order 3 shipped not eligible", check_return_eligibility(3)["reason"] == "not_delivered")

# Cancel
check("cancel shipped refused", cancel_order(3)["error"] == "not_cancellable")
check("cancel already cancelled refused", cancel_order(4)["error"] == "already_cancelled")
check("cancel placed ok", cancel_order(5)["ok"] is True)
check("cancel same order again refused", cancel_order(5)["error"] == "already_cancelled")

# Refund
check("refund on ineligible order refused", initiate_refund(2, 100)["error"] == "not_eligible")
r = initiate_refund(1, 100)
check("refund 100 on order 1 processed", r["ok"] and r["status"] == "processed")
check("refund more than remaining refused", initiate_refund(1, 999999)["error"] == "exceeds_total")
check("negative refund refused", initiate_refund(1, -5)["error"] == "invalid_amount")

# Human approval limit
init()
with sqlite3.connect(DB_PATH) as con:
    con.execute("UPDATE orders SET total=8000 WHERE id=1")
r = initiate_refund(1, 6000)
check("refund 6000 pending human approval", r["ok"] and r["status"] == "pending_human_approval")

print(f"\n{passed} passed, {failed} failed")