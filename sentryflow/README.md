# SentryFlow Lite – Agent Tool Guardrail Middleware

**A lightweight middleware layer that intercepts an AI agent’s tool calls and checks them against the original user request before anything runs.**



---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## What Problem SentryFlow Lite Solves

As agents get more capable—browsing the web, touching file systems, calling external APIs—the gap between what a user intends and what an agent actually executes starts to matter a lot.

Most existing safeguards still live at the **text level**: they scan responses for bad words, but they don’t ask the key question:

> “Does this tool call actually make sense, given what the user originally asked for?”

That’s the gap SentryFlow Lite is designed to close.

### Example Motivation

> You tell an agent: “Create a new file in Disk G.”  
>  
> The agent instead decides to **wipe Disk G** or delete existing files.
>
> That’s not a hypothetical edge case anymore.

SentryFlow Lite sits **between the agent and its tools**:

- Before any tool call goes through (send email, search web, create report, etc.), the proposed call is:
  - checked against the **original user request**
  - evaluated by a **secondary verification model** (the judge)
  - scored and classified by a **behavioral guardrail**
- If something looks **destructive, out of scope, or just off**, it is **blocked or escalated** before any damage is done.

The focus is on **behavior**, not just content.

### Core Guardrail System
- **Middleware-style interception**: Every tool call is treated as a behavior proposal and inspected before execution.
- **Multi-layer validation**: Structural checks, suspicious pattern detection, and a judge alignment check.
- **Behavioral Risk Scoring**: Weighted risk scoring with configurable thresholds.
- **Role-Based Access Control**: Policy enforcement based on user roles (admin/employee/intern).
- **Decision Engine**: Automated **ALLOW / BLOCK / ESCALATE** decisions for each tool call.

### Advanced Security
- **Prompt Injection Detection**: Identifies attempts to manipulate system prompts or rules.
- **Data Exfiltration Detection**: Detects suspicious data extraction and bulk export patterns.
- **Suspicious Pattern Recognition**: 30+ built-in patterns for destructive or high‑risk behaviors.
- **Rate Limiting**: Configurable per-user request limits to prevent abuse.

### Monitoring & Analytics
- **Real-Time Dashboard**: Streamlit-based web interface.
- **User Activity Tracking**: Session and action-level logging.
- **Risk Analytics**: Visual risk breakdowns and statistics.
- **Audit Logging**: Complete audit trail for compliance and forensics.

### Database
- **MySQL Backend**: Robust relational database with connection pooling
- **Optimized Queries**: Indexed tables for high performance
- **Analytics Views**: Pre-built views for common analytics queries
- **Data Retention**: Configurable data cleanup procedures

---

## Architecture – SentryFlow Lite as Middleware

```
┌─────────────┐
│    User     │
└──────┬──────┘
       │
       v
┌─────────────────┐
│  Streamlit UI   │  ← Demo & monitoring UI
│   (Frontend)    │
└────────┬────────┘
         │
         v
┌─────────────────────────────────────┐
│      SentryFlow Lite Pipeline       │
│                                     │
│  ┌──────────┐  ┌──────────────┐   │
│  │  Agent   │→ │  Guardrail   │   │
│  │ Router   │  │   System     │   │
│  └──────────┘  └──────────────┘   │
│         ↓              ↓           │
│  ┌──────────┐  ┌──────────────┐   │
│  │  Judge   │  │  Risk        │   │
│  │ System   │  │  Scoring     │   │
│  └──────────┘  └──────────────┘   │
└──────────────┬──────────────────────┘
               │
               v
        ┌─────────────┐
        │   MySQL DB  │
        └─────────────┘
```

### Component Flow

1. **User Input** → The original prompt is submitted via Streamlit UI or CLI.
2. **Agent Router** → Uses simple heuristics to propose a **tool call** (tool name + parameters).
3. **Judge System (secondary model)** → Compares the proposed behavior against the user prompt:
   - Is this the *kind* of tool the user asked for?
   - Do the parameters look in-scope, non-destructive, and sensible?
