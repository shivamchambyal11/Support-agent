import json
import os
import sys
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

from agent import SYSTEM, make_tools
from llm import _retry

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


@lru_cache(maxsize=1)
def _client():
    return OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
        timeout=30,
    )


def _fn(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


ORDER_ID = {"type": "integer", "description": "The order id"}
DAMAGED = {"type": "boolean", "description": "true only if the customer says the item is damaged or wrong"}

SCHEMAS = [
    _fn("get_order", "Get status, total, delivery date and items of one of the customer's orders.",
        {"order_id": ORDER_ID}, ["order_id"]),
    _fn("check_return_eligibility", "Check whether a delivered order can still be returned under policy.",
        {"order_id": ORDER_ID, "damaged": DAMAGED}, ["order_id", "damaged"]),
    _fn("cancel_order", "Cancel an order. Works only for 'placed' orders. Needs customer confirmation first.",
        {"order_id": ORDER_ID}, ["order_id"]),
    _fn("initiate_refund", "Start a refund for a returned order. Needs customer confirmation first.",
        {"order_id": ORDER_ID, "amount": {"type": "number", "description": "Refund amount in Rs"},
         "damaged": DAMAGED}, ["order_id", "amount", "damaged"]),
]


def run_turn(messages: list, customer_id: int, max_steps: int = 6) -> str:
    registry = {f.__name__: f for f in make_tools(customer_id)}
    system = SYSTEM + f"\nThe logged-in customer id is {customer_id}."

    for _ in range(max_steps):
        resp = _retry(lambda: _client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system}] + messages,
            tools=SCHEMAS,
            tool_choice="auto",
        ))
        msg = resp.choices[0].message

        entry = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]
        messages.append(entry)

        if not msg.tool_calls:
            return msg.content or "(empty reply)"

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"  [tool] {tc.function.name}({args})")
            fn = registry.get(tc.function.name)
            try:
                out = fn(**args) if fn else {"ok": False, "error": "unknown_tool"}
            except Exception as e:  # galat args pe bhi crash nahi
                out = {"ok": False, "error": "tool_exception", "message": str(e)}
            print(f"  [result] {out}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out)})

    return "Sorry, request process nahi ho paayi (too many steps). Please dobara try karein."


if __name__ == "__main__":
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Agent (Groq: {MODEL}) ready, customer {cid}. Exit ke liye 'q'.\n")
    history: list = []
    while True:
        q = input("You: ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        if not q:
            continue
        history.append({"role": "user", "content": q})
        try:
            print(f"\nAgent: {run_turn(history, cid)}\n")
        except Exception as e:
            print(f"\n[ERROR] {str(e)[:200]}\n")