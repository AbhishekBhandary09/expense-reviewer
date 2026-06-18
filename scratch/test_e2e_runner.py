import asyncio
import os
import uuid
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.expense_graph import expense_workflow, WorkflowInput, ExpensePayload

async def main():
    os.environ["ADK_OTEL_TO_CLOUD"] = "false"
    
    session_service = InMemorySessionService()
    runner = Runner(
        agent=expense_workflow,
        app_name="expense-reviewer",
        session_service=session_service,
        auto_create_session=True
    )

    # Test Case 1: Low amount ($50) -> Should auto-approve
    print("--- Test Case 1: Low Amount ($50) ---")
    session_id_1 = str(uuid.uuid4())
    input_data_1 = WorkflowInput(
        data=ExpensePayload(amount=50.0, description="Team coffee chat", submitter="Alice")
    )
    new_message_1 = types.Content(
        role="user",
        parts=[types.Part.from_text(text=input_data_1.model_dump_json())]
    )
    
    async for event in runner.run_async(
        user_id="user_1",
        session_id=session_id_1,
        new_message=new_message_1
    ):
        if event.output is not None:
            output = event.output
            status = output.get("status") if isinstance(output, dict) else getattr(output, "status", None)
            print(f"Workflow finished! Final status: {status}")

    # Test Case 2: High amount ($150) -> Should pause for human review (yield RequestInput)
    print("\n--- Test Case 2: High Amount ($150) ---")
    session_id_2 = str(uuid.uuid4())
    input_data_2 = WorkflowInput(
        data=ExpensePayload(amount=150.0, description="Standard business lunch", submitter="Bob")
    )
    new_message_2 = types.Content(
        role="user",
        parts=[types.Part.from_text(text=input_data_2.model_dump_json())]
    )
    
    interrupted = False
    interrupt_id = None
    async for event in runner.run_async(
        user_id="user_2",
        session_id=session_id_2,
        new_message=new_message_2
    ):
        # Detect RequestInput
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call and part.function_call.name == "adk_request_input":
                    interrupt_id = part.function_call.id
                    print(f"Workflow paused! RequestInput detected: {part.function_call.args['message']}")
                    interrupted = True

    # If interrupted, simulate resuming the workflow with approval
    if interrupted and interrupt_id:
        print("\nResuming Workflow with 'approve' decision...")
        
        # Build the FunctionResponse part
        part = types.Part(
            function_response=types.FunctionResponse(
                id=interrupt_id,
                name="adk_request_input",
                response={"decision": "approve"}
            )
        )
        resume_message = types.Content(
            role="user",
            parts=[part]
        )
        
        async for event in runner.run_async(
            user_id="user_2",
            session_id=session_id_2,
            new_message=resume_message
        ):
            if event.output is not None:
                output = event.output
                status = output.get("status") if isinstance(output, dict) else getattr(output, "status", None)
                print(f"Resumed workflow finished! Final status: {status}")

if __name__ == "__main__":
    asyncio.run(main())
