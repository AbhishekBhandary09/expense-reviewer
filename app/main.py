import os
import base64
import json
import logging
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.expense_graph import expense_workflow, WorkflowInput, ExpensePayload

# 1. Setup standard python logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("expense_reviewer_ambient")

app = FastAPI(title="Ambient Expense Reviewer Service")

@app.get("/")
async def root():
    return {"status": "healthy", "service": "Ambient Expense Reviewer Service"}


# 2. Pub/Sub Request Payload Schemas
class PubSubMessage(BaseModel):
    data: Optional[str] = Field(None, description="Base64-encoded message data.")
    attributes: Optional[dict[str, str]] = Field(None, description="Message attributes.")
    messageId: Optional[str] = Field(None, description="Pub/Sub message ID.")
    publishTime: Optional[str] = Field(None, description="Publish timestamp.")

class PubSubTriggerRequest(BaseModel):
    message: PubSubMessage
    subscription: Optional[str] = Field(None, description="FQN subscription path.")

class TriggerResponse(BaseModel):
    status: str

# Create in-memory session service for the runner
session_service = InMemorySessionService()

async def process_trigger(app_name: str, req: PubSubTriggerRequest) -> TriggerResponse:
    # 1. Normalize the fully-qualified subscription path down to a short name
    subscription_path = req.subscription or "default-subscription"
    user_id = subscription_path.split("/")[-1]
    logger.info("Normalized subscription FQN '%s' to short name '%s'", subscription_path, user_id)
    
    # 2. Base64 decode message data
    if not req.message.data:
        raise HTTPException(status_code=400, detail="Missing message data field.")
        
    try:
        decoded_bytes = base64.b64decode(req.message.data)
        decoded_str = decoded_bytes.decode("utf-8")
        expense_data = json.loads(decoded_str)
    except Exception as e:
        logger.exception("Failed to decode base64 data payload")
        raise HTTPException(status_code=400, detail=f"Failed to decode base64 data: {e}")
        
    attributes = req.message.attributes or {}
    logger.info("Decoded Pub/Sub payload data: %s, attributes: %s", expense_data, attributes)
    
    # 3. Construct the WorkflowInput
    try:
        workflow_input = WorkflowInput(
            data=ExpensePayload(**expense_data),
            attributes=attributes
        )
    except Exception as e:
        logger.exception("Validation failed for input expense data")
        raise HTTPException(status_code=400, detail=f"Invalid expense data: {e}")
        
    # 4. Instantiate the ADK Runner
    # Developer checklist: Set otel_to_cloud=False
    os.environ["ADK_OTEL_TO_CLOUD"] = "false"
    runner = Runner(
        agent=expense_workflow,
        app_name=app_name,
        session_service=session_service,
        auto_create_session=True
    )
    
    session_id = str(uuid.uuid4())
    logger.info("Creating session %s for user (subscription) %s", session_id, user_id)
    
    # Create the Content representation of the input JSON
    new_message_str = workflow_input.model_dump_json()
    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=new_message_str)]
    )
    
    # 5. Feed into workflow
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message
        ):
            if event.output is not None:
                logger.info("Event output: %s", event.output)
            elif event.content:
                logger.info("Event content: %s", event.content)
    except Exception as e:
        logger.exception("Error during workflow execution")
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {e}")
        
    logger.info("Workflow completed successfully for session %s", session_id)
    return TriggerResponse(status="success")

@app.post("/trigger/pubsub", response_model=TriggerResponse)
async def post_trigger_pubsub(req: PubSubTriggerRequest):
    return await process_trigger("app", req)

@app.post("/apps/{app_name}/trigger/pubsub", response_model=TriggerResponse)
async def post_apps_trigger_pubsub(app_name: str, req: PubSubTriggerRequest):
    return await process_trigger(app_name, req)
