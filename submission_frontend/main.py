import os
import ssl
import urllib3
import warnings
import requests
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Disable SSL validation globally for any external calls in this process
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

original_request = requests.Session.request
def unverified_request(*args, **kwargs):
    kwargs['verify'] = False
    return original_request(*args, **kwargs)
requests.Session.request = unverified_request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

app = FastAPI(title="Manager Expense Approval Dashboard")

# HTML Content of the beautiful manager dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manager Expense Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            background-color: #080b11;
            color: #f1f5f9;
            font-family: 'Outfit', sans-serif;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.12) 0%, transparent 45%),
                radial-gradient(circle at 90% 80%, rgba(236, 72, 153, 0.1) 0%, transparent 45%);
            background-attachment: fixed;
            min-height: 100vh;
            overflow-x: hidden;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 24px 80px;
            background: rgba(8, 11, 17, 0.6);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .logo-section {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .logo-icon {
            color: #6366f1;
            filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.6));
        }
        .logo-text {
            font-size: 22px;
            font-weight: 600;
            letter-spacing: -0.5px;
            background: linear-gradient(to right, #ffffff, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status-badge {
            background: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.2);
            padding: 6px 14px;
            border-radius: 99px;
            font-size: 13px;
            font-weight: 500;
            color: #818cf8;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #34d399;
            box-shadow: 0 0 8px #34d399;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 0.5; }
            50% { opacity: 1; }
            100% { opacity: 0.5; }
        }
        main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 48px 80px;
        }
        .dashboard-header {
            margin-bottom: 40px;
        }
        .dashboard-title {
            font-size: 32px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .dashboard-subtitle {
            color: #94a3b8;
            font-size: 16px;
        }
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 30px;
        }
        .no-data {
            grid-column: 1 / -1;
            text-align: center;
            padding: 80px 20px;
            background: rgba(255, 255, 255, 0.01);
            border: 1px dashed rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            color: #64748b;
        }
        .no-data i {
            font-size: 48px;
            margin-bottom: 16px;
            color: #475569;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 20px;
            padding: 28px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        .glass-card:hover {
            transform: translateY(-5px);
            border-color: rgba(99, 102, 241, 0.25);
            box-shadow: 0 20px 40px -20px rgba(99, 102, 241, 0.3);
            background: rgba(255, 255, 255, 0.03);
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
        }
        .submitter-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 15px;
            color: white;
            text-transform: uppercase;
        }
        .submitter-details h4 {
            font-size: 16px;
            font-weight: 500;
            color: #f8fafc;
        }
        .submitter-details p {
            font-size: 13px;
            color: #64748b;
        }
        .amount-tag {
            font-size: 24px;
            font-weight: 600;
            color: #818cf8;
            background: rgba(99, 102, 241, 0.1);
            padding: 6px 14px;
            border-radius: 12px;
            border: 1px solid rgba(99, 102, 241, 0.15);
        }
        .card-body {
            margin-bottom: 24px;
        }
        .expense-desc {
            font-size: 16px;
            color: #cbd5e1;
            line-height: 1.5;
            margin-bottom: 16px;
        }
        .expense-meta {
            display: flex;
            gap: 20px;
            font-size: 13px;
            color: #64748b;
        }
        .meta-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .card-actions {
            display: flex;
            gap: 16px;
            margin-top: auto;
        }
        button {
            flex: 1;
            padding: 12px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s ease;
            position: relative;
        }
        .btn-approve {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            border: none;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
        }
        .btn-approve:hover {
            box-shadow: 0 4px 20px rgba(16, 185, 129, 0.4);
            transform: translateY(-1px);
        }
        .btn-reject {
            background: transparent;
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        .btn-reject:hover {
            background: rgba(239, 68, 68, 0.05);
            border-color: #ef4444;
        }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
        .spinner {
            width: 18px;
            height: 18px;
            border: 2.5px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 0.8s linear infinite;
            display: none;
        }
        .btn-reject .spinner {
            border-top-color: #ef4444;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        /* Side slide-out modal */
        .side-modal {
            position: fixed;
            top: 0;
            right: -500px;
            width: 500px;
            height: 100%;
            background: rgba(10, 14, 23, 0.95);
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            border-left: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: -20px 0 50px rgba(0, 0, 0, 0.8);
            transition: right 0.45s cubic-bezier(0.25, 0.8, 0.25, 1);
            z-index: 1000;
            padding: 40px;
            display: flex;
            flex-direction: column;
        }
        .side-modal.open {
            right: 0;
        }
        .modal-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            z-index: 999;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }
        .modal-backdrop.open {
            opacity: 1;
            pointer-events: auto;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }
        .modal-close {
            background: transparent;
            border: none;
            color: #94a3b8;
            cursor: pointer;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s ease;
        }
        .modal-close:hover {
            background: rgba(255, 255, 255, 0.05);
            color: white;
        }
        .modal-body {
            flex: 1;
            overflow-y: auto;
        }
        .result-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .result-badge {
            font-size: 14px;
            padding: 6px 14px;
            border-radius: 99px;
            font-weight: 500;
            text-transform: uppercase;
        }
        .badge-approved {
            background: rgba(16, 185, 129, 0.1);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        .badge-rejected {
            background: rgba(239, 68, 68, 0.1);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.2);
        }
        .summary-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .summary-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 14px;
        }
        .summary-row:last-child {
            margin-bottom: 0;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }
        .summary-label {
            color: #64748b;
        }
        .summary-value {
            color: #cbd5e1;
            font-weight: 500;
        }
        .agent-explanation {
            line-height: 1.6;
            color: #94a3b8;
            font-size: 15px;
            background: rgba(99, 102, 241, 0.05);
            border-left: 3px solid #6366f1;
            padding: 16px;
            border-radius: 0 12px 12px 0;
            margin-bottom: 24px;
        }
        .agent-explanation h5 {
            color: #818cf8;
            margin-bottom: 6px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-section">
            <i data-lucide="shield-check" class="logo-icon"></i>
            <span class="logo-text">Expense Compliance Portal</span>
        </div>
        <div class="status-badge">
            <div class="status-dot"></div>
            Agent Runtime Active
        </div>
    </header>

    <main>
        <div class="dashboard-header">
            <h1 class="dashboard-title">Pending Approvals</h1>
            <p class="dashboard-subtitle">Review, approve, or reject expenses that require manager override.</p>
        </div>

        <div class="cards-grid" id="cards-container">
            <div class="no-data">
                <i data-lucide="loader-2" class="spin"></i>
                <p>Loading pending approvals...</p>
            </div>
        </div>
    </main>

    <div class="modal-backdrop" id="backdrop" onclick="closeModal()"></div>
    <div class="side-modal" id="modal">
        <div class="modal-header">
            <h3 style="font-weight: 500; font-size: 18px; color: #94a3b8;">Review Complete</h3>
            <button class="modal-close" onclick="closeModal()">
                <i data-lucide="x"></i>
            </button>
        </div>
        <div class="modal-body" id="modal-content">
            <!-- Populated dynamically -->
        </div>
    </div>

    <script>
        // Initialize Lucide icons
        lucide.createIcons();

        async function fetchPending() {
            try {
                const response = await fetch('/api/pending');
                const data = await response.json();
                renderCards(data);
            } catch (error) {
                console.error("Error fetching data:", error);
                document.getElementById('cards-container').innerHTML = `
                    <div class="no-data" style="color: #ef4444;">
                        <i data-lucide="alert-triangle"></i>
                        <p>Error connecting to dashboard API.</p>
                    </div>
                `;
                lucide.createIcons();
            }
        }

        function renderCards(items) {
            const container = document.getElementById('cards-container');
            if (items.length === 0) {
                container.innerHTML = `
                    <div class="no-data">
                        <i data-lucide="check-circle" style="color: #10b981;"></i>
                        <p>All clear! No pending approvals found.</p>
                    </div>
                `;
                lucide.createIcons();
                return;
            }

            container.innerHTML = items.map(item => {
                const submitterInitials = item.expense.submitter ? item.expense.submitter.substring(0, 2) : "EX";
                return `
                    <div class="glass-card" id="card-${item.session_id}">
                        <div class="card-header">
                            <div class="submitter-info">
                                <div class="avatar">${submitterInitials}</div>
                                <div class="submitter-details">
                                    <h4>${item.expense.submitter || 'unknown'}</h4>
                                    <p>${item.expense.date || 'no date'}</p>
                                </div>
                            </div>
                            <div class="amount-tag">$${item.expense.amount.toFixed(2)}</div>
                        </div>
                        <div class="card-body">
                            <p class="expense-desc">"${item.expense.description}"</p>
                            <div class="expense-meta">
                                <div class="meta-item">
                                    <i data-lucide="tag" style="width:14px;height:14px;"></i>
                                    <span>${item.expense.category || 'meals'}</span>
                                </div>
                                <div class="meta-item">
                                    <i data-lucide="key-round" style="width:14px;height:14px;"></i>
                                    <span style="font-family:monospace; font-size: 11px;">${item.session_id.substring(0, 12)}...</span>
                                </div>
                            </div>
                        </div>
                        <div class="card-actions">
                            <button class="btn-reject" onclick="action('${item.session_id}', '${item.interrupt_id}', false, this)">
                                <span class="spinner"></span>
                                <span class="btn-text">Reject</span>
                            </button>
                            <button class="btn-approve" onclick="action('${item.session_id}', '${item.interrupt_id}', true, this)">
                                <span class="spinner"></span>
                                <span class="btn-text">Approve</span>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
            
            lucide.createIcons();
        }

        async function action(sessionId, interruptId, approved, button) {
            const card = document.getElementById(`card-${sessionId}`);
            const buttons = card.querySelectorAll('button');
            const spinner = button.querySelector('.spinner');
            const btnText = button.querySelector('.btn-text');

            // Disable buttons and show loading spinner
            buttons.forEach(btn => btn.disabled = true);
            spinner.style.display = 'block';
            btnText.style.display = 'none';

            try {
                const response = await fetch(`/api/action/${sessionId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        interrupt_id: interruptId,
                        approved: approved
                    })
                });

                if (!response.ok) {
                    throw new Error("Action request failed");
                }

                const result = await response.json();
                
                // Show slide out modal with the details
                showResultModal(result, sessionId, approved);
                
                // Remove card from list
                card.style.opacity = '0';
                card.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    card.remove();
                    // Refetch in case list is empty now
                    if (document.querySelectorAll('.glass-card').length === 0) {
                        fetchPending();
                    }
                }, 300);

            } catch (error) {
                console.error("Action error:", error);
                alert("Failed to process approval action.");
                // Reset buttons
                buttons.forEach(btn => btn.disabled = false);
                spinner.style.display = 'none';
                btnText.style.display = 'block';
            }
        }

        function showResultModal(result, sessionId, approved) {
            const modal = document.getElementById('modal');
            const backdrop = document.getElementById('backdrop');
            const content = document.getElementById('modal-content');
            
            const badgeClass = approved ? 'badge-approved' : 'badge-rejected';
            const badgeText = approved ? 'Approved' : 'Rejected';
            
            let explanationHtml = "";
            let amount = 0;
            let description = "N/A";
            
            if (result.final_state) {
                amount = result.final_state.amount || 0;
                description = result.final_state.description || "N/A";
                explanationHtml = `
                    <div class="agent-explanation">
                        <h5>Agent Compliance Review</h5>
                        <p>${result.final_state.flagged_reason || 'Compliance checks evaluated successfully.'}</p>
                    </div>
                `;
            } else {
                explanationHtml = `
                    <div class="agent-explanation">
                        <h5>Response Details</h5>
                        <pre style="font-family: monospace; font-size: 11px; white-space: pre-wrap; overflow-x: auto; color: #94a3b8; max-height: 200px;">${JSON.stringify(result, null, 2)}</pre>
                    </div>
                `;
            }

            content.innerHTML = `
                <div class="result-title">
                    <span class="result-badge ${badgeClass}">${badgeText}</span>
                    <span style="font-size: 18px; font-weight: 500;">Action Registered</span>
                </div>
                
                <div class="summary-card">
                    <div class="summary-row">
                        <span class="summary-label">Session ID</span>
                        <span class="summary-value" style="font-family: monospace; font-size: 12px;">${sessionId}</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Description</span>
                        <span class="summary-value">${description}</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Override Action</span>
                        <span class="summary-value" style="color: ${approved ? '#34d399' : '#f87171'}">${approved ? 'Manual Approval' : 'Manual Rejection'}</span>
                    </div>
                </div>

                ${explanationHtml}
            `;

            modal.classList.add('open');
            backdrop.classList.add('open');
            lucide.createIcons();
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('open');
            document.getElementById('backdrop').classList.remove('open');
        }

        // Poll pending approvals initially
        fetchPending();
    </script>
