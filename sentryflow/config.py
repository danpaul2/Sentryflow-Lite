# ==============================
# config.py
# ==============================

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "yourpassword"),
    "database": os.getenv("DB_NAME", "sentryflow"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": False,
    "pool_name": "sentryflow_pool",
    "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
    "pool_reset_session": True
}

# Risk Thresholds
DEFAULT_MAX_RISK = int(os.getenv("DEFAULT_MAX_RISK", "50"))
HIGH_RISK_THRESHOLD = int(os.getenv("HIGH_RISK_THRESHOLD", "70"))
CRITICAL_RISK_THRESHOLD = int(os.getenv("CRITICAL_RISK_THRESHOLD", "90"))

# Risk Scoring Weights
RISK_WEIGHTS = {
    "structural": 50,
    "suspicious": 30,
    "judge": 40,
    "role_violation": 40,
    "prompt_injection": 35,
    "data_exfiltration": 45
}

# Authentication / Passwords
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "sentryflow-lite-default-salt")

# Logging Configuration
LOG_FILE = os.getenv("LOG_FILE", "sentryflow.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Streamlit / App Identity
APP_TITLE = "SentryFlow Lite - Agent Tool Guardrail"
APP_ICON = "SFL"
APP_TAGLINE = (
    "Middleware that intercepts agent tool calls and checks them "
    "against the original user request before anything runs."
)
PAGE_CONFIG = {
    "page_title": APP_TITLE,
    "page_icon": APP_ICON,
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Cache Configuration
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"

# Suspicious Patterns (moved from guardrail.py for centralized config)
SUSPICIOUS_PATTERNS = [
    # Destructive actions
    "delete", "drop", "truncate", "shutdown", "remove", "destroy",
    # Security sensitive
    "password", "credentials", "secret", "token", "api_key", "private_key",
    "admin access", "sudo", "root", "privilege",
    # Data exfiltration
    "download all", "export database", "dump", "extract all",
    # Injection attempts
    "'; drop", "union select", "exec(", "eval(", "__import__",
    # System manipulation
    "os.system", "subprocess", "shell", "execute", "run command"
]

# Tool Schemas for validation
TOOL_SCHEMAS = {
    "send_email": {
        "required": ["to", "subject", "body"],
        "optional": ["cc", "bcc", "attachments"],
        "types": {
            "to": str,
            "subject": str,
            "body": str,
            "cc": list,
            "bcc": list,
            "attachments": list
        }
    },
    "search_web": {
        "required": ["query"],
        "optional": ["max_results", "filter"],
        "types": {
            "query": str,
            "max_results": int,
            "filter": dict
        }
    },
    "create_report": {
        "required": ["title", "content"],
        "optional": ["format", "recipients"],
        "types": {
            "title": str,
            "content": str,
            "format": str,
            "recipients": list
        }
    },
    "database_query": {
        "required": ["query"],
        "optional": ["parameters"],
        "types": {
            "query": str,
            "parameters": list
        }
    }
}

# Rate Limiting
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

# Feature Flags
ENABLE_AI_JUDGE = os.getenv("ENABLE_AI_JUDGE", "false").lower() == "true"
ENABLE_SEMANTIC_ANALYSIS = os.getenv("ENABLE_SEMANTIC_ANALYSIS", "false").lower() == "true"
ENABLE_AUDIT_LOG = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"

TOOL_POLICIES = {

    "send_email": {
        "allowed_domains": ["company.com"],
        "max_recipients": 5,
        "allow_external": False
    },

    "query_database": {
        "allowed_tables": [
            "employees",
            "projects",
            "departments"
        ],
        "blocked_keywords": [
            "password",
            "ssn",
            "credit_card"
        ],
        "max_rows": 100
    }

}
