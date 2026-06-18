import re
from typing import Optional
from pydantic import BaseModel, Field
from google.adk.workflow import Workflow, START, node, Edge
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.agents import LlmAgent

# 1. State and IO Schemas
class ExpensePayload(BaseModel):
    amount: float = 0.0
    submitter: str = ""
    category: str = ""
    description: str = ""
    date: str = ""

class WorkflowInput(BaseModel):
    data: ExpensePayload = Field(default_factory=ExpensePayload)
    attributes: dict[str, str] = Field(default_factory=dict)

class ExpenseState(BaseModel):
    data: ExpensePayload = Field(default_factory=ExpensePayload)
    attributes: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    original_description: str = ""
    amount: float = 0.0
    redacted_categories: list[str] = Field(default_factory=list)
    is_security_event: bool = False
    flagged_reason: str = ""
    status: str = "pending"

class LlmReviewOutput(BaseModel):
    decision: str = Field(description="Must be 'approved' or 'needs_approval'")
    reason: str = Field(description="Reason for the decision")

# 2. Regular Expressions for PII Detection
SSN_REGEX = re.compile(r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b')
CREDIT_CARD_REGEX = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b|\b(?:\d[ -]*?){13,16}\b')

# Prompt Injection Keywords
INJECTION_KEYWORDS = [
    "ignore all previous instructions",
    "ignore instructions",
    "bypass rules",
    "auto-approve",
    "approve this expense",
    "force approval",
    "system override",
    "ignore policy",
    "ignore guidelines",
    "you must approve"
]

# 3. Graph Nodes

@node
def check_amount(ctx: Context, node_input: WorkflowInput) -> Event:
    """Check if the expense amount is low (< 100) or high (>= 100)."""
    payload = node_input.data
    amount = payload.amount
    description = payload.description
    
    state_delta = {
        "data": payload.model_dump(),
        "attributes": node_input.attributes,
        "amount": amount,
        "description": description,
        "original_description": description,
        "status": "pending"
    }
    
    next_state = ExpenseState(
        data=payload,
        attributes=node_input.attributes,
        amount=amount,
        description=description,
        original_description=description,
        status="pending"
    )
    
    route = "low_amount" if amount < 100.0 else "high_amount"
    return Event(output=next_state, route=route, state=state_delta)

@node
def security_checkpoint(ctx: Context, node_input: ExpenseState) -> Event:
    """Scrub PII (SSNs and CCs) and check for prompt injection."""
    description = node_input.description
    redacted_categories = []
    
    # Scrub SSN
    if SSN_REGEX.search(description):
        description = SSN_REGEX.sub("[SSN_REDACTED]", description)
        redacted_categories.append("ssn")
        
    # Scrub Credit Card
    if CREDIT_CARD_REGEX.search(description):
        description = CREDIT_CARD_REGEX.sub("[CREDIT_CARD_REDACTED]", description)
        redacted_categories.append("credit_card")
        
    # Detect Prompt Injection
    is_suspicious = False
    desc_lower = description.lower()
    for kw in INJECTION_KEYWORDS:
        if kw in desc_lower:
            is_suspicious = True
            break
            
    if is_suspicious:
        # Route directly to human review, bypass the LLM entirely, and flag security event.
        updated_state = ExpenseState(
            description=description,
            original_description=node_input.description,
            amount=node_input.amount,
            redacted_categories=redacted_categories,
            is_security_event=True,
            flagged_reason="Possible prompt injection attempt detected.",
            status="flagged_for_human_review"
        )
        return Event(
            output=updated_state,
            route="suspicious",
            state=updated_state.model_dump()
        )
        
    # Clean expense, proceed to LLM reviewer
    updated_state = ExpenseState(
        description=description,
        original_description=node_input.description,
        amount=node_input.amount,
        redacted_categories=redacted_categories,
        is_security_event=False,
        status="pending_llm_review"
    )
    return Event(
        output=updated_state,
        route="clean",
        state=updated_state.model_dump()
    )

# The LLM Reviewer Agent
real_llm_reviewer = LlmAgent(
    name="real_llm_reviewer",
    model="gemini-1.5-flash",
    instruction=(
        "You are an expense compliance reviewer. Review the expense description and decide "
        "if it complies with corporate policy. If it looks standard, approve it. "
        "Otherwise, route it for needs_approval."
    ),
    output_schema=LlmReviewOutput
)

@node(rerun_on_resume=True)
async def llm_reviewer(ctx: Context, node_input: ExpenseState) -> Event:
    """Wrapper node that executes LlmAgent and falls back to a mock if it fails."""
    try:
        res = await ctx.run_node(real_llm_reviewer, node_input=node_input.description)
        if hasattr(res, "model_dump"):
            res = res.model_dump()
        return Event(output=res)
    except Exception as e:
        mock_output = {
            "decision": "needs_approval",
            "reason": f"Mock review fallback (real review failed: {str(e)})"
        }
        return Event(output=mock_output)


# Route adapter to convert LLM output into the correct route ("approved" or "needs_approval")
@node
def route_llm_output(ctx: Context, node_input: dict) -> Event:
    decision = node_input.get("decision", "needs_approval")
    reason = node_input.get("reason", "Needs manual confirmation.")
    
    # Retrieve current state to preserve description, PII redaction data, etc.
    if hasattr(ctx.state, "to_dict"):
        state_dict = ctx.state.to_dict()
    elif hasattr(ctx.state, "copy"):
        state_dict = ctx.state.copy()
    else:
        state_dict = dict(ctx.state)
        
    state_dict["status"] = "approved" if decision == "approved" else "needs_approval"
    state_dict["flagged_reason"] = reason
    
    updated_state = ExpenseState(**state_dict)
    
    return Event(
        output=updated_state,
        route=decision,
        state=updated_state.model_dump()
    )

@node
def auto_approve(ctx: Context, node_input: ExpenseState) -> ExpenseState:
    """Auto-approve node."""
    node_input.status = "approved"
    return node_input

@node(rerun_on_resume=True)
async def review_agent(ctx: Context, node_input: ExpenseState):
    """Review agent node. Pauses to wait for human approval."""
    from google.adk.events.request_input import RequestInput
    interrupt_id = f"human_approval_{ctx.session.id}"
    if not ctx.resume_inputs or interrupt_id not in ctx.resume_inputs:
        yield RequestInput(
            interrupt_id=interrupt_id,
            message=f"Expense of ${node_input.amount} requires approval. Description: {node_input.description}"
        )
        return
        
    res = ctx.resume_inputs[interrupt_id]
    decision = res.get("decision", "reject") if isinstance(res, dict) else res
    node_input.status = "approved" if decision == "approve" else "rejected"
    yield Event(output=node_input, state={"status": node_input.status})

# 4. Workflow Definition
expense_workflow = Workflow(
    name="expense_reviewer_workflow",
    edges=[
        ('START', check_amount),
        (check_amount, {
            "low_amount": auto_approve,
            "high_amount": security_checkpoint
        }),
        (security_checkpoint, {
            "suspicious": review_agent,
            "clean": llm_reviewer
        }),
        (llm_reviewer, route_llm_output),
        Edge(from_node=route_llm_output, to_node=review_agent, route=["approved", "needs_approval"]),
    ],
    state_schema=ExpenseState,
    input_schema=WorkflowInput,
    output_schema=ExpenseState
)

from google.adk.apps import App
app = App(
    root_agent=expense_workflow,
    name="app"
)
