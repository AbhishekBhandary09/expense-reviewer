import os
import json
import uuid
import asyncio
import sys
from typing import Any, List
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.expense_graph import expense_workflow

# Ensure Python path includes the workspace root and app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../app")))

def to_agent_event(event) -> dict:
    author = event.author
    if not author:
        author = "user" if event.content and event.content.role == "user" else "model"
        
    content_dict = {"parts": []}
    if event.content:
        content_dict["role"] = event.content.role or "user"
        for part in event.content.parts or []:
            part_dict = {}
            if part.text is not None:
                part_dict["text"] = part.text
            elif part.function_call:
                part_dict["function_call"] = {
                    "name": part.function_call.name,
                    "args": part.function_call.args,
                    "id": part.function_call.id
                }
            elif part.function_response:
                part_dict["function_response"] = {
                    "name": part.function_response.name,
                    "response": part.function_response.response,
                    "id": part.function_response.id
                }
            content_dict["parts"].append(part_dict)
            
    return {
        "author": author,
        "content": content_dict
    }

def group_events_to_turns(events) -> List[dict]:
    turns = []
    current_turn_events = []
    turn_index = 0
    
    for event in events:
        # If this is a user-bearing event and we already have events, split the turn
        if event.content and event.content.role == "user" and current_turn_events:
            turns.append({
                "turn_index": turn_index,
                "events": current_turn_events
            })
            current_turn_events = []
            turn_index += 1
            
        current_turn_events.append(to_agent_event(event))
        
    if current_turn_events:
        turns.append({
            "turn_index": turn_index,
            "events": current_turn_events
        })
        
    return turns

async def evaluate_case(case: dict) -> dict:
    case_id = case["eval_case_id"]
    prompt_text = case["prompt"]["parts"][0]["text"]
    
    print(f"Running scenario: {case_id}...")
    
    session_service = InMemorySessionService()
    os.environ["ADK_OTEL_TO_CLOUD"] = "false"
    
    runner = Runner(
        agent=expense_workflow,
        app_name="app",
        session_service=session_service,
        auto_create_session=True
    )
    
    session_id = f"eval-{case_id}-{uuid.uuid4()}"
    user_id = "eval-user"
    
    # Run Turn 0
    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt_text)]
    )
    
    first_run_events = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message
    ):
        first_run_events.append(event)
        
    # Check for human review interruption
    interrupt_id = None
    for event in first_run_events:
        if event.long_running_tool_ids:
            interrupt_id = list(event.long_running_tool_ids)[0]
            break
            
    # Resume if interrupted
    if interrupt_id:
        # Automate decision: Reject prompt injections, approve clean requests
        if "ignore" in prompt_text.lower() or "bypass" in prompt_text.lower():
            decision = "reject"
            print(f"  [HITL] Intercepted. Auto-rejected injection attempt.")
        else:
            decision = "approve"
            print(f"  [HITL] Intercepted. Auto-approved clean request.")
            
        resume_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name="request_input",
                        id=interrupt_id,
                        response={"decision": decision}
                    )
                )
            ]
        )
        
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=resume_message
        ):
            pass
            
    # Retrieve all events
    session = await session_service.get_session(
        app_name="app",
        user_id=user_id,
        session_id=session_id
    )
    
    turns = group_events_to_turns(session.events)
    
    # Extract description from final state
    final_desc = ""
    if session.state:
        if hasattr(session.state, "description"):
            final_desc = session.state.description
        elif isinstance(session.state, dict):
            final_desc = session.state.get("description", "")
            
    # Construct output case result
    return {
        "eval_case_id": case_id,
        "prompt": {
            "role": "user",
            "parts": [{"text": prompt_text}]
        },
        "responses": [
            {
                "response": {
                    "role": "model",
                    "parts": [{"text": final_desc or "Done"}]
                }
            }
        ],
        "agent_data": {
            "agents": {
                "expense_reviewer_workflow": {
                    "agent_id": "expense_reviewer_workflow",
                    "instruction": "Expense reviewer workflow agent"
                }
            },
            "turns": turns
        }
    }

async def main():
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "datasets/basic-dataset.json"))
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../artifacts/traces"))
    output_path = os.path.join(output_dir, "generated_traces.json")
    
    os.makedirs(output_dir, exist_ok=True)
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    results = []
    for case in dataset["eval_cases"]:
        res_case = await evaluate_case(case)
        results.append(res_case)
        
    output_dataset = {"eval_cases": results}
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_dataset, f, indent=2)
        
    print(f"\nSuccessfully generated and saved traces to: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
