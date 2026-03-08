

from typing import Tuple, Dict
from utils import extract_keywords, compare_similarity
from logger import logger

class JudgeSystem:
    """
    Secondary verification layer for agent actions.

    The judge takes the original user prompt and the agent's proposed
    tool call (tool name + parameters) and decides whether that call
    is aligned with what the user actually asked for, in-scope for
    the tool, and non-destructive.

    In other words, this is the “second pair of eyes” that SentryFlow
    Lite uses to catch obviously wrong or unsafe behaviors before any
    tool is allowed to execute.
    """
    
    def __init__(self):
        self.tool_purposes = {
            "send_email": {
                "primary_purpose": "communication",
                "expected_keywords": ["send", "email", "message", "notify", "contact", "tell"],
                "unexpected_keywords": ["search", "find", "look up", "report", "document"]
            },
            "search_web": {
                "primary_purpose": "information_retrieval",
                "expected_keywords": ["search", "find", "look up", "information", "query"],
                "unexpected_keywords": ["send", "email", "create", "write"]
            },
            "create_report": {
                "primary_purpose": "document_creation",
                "expected_keywords": ["create", "report", "document", "write", "generate"],
                "unexpected_keywords": ["search", "email", "send"]
            }
        }
    
    def check_tool_alignment(self, prompt: str, tool_name: str) -> Tuple[bool, float]:
        """
        Check if the tool aligns with the prompt
        
        Returns:
            (is_aligned, alignment_score)
        """
        if tool_name not in self.tool_purposes:
            return True, 1.0 
        
        prompt_lower = prompt.lower()
        tool_purpose = self.tool_purposes[tool_name]
        
        expected_matches = sum(
            1 for kw in tool_purpose["expected_keywords"] 
            if kw in prompt_lower
        )
        
        unexpected_matches = sum(
            1 for kw in tool_purpose["unexpected_keywords"] 
            if kw in prompt_lower
        )
        
        expected_score = expected_matches / len(tool_purpose["expected_keywords"])
        unexpected_penalty = unexpected_matches * 0.2
        
        alignment_score = max(0.0, expected_score - unexpected_penalty)
        
        is_aligned = alignment_score > 0.3 or expected_matches > 0
        
        return is_aligned, alignment_score
    
    def check_parameter_safety(self, tool_name: str, parameters: Dict) -> Tuple[bool, str]:
        """
        Check if parameters are safe and appropriate
        
        Returns:
            (is_safe, reason)
        """
        if tool_name == "send_email":
            return self._check_email_safety(parameters)
        elif tool_name == "search_web":
            return self._check_search_safety(parameters)
        elif tool_name == "create_report":
            return self._check_report_safety(parameters)
        else:
            return True, "No safety checks defined for this tool"
    
    def _check_email_safety(self, params: Dict) -> Tuple[bool, str]:
        """Check email parameter safety"""
        body = str(params.get("body", "")).lower()
        to = str(params.get("to", "")).lower()
        
        # sensitive info
        sensitive_patterns = [
            "password", "credentials", "secret key", "api key",
            "confidential", "private key", "credit card"
        ]
        
        for pattern in sensitive_patterns:
            if pattern in body:
                return False, f"Email contains sensitive information: {pattern}"
        
        # sus external domains
        if any(domain in to for domain in ["temp", "disposable", "guerrilla"]):
            return False, "Email to suspicious external domain"
        
        #mass sending
        if "cc" in params and isinstance(params["cc"], list) and len(params["cc"]) > 10:
            return False, "Mass email sending detected"
        
        return True, "Email parameters are safe"
    
    def _check_search_safety(self, params: Dict) -> Tuple[bool, str]:
        """Check search parameter safety"""
        query = str(params.get("query", "")).lower()
        
        # Check for malicious search queries
        malicious_patterns = [
            "exploit", "vulnerability", "hack", "bypass",
            "crack", "keygen", "malware"
        ]
        
        for pattern in malicious_patterns:
            if pattern in query:
                return False, f"Potentially malicious search query: {pattern}"
        
        return True, "Search parameters are safe"
    
    def _check_report_safety(self, params: Dict) -> Tuple[bool, str]:
        """Check report parameter safety"""
        content = str(params.get("content", "")).lower()
        
        # data exfiltration 
        if any(word in content for word in ["dump", "extract all", "export database"]):
            return False, "Report appears to contain data exfiltration attempt"
        
        return True, "Report parameters are safe"
    
    def check_context_consistency(self, prompt: str, tool_json: Dict) -> Tuple[bool, str]:
        """
        Check if the action is consistent with the prompt context
        
        Returns:
            (is_consistent, reason)
        """
        tool_name = tool_json.get("tool")
        parameters = tool_json.get("parameters", {})
        
        # Example: If prompt asks to search but tool sends email
        prompt_keywords = set(extract_keywords(prompt))
        
        # mismatches
        if "search" in prompt.lower() and tool_name == "send_email":
            return False, "User asked to search but action is sending email"
        
        if "email" in prompt.lower() and tool_name == "search_web":
            return False, "User asked to email but action is searching web"
        
        # Check if parameters match prompt intent
        if tool_name == "send_email":
            body = str(parameters.get("body", "")).lower()
            if "search" in prompt.lower() and "search" not in body:
                return False, "Email body doesn't reflect search intent from prompt"
        
        return True, "Action is consistent with prompt"
    
    def judge(self, user_prompt: str, tool_json: Dict) -> Tuple[bool, str]:
        """
        Main judge function - comprehensive safety and alignment check
        
        Returns:
            (is_safe, reason)
        """
        tool_name = tool_json.get("tool_name") or tool_json.get("tool", "")
        parameters = tool_json.get("parameters", {})
        dangerous_patterns = ["delete","shutdown","wipe","format","drop"]

        for pattern in dangerous_patterns:
            if tool_name and pattern in tool_name:
                reason = f"Dangerous tool detected: {tool_name}"
                logger.warning("Judge verdict: UNSAFE", reason=reason)
                return False, reason
                
        # Also check parameters for dangerous patterns
        def scan_dict_for_patterns(d):
            if isinstance(d, dict):
                for v in d.values():
                    scan_dict_for_patterns(v)
            elif isinstance(d, list):
                for item in d:
                    scan_dict_for_patterns(item)
            elif isinstance(d, str):
                d_lower = d.lower()
                for pattern in dangerous_patterns:
                    # Look for standalone words to avoid matching "dropout" or "format" when it's safe
                    import re
                    if re.search(rf'\b{pattern}\b', d_lower):
                        reason = f"Dangerous pattern '{pattern}' detected in parameters"
                        logger.warning("Judge verdict: UNSAFE", reason=reason)
                        raise ValueError(reason)

        try:
            scan_dict_for_patterns(parameters)
        except ValueError as e:
            return False, str(e)

        
        # Check 1: Tool alignment
        is_aligned, alignment_score = self.check_tool_alignment(user_prompt, tool_name)
        if not is_aligned:
            reason = f"Tool '{tool_name}' is not aligned with user prompt (score: {alignment_score:.2f})"
            logger.warning(f"Judge verdict: UNSAFE", reason=reason)
            return False, reason
        
        # Check 2: Parameter safety
        is_safe, safety_reason = self.check_parameter_safety(tool_name, parameters)
        if not is_safe:
            logger.warning(f"Judge verdict: UNSAFE", reason=safety_reason)
            return False, safety_reason
        
        # Check 3: Context consistency
        is_consistent, consistency_reason = self.check_context_consistency(user_prompt, tool_json)
        if not is_consistent:
            logger.warning(f"Judge verdict: UNSAFE", reason=consistency_reason)
            return False, consistency_reason
        
        # All checks passed
        logger.debug(f"Judge verdict: SAFE", tool=tool_name, alignment_score=alignment_score)
        return True, "Action is safe and aligned"

# Global judge instance
judge = JudgeSystem()

# Convenience function for backward compatibility
def judge_action(user_prompt: str, tool_json: Dict) -> Tuple[bool, str]:
    """Backward compatible function"""
    return judge.judge(user_prompt, tool_json)
