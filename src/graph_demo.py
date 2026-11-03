from typing import TypedDict

from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    question: str
    kind: str
    answer: str


def classify(state):
    q = state["question"].lower()
    if "order" in q:
        return {"kind": "order"}
    return {"kind": "policy"}


def order_step(state):
    return {"answer": "order wala step chala"}


def policy_step(state):
    return {"answer": "policy wala step chala"}


def pick_next(state):
    # conditional edge: ye function next node ka naam batata hai
    if state["kind"] == "order":
        return "order_step"
    return "policy_step"


graph = StateGraph(State)
graph.add_node("classify", classify)
graph.add_node("order_step", order_step)
graph.add_node("policy_step", policy_step)

graph.add_edge(START, "classify")
graph.add_conditional_edges("classify", pick_next, ["order_step", "policy_step"])
graph.add_edge("order_step", END)
graph.add_edge("policy_step", END)

app = graph.compile()

print(app.invoke({"question": "Order 1 ka status?"}))
print(app.invoke({"question": "Refund kitne din mein aata hai?"}))