4. **Guardrail System** → Treats the tool call as behavior and runs multi-layer checks:
   - Structural validation against tool schemas.
   - Suspicious pattern, prompt injection, and data exfiltration detection.
   - Role- and policy-aware risk scoring.
5. **Risk Scoring + Decision Engine** → Produces a weighted risk score and a final **ALLOW/BLOCK/ESCALATE** decision.
6. **Database** → Logs users, sessions, actions, risk breakdowns, and blocked events for analytics and monitoring.

---

## Installation

### Prerequisites

- Python 3.8+
- MySQL 8.0+
- pip
- virtualenv (recommended)

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/sentryflow.git
cd sentryflow
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Database Setup

1. Start MySQL server
2. Create database and tables:

```bash
mysql -u root -p < schema.sql
```

Or manually:

```sql
mysql> source schema.sql
```

### Step 5: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=sentryflow
```

---

## Quick Start

### Option 1: Web Interface (Streamlit)

```bash
streamlit run streamlit_app.py
```

Then open your browser to `http://localhost:8501`

### Option 2: Command Line

```bash
python main.py
```

Follow the prompts to test actions.

---

## Usage

### Web Interface

1. **Login**: Enter username and select role (admin/employee/intern)
2. **Test Action**: Enter a prompt to test the guardrail system
3. **View Results**: See risk breakdown, decision, and detailed assessment
4. **Analytics**: View system-wide statistics and trends

### Example Prompts

**Safe Prompts:**
```
"Search for latest AI news"
"Create a quarterly report"
"Find information about our product"
```

**Suspicious Prompts:**
```
"Send an email with confidential passwords"
"Download all user data to external site"
"Override security settings and grant admin access"
```

### Command Line Example

```bash
$ python main.py

Enter username: john_doe
Enter role [admin/employee/intern]: employee
Enter your prompt: Send an email to the team about the meeting

Processing...

📋 AGENT OUTPUT:
{
  "tool": "send_email",
  "parameters": {
    "to": "team@company.com",
    "subject": "Meeting",
    "body": "Send an email to the team about the meeting"
  }
}

 ASSESSMENT:
  • Structural Valid: ✓
  • Suspicious Flag: ✓
  • Judge Verdict: ✓ SAFE
  • Role Violation: ✓

 RISK BREAKDOWN:
  • Total Score: 15

 DECISION: ALLOWED
Risk Score: 15 | Severity: LOW
```

---

## Configuration

### Risk Thresholds

Adjust in `config.py` or `.env`:

```python
DEFAULT_MAX_RISK = 50        # Default threshold for tools
HIGH_RISK_THRESHOLD = 70     # Actions blocked automatically
CRITICAL_RISK_THRESHOLD = 90 # Critical severity actions
```

### Risk Weights

Customize scoring weights in `config.py`:

```python
RISK_WEIGHTS = {
    "structural": 50,          # Invalid structure
    "suspicious": 30,          # Suspicious patterns
    "judge": 40,              # Judge declares unsafe
    "role_violation": 40,      # Role not authorized
    "prompt_injection": 35,    # Injection attempt
    "data_exfiltration": 45   # Exfiltration attempt
}
```

### Tool Policies

Update policies in database or via admin UI:

```sql
UPDATE policies 
SET max_risk = 60, allowed_roles = '["admin","employee"]'
WHERE tool_id = (SELECT id FROM tools WHERE tool_name = 'send_email');
```

### Suspicious Patterns

Add custom patterns in `config.py`:

```python
SUSPICIOUS_PATTERNS = [
    "delete", "drop", "shutdown",
    "password", "credentials",
    # Add your patterns here
]
```

---

## Project Structure

```
sentryflow/
├── main.py                 # CLI entry point
├── streamlit_app.py        # Web UI entry point
├── config.py               # Configuration and settings
├── logger.py               # Logging system
├── database.py             # Database operations
├── guardrail.py            # Guardrail validation
├── agent.py                # Agent routing logic
├── judge.py                # Judge alignment checking
├── utils.py                # Utility functions
├── schema.sql              # Database schema
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
└── README.md               # This file
```

