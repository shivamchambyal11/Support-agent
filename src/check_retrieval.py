from rag import retrieve

tests = [
    ("Refund kitne din mein aata hai?", "refunds.md"),
    ("How many days does a refund take?", "refunds.md"),
    ("Return window kitna hai?", "returns.md"),
    ("What is the return window?", "returns.md"),
    ("Shipped order cancel ho sakta hai?", "cancellation.md"),
    ("Can I cancel a shipped order?", "cancellation.md"),
    ("Free shipping kab milti hai?", "shipping.md"),
    ("Headphones ki warranty kitni hai?", "warranty.md"),
    ("Damaged item kitne din mein return ho sakta hai?", "returns.md"),
    ("COD order ka refund kaise milta hai?", "refunds.md"),
]

hits = 0
top1 = 0
for question, expected in tests:
    results = retrieve(question)
    sources = [source for text, source in results]
    if expected in sources:
        hits += 1
    if sources[0] == expected:
        top1 += 1
    print(sources[0], "|", "OK " if expected in sources else "MISS", "|", question)

print("Hit@4:", hits, "/", len(tests))
print("Top-1:", top1, "/", len(tests))