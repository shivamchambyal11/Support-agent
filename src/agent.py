import sys

from google.genai import types

import tools as T
from llm import gemini_step
from rag import retrieve

SYSTEM = """You are a support agent for an e-commerce store. Reply in the language the customer uses.
Rules:
- Use tools to look up real order data. Never guess order details.
- Before cancelling an order or initiating a refund, ask the customer to confirm and wait for a clear 'yes'.
- Set damaged=true only if the customer says the item is damaged or wrong.
- If a tool returns an error, explain it to the customer simply. Do not retry the same call.
- If a refund needs human approval, tell the customer it is sent for review.
- For policy questions (returns, refunds, shipping, warranty), call search_policy and answer only from its results. Do not answer policies from your own knowledge."""


def make_tools(customer_id: int):

    def check_owner(order_id: int):
        # order is customer ka hai ya nahi. Theek hai to None, nahi to error dict
        order = T.get_order(order_id)
        if not order["ok"]:
            return order
        if order["customer_id"] != customer_id:
            return T._err("forbidden", "This order does not belong to the current customer")
        return None

    def get_order(order_id: int) -> dict:
        """Get status, total, delivery date and items of one of the customer's orders."""
        return check_owner(order_id) or T.get_order(order_id)

    def check_return_eligibility(order_id: int, damaged: bool) -> dict:
        """Check whether a delivered order can still be returned under policy."""
        return check_owner(order_id) or T.check_return_eligibility(order_id, damaged)

    def cancel_order(order_id: int) -> dict:
        """Cancel an order. Works only for orders in 'placed' status. Needs customer confirmation first."""
        return check_owner(order_id) or T.cancel_order(order_id)

    def initiate_refund(order_id: int, amount: float, damaged: bool) -> dict:
        """Start a refund for a returned order. Needs customer confirmation first."""
        return check_owner(order_id) or T.initiate_refund(order_id, amount, damaged)

    def search_policy(question: str) -> dict:
        """Search the store policy documents (returns, refunds, shipping, cancellation, warranty)."""
        hits = retrieve(question)
        results = []
        for text, source in hits:
            results.append({"source": source, "text": text})
        return {"ok": True, "results": results}

    return [get_order, check_return_eligibility, cancel_order, initiate_refund, search_policy]


def run_turn(contents: list, customer_id: int, max_steps: int = 6) -> str:
    tool_list = make_tools(customer_id)
    registry = {}
    for f in tool_list:
        registry[f.__name__] = f
    system = SYSTEM + f"\nThe logged-in customer id is {customer_id}."

    for step in range(max_steps):
        resp = gemini_step(contents, system, tool_list)
        content = resp.candidates[0].content
        contents.append(content)

        calls = []
        for part in (content.parts or []):
            if part.function_call:
                calls.append(part.function_call)
        if not calls:
            return resp.text or "(empty reply)"

        results = []
        for call in calls:
            args = {}
            for key, value in dict(call.args or {}).items():
                if key.endswith("_id") and isinstance(value, float) and value.is_integer():
                    value = int(value)
                args[key] = value
            print(f"  [tool] {call.name}({args})")

            fn = registry.get(call.name)
            try:
                out = fn(**args) if fn else {"ok": False, "error": "unknown_tool"}
            except Exception as e:
                out = {"ok": False, "error": "tool_exception", "message": str(e)}
            print(f"  [result] {out}")
            results.append(types.Part.from_function_response(name=call.name, response=out))
        contents.append(types.Content(role="user", parts=results))

    return "Sorry, request process nahi ho paayi (too many steps). Please dobara try karein."


if __name__ == "__main__":
    customer_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Agent ready (customer {customer_id}). Exit ke liye 'q'.\n")
    history = []
    while True:
        q = input("You: ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        if not q:
            continue
        history.append(types.Content(role="user", parts=[types.Part.from_text(text=q)]))
        try:
            print(f"\nAgent: {run_turn(history, customer_id)}\n")
        except Exception as e:
            print(f"\n[ERROR] {str(e)[:200]}\n")