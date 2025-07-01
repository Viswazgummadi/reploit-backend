# backend/app/ai_core/agent.py

from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from .tools import all_tools # Import the tools we created

# --- 1. Define the State for our Graph ---
# This is the "memory" of our agent. It's what gets passed between each step (node).
class AgentState(TypedDict):
    # The list of messages in the conversation
    messages: Annotated[Sequence[BaseMessage], operator.add]
    # The data_source_id of the repository we are analyzing
    data_source_id: str

# --- 2. Define the Nodes of our Graph ---
# Each node is a function that takes the current state and returns a modified state.

def tool_router(state: AgentState):
    """
    This node acts as the "brain" of the agent. It decides which tool to call, if any.
    """
    # We use a powerful feature of LangChain called "tool calling".
    # We bind our tools to the LLM, and it will generate a structured response
    # telling us which tool to use and what arguments to pass it.
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    
    # We create a version of the LLM that "knows" about our tools.
    llm_with_tools = llm.bind_tools(all_tools)
    
    # The last message is the user's query.
    query = state["messages"][-1]
    
    # We call the LLM, and it will decide if a tool call is necessary.
    ai_response = llm_with_tools.invoke([query])
    
    # The response might contain a tool call. If so, we add it to our message list.
    # The LangGraph engine will see this special "tool_calls" message and know
    # that it needs to execute a tool next.
    return {"messages": [ai_response]}


def tool_executor(state: AgentState):
    """
    This node is responsible for actually running the tools.
    """
    # The last message from the 'tool_router' will be an AIMessage with tool_calls.
    last_message = state["messages"][-1]
    
    # We extract the tool call information.
    tool_call = last_message.tool_calls[0]
    
    # Find the corresponding tool from our list of all_tools.
    selected_tool = {t.name: t for t in all_tools}[tool_call["name"]]
    
    # Get the arguments for the tool, and importantly, add the data_source_id from our state.
    tool_args = tool_call["args"]
    tool_args["data_source_id"] = state["data_source_id"]

    # Call the tool with the correct arguments.
    response = selected_tool.invoke(tool_args)

    # We need to return the response in a special ToolMessage format.
    # The LangGraph engine understands this and knows the tool has been run.
    from langchain_core.messages import ToolMessage
    return {"messages": [ToolMessage(content=str(response), tool_call_id=tool_call["id"])]}

# --- 3. Define the Logic for Conditional Edges ---
# This function decides where to go next after a node has finished.

def should_continue(state: AgentState):
    """
    This function decides the next step after the LLM has been called.
    - If the LLM's response included a tool call, we go to the 'tool_executor' node.
    - If the LLM responded directly without a tool call, the conversation is over, so we go to the END.
    """
    if "tool_calls" in state["messages"][-1].additional_kwargs:
        # The LLM wants to use a tool.
        return "use_tool"
    else:
        # The LLM has given a final answer.
        return END

# --- 4. Assemble the Graph ---

# We create a new graph and define our agent's state object.
graph_builder = StateGraph(AgentState)

# Add our nodes to the graph.
graph_builder.add_node("router", tool_router)
graph_builder.add_node("tool_executor", tool_executor)

# Set the entry point for the graph.
graph_builder.set_entry_point("router")

# Add the conditional edge. After the 'router' runs, call the 'should_continue' function
# to decide whether to go to 'tool_executor' or to the 'END'.
graph_builder.add_conditional_edges(
    "router",
    should_continue,
    {
        "use_tool": "tool_executor",
        END: END
    }
)

# After the 'tool_executor' runs, it should always go back to the 'router'
# to evaluate the new information and decide on the next step.
graph_builder.add_edge("tool_executor", "router")

# Compile the graph into a runnable object.
agent_graph = graph_builder.compile()

# --- To make it easier to see what's happening, you can visualize the graph ---
from IPython.display import Image
Image(agent_graph.get_graph().draw_png())