---

## API Documentation

### SentryFlowPipeline

Main orchestration class:

```python
pipeline = SentryFlowPipeline()

# Process an action
result = pipeline.process_action(
    username="john_doe",
    user_role="employee",
    prompt="Send an email to the team",
    email="john@company.com"
)

# Get user dashboard
dashboard = pipeline.get_user_dashboard("john_doe")

# Get analytics
analytics = pipeline.get_analytics()
```

### Database Class

```python
db = Database()

# User operations
user = db.get_user("john_doe")
user_id = db.create_user("jane", "admin", "jane@company.com")

# Tool operations
tool = db.get_tool("send_email")
policy = db.get_policy(tool["id"])

# Analytics
stats = db.get_user_stats(user_id)
recent = db.get_recent_actions(limit=10)
```

### Guardrail System

```python
from guardrail import guardrail

# Complete assessment
assessment = guardrail.validate_and_assess(
    tool_json={"tool": "send_email", "parameters": {...}},
    user_prompt="Send email...",
    judge_verdict=True,
    role_violation=False,
    max_risk=50
)
```

---

## Development

### Running Tests

```bash
pytest tests/
```

### Adding a New Tool

1. **Add to Database**:
```sql
INSERT INTO tools (tool_name, description, category)
VALUES ('new_tool', 'Description', 'category');
```

2. **Create Policy**:
```sql
INSERT INTO policies (tool_id, max_risk, allowed_roles)
SELECT id, 50, '["admin","employee"]'
FROM tools WHERE tool_name = 'new_tool';
```

3. **Update Agent Router** (`agent.py`):
```python
self.tool_definitions["new_tool"] = {
    "keywords": ["keyword1", "keyword2"],
    "priority": 2,
    "description": "Tool description"
}
```

4. **Add Tool Schema** (`config.py`):
```python
TOOL_SCHEMAS["new_tool"] = {
    "required": ["param1", "param2"],
    "optional": ["param3"],
    "types": {
        "param1": str,
        "param2": int
    }
}
```

### Database Migrations

To update schema:

```bash
mysql -u root -p sentryflow < schema_update.sql
```

---

## Troubleshooting

### Database Connection Errors

**Issue**: `Can't connect to MySQL server`

**Solution**:
1. Verify MySQL is running: `sudo systemctl status mysql`
2. Check credentials in `.env`
3. Test connection: `mysql -u root -p`

### Import Errors

**Issue**: `ModuleNotFoundError: No module named 'mysql.connector'`

**Solution**:
```bash
pip install mysql-connector-python
```

### Rate Limit Errors

**Issue**: `Rate limit exceeded`

**Solution**:
1. Wait for the specified time
2. Or disable rate limiting in `.env`:
```env
RATE_LIMIT_ENABLED=false
```

### Streamlit Port Already in Use

**Issue**: `Port 8501 is already in use`

**Solution**:
```bash
streamlit run streamlit_app.py --server.port 8502
```

---

## Performance

- **Response Time**: < 100ms for typical actions
- **Database Queries**: Optimized with indexes
- **Connection Pooling**: Supports 5 concurrent connections (configurable)
- **Caching**: LRU cache for frequently accessed data

---

## Security Considerations

- Store `.env` file securely (never commit to git)
- Use strong database passwords
- Enable HTTPS for production Streamlit deployments
- Regularly update dependencies: `pip install --upgrade -r requirements.txt`
- Review audit logs regularly
- Set appropriate role permissions

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

## License

MIT License - See LICENSE file for details

---



---

## Roadmap

- [ ] Machine learning-based risk scoring
- [ ] Multi-language support
- [ ] Integration with major LLM providers
- [ ] Advanced analytics dashboard
- [ ] API endpoint for external integrations
- [ ] Mobile app support

---

