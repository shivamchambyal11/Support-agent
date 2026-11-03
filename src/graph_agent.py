import json
import os
import sys
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from agent import SYSTEM, make_tools

load_dotenv()

WRITE_TOOLS = ["cancel_order", "initiate_refund"]

# approval ab code mein hota hai, to model se confirm poochne ko mana karo
GRAPH_SYSTEM = SYSTEM.replace(
    "- Before cancelling an order or initiating a refund, ask the customer to confirm and wait for a clear 'yes'.",
    "- When the customer clearly asks to cancel an order or get a refund, call the tool directly. The system asks the customer for approval by itself.",
)


def build_app(customer_id):
    tool_list = make_tools(customer_id)
    llm = ChatGroq(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
                   temperature=0, max_retries=3, timeout=30)
    llm_with_tools = llm.bind_tools(tool_list)
    system = GRAPH_SYSTEM + f"\nThe logged-in customer id is {customer_id}."

    def agent(state: MessagesState):
        messages = [SystemMessage(content=system)] + state["messages"]
        reply = llm_with_tools.invoke(messages)
        return {"messages": [reply]}

    def after_agent(state: MessagesState):
        last = state["messages"][-1]
        if not last.tool_calls:
            return END
        for call in last.tool_calls:
            if call["name"] in WRITE_TOOLS:
                return "approval"
        return "tools"

    def approval(state: MessagesState) -> Command[Literal["tools", "agent"]]:
        last = state["messages"][-1]
        pending = []
        for call in last.tool_calls:
            if call["name"] in WRITE_TOOLS:
                pending.append({"tool": call["name"], "args": call["args"]})

        answer = interrupt({"pending": pending})   # yahan graph ruk jata hai

        if answer in ("yes", "y", "haan"):
            return Command(goto="tools")

        declined = []
        for call in last.tool_calls:
            result = {"ok": False, "error": "declined_by_customer",
                      "message": "The customer did not approve this action"}
            declined.append(ToolMessage(content=json.dumps(result), tool_call_id=call["id"]))
        return Command(goto="agent", update={"messages": declined})

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tool_list))
    graph.add_node("approval", approval)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", after_agent, ["approval", "tools", END])
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())


def ask(app, config, text):
    result = app.invoke({"messages": [("user", text)]}, config)

    # graph approval ke liye ruka hai to poochho aur resume karo
    while app.get_state(config).next:
        snapshot = app.get_state(config)
        pending = snapshot.tasks[0].interrupts[0].value["pending"]
        print("\n  APPROVAL CHAHIYE:")
        for item in pending:
            print("   ", item["tool"], item["args"])
        answer = input("  Approve? (yes/no): ").strip().lower()
        result = app.invoke(Command(resume=answer), config)

    return result["messages"][-1].content


if __name__ == "__main__":
    customer_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    app = build_app(customer_id)
    config = {"configurable": {"thread_id": f"customer-{customer_id}"}}
    print(f"Graph agent ready (customer {customer_id}). Exit ke liye 'q'.\n")
    while True:
        q = input("You: ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        if not q:
            continue
        try:
            print(f"\nAgent: {ask(app, config, q)}\n")
        except Exception as e:
            print(f"\n[ERROR] {str(e)[:200]}\n")