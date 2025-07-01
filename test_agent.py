# backend/test_agent.py

import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append('.')

from app import create_app
from app.ai_core.agent import agent_graph
from langchain_core.messages import HumanMessage

def run_agent_test():
    """
    A test harness to run the full LangGraph agent directly.
    """
    # --- !! CONFIGURATION !! ---
    # 1. Paste the ID you copied from your Supabase table here.
    TEST_DATA_SOURCE_ID = "09636f8d-a47d-49cc-bd91-7c0be48cc9de" # <-- PASTE YOUR ID HERE

    # 2. Choose ONE question to ask. Uncomment the one you want to test.
    #    Make sure the file/function names match what's in your repository.

    # A) Test the Knowledge Graph Tool
    USER_QUERY = "How many functions are defined in the file 'server.py'?"

    # B) Test the Vector DB Tool
    # USER_QUERY = "What part of the code handles sending chat messages?"

    # C) Test the File Reader Tool (requires the agent to first find the file)
    # USER_QUERY = "Show me the full source code for the 'handle_client' function in the 'server.py' file."
    # --- End Configuration ---

    if "09636f8d-a47d-49cc-bd91-7c0be48cc9de" in TEST_DATA_SOURCE_ID:
        print("🛑 STOP: Please edit `test_agent.py` and set TEST_DATA_SOURCE_ID to a real ID from your database.")
        return

    print(f"--- 🚀 Starting Agent Test ---")
    print(f"Query: '{USER_QUERY}'")
    print(f"Data Source ID: {TEST_DATA_SOURCE_ID}\n")

    initial_state = {
        "messages": [HumanMessage(content=USER_QUERY)],
        "data_source_id": TEST_DATA_SOURCE_ID
    }

    # The .stream() method lets us see each step of the agent's "thinking" process.
    event_stream = agent_graph.stream(initial_state)

    final_answer = ""
    print("--- Agent Execution Steps ---")
    for event in event_stream:
        for key, value in event.items():
            print(f"Node '{key}' finished. Current state:")
            # We are printing the 'messages' part of the state to see the conversation flow.
            print(value['messages'])
            print("---")

            # The final answer is the last message that is NOT a tool call.
            if key == "router":
                last_message = value["messages"][-1]
                if not last_message.tool_calls:
                    final_answer = last_message.content
    
    print("\n--- ✅ Agent Finished ---")
    print("Final Answer:")
    print(final_answer)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        run_agent_test()