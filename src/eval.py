import time

import agent_openai as A
from mock_db import init

RUNS = 3  # har case kitni baar chalana hai

# (customer, sawal, jo tools chalne chahiye, jo nahi chalne chahiye)
cases = [
    (1, "Refund kitne din mein aata hai?", ["search_policy"], ["get_order"]),
    (1, "Order 1 ka status batao", ["get_order"], ["search_policy"]),
    (1, "Order 1 return kar sakta hoon, aur refund kitne din mein aayega?",
     ["check_return_eligibility", "search_policy"], []),
    (1, "Gold customer ka return window kitna hota hai?", ["search_policy"], []),
    (1, "Aaj ka weather kaisa hai?", [], ["search_policy", "get_order"]),
]

total_wins = 0
total_runs = 0

for customer, message, must, must_not in cases:
    wins = 0
    for run in range(RUNS):
        init()
        A.TRACE.clear()
        try:
            A.run_turn([{"role": "user", "content": message}], customer)
        except Exception as e:
            print("   ERROR:", str(e)[:80])

        names = []
        for name, args, result in A.TRACE:
            names.append(name)

        missing = [m for m in must if m not in names]
        unexpected = [x for x in must_not if x in names]

        if len(missing) == 0 and len(unexpected) == 0:
            wins += 1
        else:
            print("   fail:", names, "| missing:", missing, "| unexpected:", unexpected)
        time.sleep(2)

    total_wins += wins
    total_runs += RUNS
    print(f"{wins}/{RUNS} | {message}")

print()
print(f"Overall: {total_wins}/{total_runs} = {total_wins / total_runs * 100:.0f}%")