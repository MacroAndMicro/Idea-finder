import os
import json
import subprocess
from supabase import create_client, Client
#from openai import OpenAI
from google import genai

# 1. Initialize Clients (expects environment variables to be set)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
llm = genai.GenerativeModel("gemini-pro")

def fetch_system_prompt(prompt_key: str) -> str:
    """Fetches the agent's operational system prompt from Supabase."""
    response = supabase.table("system_prompts").select("content").eq("key", prompt_key).execute()
    if response.data:
        return response.data[0]["content"]
    raise ValueError(f"System prompt '{prompt_key}' not found in Supabase.")

def fetch_agent_queue(assignee_name: str):
    """Fetches 'To Do' tickets assigned to this agent from the project_board."""
    response = supabase.table("project_board") \
        .select("*") \
        .eq("status", "To Do") \
        .eq("assignee", assignee_name) \
        .execute()
    return response.data

def log_agent_run(agent_name: str, summary: str, metrics: dict):
    """Writes the execution run report to Supabase."""
    supabase.table("agent_run_reports").insert({
        "agent": agent_name,
        "run_summary": summary,
        "metrics_json": metrics
    }).execute()

def execute_agent_loop(agent_name: str, prompt_key: str):
    print(f"--- Starting Autonomous Run for: {agent_name} ---")
    
    try:
        # Step 1: Read System Prompt & Queue
        system_prompt = fetch_system_prompt(prompt_key)
        queue = fetch_agent_queue(agent_name)
        
        print(f"Found {len(queue)} pending tickets in queue.")
        
        # Build context payload for the LLM
        user_context = f"""
        Here is your current active queue from the project_board:
        {json.dumps(queue, indent=2)}
        
        Analyze the top priority ticket, write the required code or changes, and return your output 
        in a strict JSON format containing:
        {{
            "ticket_id": <int>,
            "action": "CREATE_FILE" or "UPDATE_FILE",
            "file_path": "<path/to/file>",
            "file_content": "<full source code>",
            "commit_message": "<git commit message>",
            "run_summary": "<brief summary of actions taken>"
        }}
        """

        # Step 2: Call LLM (Reasoning Step)
        response = llm.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        print(f"Agent decided action for Ticket #{result.get('ticket_id')}: {result.get('action')}")

        # Step 3: Execute File Operations (Agent's Hands)
        file_path = result.get("file_path")
        file_content = result.get("file_content")
        
        if file_path and file_content:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write file locally
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"Successfully wrote code to {file_path}")
            
            # Step 4: Run basic verification/tests
            test_process = subprocess.run(["pytest"], capture_output=True, text=True)
            tests_passed = test_process.returncode == 0
            print(f"Test suite execution status: {'PASSED' / 'FAILED' if not tests_passed else 'PASSED'}")

            # Step 5: Log run report to Supabase
            log_agent_run(
                agent_name=agent_name,
                summary=result.get("run_summary"),
                metrics={
                    "ticket_id": result.get("ticket_id"),
                    "file_modified": file_path,
                    "tests_passed": tests_passed
                }
            )
            print(f"--- Run Completed Successfully for {agent_name} ---")

    except Exception as e:
        print(f"Error during agent execution: {str(e)}")
        log_agent_run(
            agent_name=agent_name,
            summary=f"Run failed with exception: {str(e)}",
            metrics={"status": "error"}
        )

if __name__ == "__main__":
    # Example: Run the Data & LLM Engineer agent cycle
    execute_agent_loop(
        agent_name="Data Engineer (agent)", 
        prompt_key="data_llm_engineer_agent_prompt"
    )