# ==============================
# utils.py
# ==============================

import json
import re
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from config import TOOL_SCHEMAS, PASSWORD_SALT
from logger import logger

def validate_json(data: Any) -> bool:
    """Validate if data is valid JSON serializable"""
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def hash_password(password: str) -> str:
    """Hash a password using a static salt and SHA-256."""
    if not isinstance(password, str):
        password = str(password)
    salted = (PASSWORD_SALT + password).encode("utf-8")
    return hashlib.sha256(salted).hexdigest()

def verify_password(password: str, expected_hash: str) -> bool:
    """Verify a password against a stored hash."""
    if not expected_hash:
        return False
    return hash_password(password) == expected_hash

def validate_tool_parameters(tool_name: str, parameters: Dict) -> tuple[bool, Optional[str]]:
    """
    Validate tool parameters against schema
    
    Returns:
        (is_valid, error_message)
    """
    if tool_name not in TOOL_SCHEMAS:
        return True, None  # No schema defined, assume valid
    
    schema = TOOL_SCHEMAS[tool_name]
    
    # Check required parameters
    for required_param in schema.get("required", []):
        if required_param not in parameters:
            return False, f"Missing required parameter: {required_param}"
    
    # Check parameter types
    for param_name, param_value in parameters.items():
        if param_name in schema.get("types", {}):
            expected_type = schema["types"][param_name]
            if not isinstance(param_value, expected_type):
                return False, f"Parameter '{param_name}' must be of type {expected_type.__name__}"
    
    return True, None

def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Sanitize and truncate string"""
    if not isinstance(text, str):
        text = str(text)
    
    # Remove potential SQL injection patterns
    text = re.sub(r'[;\'"\\]', '', text)
    
    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()

def format_timestamp(dt: datetime = None) -> str:
    """Format datetime as string"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse timestamp string to datetime"""
    try:
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error(f"Failed to parse timestamp: {timestamp_str}")
        return None

def calculate_percentage(value: int, total: int) -> float:
    """Calculate percentage safely"""
    if total == 0:
        return 0.0
    return round((value / total) * 100, 2)

def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text"""
    # Remove special characters and convert to lowercase
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
    
    # Split into words and filter
    words = [w for w in text.split() if len(w) >= min_length]
    
    # Remove common stop words
    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'this', 'that', 'with'}
    keywords = [w for w in words if w not in stop_words]
    
    return keywords

def detect_prompt_injection(text: str) -> tuple[bool, List[str]]:
    """
    Detect potential prompt injection attempts
    
    Returns:
        (is_suspicious, detected_patterns)
    """
    injection_patterns = [
        r'ignore (previous|all|above) (instructions|commands)',
        r'forget (everything|all|your) (instructions|rules)',
        r'system prompt',
        r'pretend (you are|to be)',
        r'act as (if|a)',
        r'disregard (your|the) (rules|guidelines)',
        r'override (your|the) (instructions|settings)',
        r'new (instructions|rules|system)',
    ]
    
    text_lower = text.lower()
    detected = []
    
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            detected.append(pattern)
    
    return len(detected) > 0, detected

def detect_data_exfiltration(text: str, parameters: Dict) -> tuple[bool, List[str]]:
    """
    Detect potential data exfiltration attempts
    
    Returns:
        (is_suspicious, reasons)
    """
    reasons = []
    text_lower = text.lower()
    
    # Check for mass data extraction keywords
    exfil_keywords = [
        'all users', 'all data', 'entire database',
        'export all', 'download all', 'dump database',
        'select *', 'full backup'
    ]
    
    for keyword in exfil_keywords:
        if keyword in text_lower:
            reasons.append(f"Data exfiltration keyword: {keyword}")
    
    # Check for suspicious email recipients
    if 'to' in parameters:
        email = str(parameters['to']).lower()
        suspicious_domains = [
            'temp', 'disposable', 'throwaway',
            'guerrilla', '10minute', 'mailinator'
        ]
        for domain in suspicious_domains:
            if domain in email:
                reasons.append(f"Suspicious email domain: {domain}")
    
    # Check for large data volumes
    if 'attachments' in parameters:
        attachments = parameters.get('attachments', [])
        if len(attachments) > 5:
            reasons.append(f"Excessive attachments: {len(attachments)}")
    
    return len(reasons) > 0, reasons

def get_severity_level(risk_score: int) -> str:
    """Determine severity level from risk score"""
    if risk_score >= 90:
        return "CRITICAL"
    elif risk_score >= 70:
        return "HIGH"
    elif risk_score >= 40:
        return "MEDIUM"
    else:
        return "LOW"

def format_risk_breakdown(breakdown: Dict) -> str:
    """Format risk breakdown for display"""
    lines = ["Risk Breakdown:"]
    for key, value in breakdown.items():
        if key != "total":
            lines.append(f"  • {key.replace('_', ' ').title()}: {value}")
    lines.append(f"  • Total Score: {breakdown['total']}")
    return "\n".join(lines)

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def safe_json_parse(json_str: str) -> Optional[Dict]:
    """Safely parse JSON string"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return None

def safe_json_dumps(data: Any, indent: int = None) -> str:
    """Safely convert to JSON string"""
    try:
        return json.dumps(data, indent=indent, default=str)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON dumps error: {e}")
        return "{}"

def compare_similarity(text1: str, text2: str) -> float:
    """
    Simple similarity comparison between two texts
    Returns value between 0 and 1
    """
    keywords1 = set(extract_keywords(text1))
    keywords2 = set(extract_keywords(text2))
    
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    
    return intersection / union if union > 0 else 0.0

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {user_id: [timestamps]}
    
    def is_allowed(self, user_id: int) -> tuple[bool, Optional[int]]:
        """
        Check if request is allowed
        
        Returns:
            (is_allowed, seconds_until_reset)
        """
        now = datetime.now().timestamp()
        
        # Initialize if first request
        if user_id not in self.requests:
            self.requests[user_id] = [now]
            return True, None
        
        # Clean old timestamps
        cutoff = now - self.window_seconds
        self.requests[user_id] = [ts for ts in self.requests[user_id] if ts > cutoff]
        
        # Check limit
        if len(self.requests[user_id]) < self.max_requests:
            self.requests[user_id].append(now)
            return True, None
        
        # Calculate wait time
        oldest = min(self.requests[user_id])
        wait_time = int(self.window_seconds - (now - oldest))
        
        return False, wait_time
