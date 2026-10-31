import sys

from google.genai import types

import tools as T
from llm import gemini_step

SYSTEM = """You are a support agent for an e-commerce store. Reply in the language the customer uses.
Rules:
- Use tools to look up real order data. Never guess order details.
- Before cancelling an order or initiating a refund, ask the customer to confirm and wait for a clear 'yes'.
- Set damaged=true only if the customer says the item is damaged or wrong.
- If a tool returns an error, explain it to the customer simply. Do not retry the same call.
- If a refund needs human approval, tell the customer it is sent for review."""


def make_tools(customer_id: int):
    """LLM ko dikhne wale tool functions. Docstrings + type hints se schema banta hai."""

    def _forbidden(order_id: int):
        """Order isi customer ka hai ya nahi. Error dict return karta hai, ya None agar sab theek."""
        o = T.get_order(order_id)
        if not o["ok"]:
            return o
        if o["customer_id"] != customer_id:
            return T._err("forbidden", "This order does not belong to the current customer")
        return None

    def get_order(order_id: int) -> dict:
        """Get status, total, delivery date and items of one of the customer's orders."""
        return _forbidden(order_id) or T.get_order(order_id)

    def check_return_eligibility(order_id: int, damaged: bool) -> dict:
        """Check whether a delivered order can still be returned under policy."""
        return _forbidden(order_id) or T.check_return_eligibility(order_id, damaged)

    def cancel_order(order_id: int) -> dict:
        """Cancel an order. Works only for orders in 'placed' status. Needs customer confirmation first."""
        return _forbidden(order_id) or T.cancel_order(order_id)

    def initiate_refund(order_id: int, amount: float, damaged: bool) -> dict:
        """Start a refund for a returned order. Needs customer confirmation first."""
        return _forbidden(order_id) or T.initiate_refund(order_id, amount, damaged)

    return [get_order, check_return_eligibility, cancel_order, initiate_refund]


def run_turn(contents: list, customer_id: int, max_steps: int = 6) -> str:
    fns = make_tools(customer_id)
    registry = {f.__name__: f for f in fns}
    system = SYSTEM + f"\nThe logged-in customer id is {customer_id}."

    for _ in range(max_steps):
        resp = gemini_step(contents, system, fns)
        content = resp.candidates[0].content
        contents.append(content)  # model ka poora turn as-is wapas history mein

        calls = [p.function_call for p in (content.parts or []) if p.function_call]
        if not calls:
            return resp.text or "(empty reply)"

        results = []
        for c in calls:
            args = {k: (int(v) if isinstance(v, float) and v.is_integer() and k.endswith("_id") else v)
                    for k, v in dict(c.args or {}).items()}
            print(f"  [tool] {c.name}({args})")
            fn = registry.get(c.name)
            try:
                out = fn(**args) if fn else {"ok": False, "error": "unknown_tool"}
            except Exception as e:  # LLM ne galat args diye to bhi crash nahi
                out = {"ok": False, "error": "tool_exception", "message": str(e)}
            print(f"  [result] {out}")
            results.append(types.Part.from_function_response(name=c.name, response=out))
        contents.append(types.Content(role="user", parts=results))

    return "Sorry, request process nahi ho paayi (too many steps). Please dobara try karein."


if __name__ == "__main__":
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Agent ready (customer {cid}). Exit ke liye 'q'.\n")
    history: list = []
    while True:
        q = input("You: ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        if not q:
            continue
        history.append(types.Content(role="user", parts=[types.Part.from_text(text=q)]))
        try:
            print(f"\nAgent: {run_turn(history, cid)}\n")
        except Exception as e:
            print(f"\n[ERROR] {str(e)[:200]}\n")