</body>
</html>
"""

class ActionPayload(BaseModel):
    interrupt_id: str
    approved: bool

def get_access_token():
    print("Getting OAuth2 access token...")
    import google.auth
    import google.auth.transport.requests
    credentials, project = google.auth.default()
    auth_request = google.auth.transport.requests.Request()
    credentials.refresh(auth_request)
    return credentials.token, project

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return HTMLResponse(content=HTML_TEMPLATE)

@app.get("/api/pending")
async def get_pending():
    project_id = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "project-694a0e03-fed9-4ed6-8a9"
    location = os.getenv("GCP_REGION") or "us-central1"
    agent_runtime_id = os.getenv("AGENT_RUNTIME_ID")
    
    if not agent_runtime_id or agent_runtime_id == "None":
        # Returns standard mock data to allow immediate validation & demonstration
        return [
            {
                "session_id": "mock-session-123",
                "interrupt_id": "human_approval_mock-session-123",
                "expense": {
                    "amount": 150.00,
                    "submitter": "alice@company.com",
                    "category": "meals",
                    "description": "Client dinner at high-end restaurant",
                    "date": "2026-06-19"
                }
            },
            {
                "session_id": "mock-session-456",
                "interrupt_id": "human_approval_mock-session-456",
                "expense": {
                    "amount": 1250.00,
                    "submitter": "bob@company.com",
                    "category": "travel",
                    "description": "Flight and lodging for annual convention",
                    "date": "2026-06-18"
                }
            }
        ]
        
    try:
        from google.adk.sessions import VertexAiSessionService
        session_service = VertexAiSessionService(
            project=project_id,
            location=location,
            agent_engine_id=agent_runtime_id
        )
        
        # List all sessions under application
        response = await session_service.list_sessions(app_name="app")
        pending_approvals = []
        
        for s in response.sessions:
            try:
                # Fetch full session with events
                full_session = await session_service.get_session(
                    app_name="app",
                    user_id=s.user_id,
                    session_id=s.id
                )
                
                if not full_session or not full_session.events:
                    continue
                    
                # Analyze event stream for unresolved adk_request_input
                calls = {}
                responses = set()
                
                for event in full_session.events:
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            # 1. Identify requests for input
                            if part.function_call and part.function_call.name == "adk_request_input":
                                args = part.function_call.args or {}
                                interrupt_id = args.get("id") or args.get("interrupt_id")
                                if interrupt_id:
                                    calls[interrupt_id] = {
                                        "interrupt_id": interrupt_id,
                                        "message": args.get("message", "Approval required.")
                                    }
                            # 2. Identify responses/overrides
                            if part.function_response and part.function_response.name == "adk_request_input":
                                resp_id = part.function_response.id
                                if resp_id:
                                    responses.add(resp_id)
                                    
                # Identify unresolved
                unresolved = [c for c_id, c in calls.items() if c_id not in responses]
                
                if unresolved:
                    state = full_session.state or {}
                    expense_data = state.get("data", {})
                    
                    for item in unresolved:
                        pending_approvals.append({
                            "session_id": s.id,
                            "interrupt_id": item["interrupt_id"],
                            "expense": {
                                "amount": state.get("amount") or expense_data.get("amount", 0.0),
                                "submitter": expense_data.get("submitter") or s.user_id,
                                "category": expense_data.get("category", "unknown"),
                                "description": state.get("description") or expense_data.get("description", "No description"),
                                "date": expense_data.get("date", "")
                            }
                        })
            except Exception as inner_e:
                print(f"Error checking session {s.id}: {inner_e}")
                
        return pending_approvals
        
    except Exception as e:
        print(f"Error listing session history: {e}")
        return []

@app.post("/api/action/{session_id}")
async def take_action(session_id: str, payload: ActionPayload):
    project_id = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "project-694a0e03-fed9-4ed6-8a9"
    location = os.getenv("GCP_REGION") or "us-central1"
    agent_runtime_id = os.getenv("AGENT_RUNTIME_ID")
    
    if not agent_runtime_id or agent_runtime_id == "None":
        # Mock action response
        decision = "approved" if payload.approved else "rejected"
        return {
            "status": "success",
            "decision": decision,
            "final_state": {
                "amount": 150.00 if "123" in session_id else 1250.00,
                "status": decision,
                "flagged_reason": f"Human manager manually {decision} the expense.",
                "description": "Client dinner at high-end restaurant" if "123" in session_id else "Flight and lodging for annual convention"
            }
        }
        
    try:
        # Obtain refreshed OAuth access token
        token, default_project = get_access_token()
        
        decision_str = "approve" if payload.approved else "reject"
        
        # Invoke Reasoning Engine REST API directly to resume the paused session on Agent Runtime.
        # This completely removes the dependency on the heavy google-cloud-aiplatform library,
        # allowing fast Vercel deployments well within standard resource limits.
        url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/reasoningEngines/{agent_runtime_id}:query"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        req_body = {
            "input": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "id": payload.interrupt_id,
                                "name": "adk_request_input",
                                "response": {
                                    "decision": decision_str,
                                    "approved": payload.approved
                                }
                            }
                        }
                    ]
                },
                "user_id": "default-user",
                "session_id": session_id
            }
        }
        
        res = requests.post(url, headers=headers, json=req_body)
        if res.status_code != 200:
            print(f"Error from Reasoning Engine API: {res.status_code} - {res.text}")
            raise HTTPException(status_code=res.status_code, detail=res.text)
            
        response_data = res.json()
        print(f"Reasoning Engine response: {response_data}")
        output = response_data.get("output", {})
        
        # Try to parse final state if returned
        final_state = {}
        if isinstance(output, dict):
            final_state = output.get("state", {})
            
        return {
            "status": "success",
            "decision": "approved" if payload.approved else "rejected",
            "final_state": final_state or {
                "status": "approved" if payload.approved else "rejected",
                "flagged_reason": f"Manual action '{decision_str}' registered in history."
            }
        }
        
    except Exception as e:
        print(f"Error invoking remote reasoning engine for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
