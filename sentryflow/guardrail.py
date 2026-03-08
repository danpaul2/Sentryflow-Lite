

from typing import Dict, Tuple, List
from config import (
    SUSPICIOUS_PATTERNS,
    RISK_WEIGHTS,
    HIGH_RISK_THRESHOLD,
    CRITICAL_RISK_THRESHOLD,
)
from utils import (
    validate_tool_parameters, 
    detect_prompt_injection,
    detect_data_exfiltration
)
from logger import logger

class GuardrailSystem:
    """
    Behavioral guardrail system for validating agent actions.

    SentryFlow Lite treats each tool call as a concrete behavior
    proposal from the agent. This system looks at that behavior in
    context of the original user prompt and the judge verdict, and
    turns it into a structured risk score and allow/block/escalate
    decision before anything actually runs.
    """
    
    def __init__(self):
        self.suspicious_patterns = SUSPICIOUS_PATTERNS
        self.risk_weights = RISK_WEIGHTS
    
    def validate_structure(self, tool_json: Dict) -> Tuple[bool, str]:
        """
        Validate the structure of the tool JSON
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(tool_json, dict):
            return False, "Tool output must be a dictionary"
        
        if "tool" not in tool_json:
            return False, "Missing 'tool' field"
        
        if "parameters" not in tool_json:
            return False, "Missing 'parameters' field"
        
        if not isinstance(tool_json["parameters"], dict):
            return False, "'parameters' must be a dictionary"
        
        tool_name = tool_json["tool"]
        parameters = tool_json["parameters"]
        
        is_valid, error = validate_tool_parameters(tool_name, parameters)
        if not is_valid:
            return False, error
        
        return True, "Valid structure"
    
    def detect_suspicious(self, tool_json: Dict, user_prompt: str = "") -> Tuple[bool, List[str]]:
        """
        Detect suspicious patterns in tool usage
        
        Returns:
            (is_suspicious, detected_patterns)
        """
        detected_patterns = []
        
        tool_str = str(tool_json).lower() #lowercase
        prompt_str = user_prompt.lower()
        combined_text = tool_str + " " + prompt_str
        
        for pattern in self.suspicious_patterns:
            if pattern in combined_text:
                detected_patterns.append(pattern)
        
        #  prompt injection check 
        is_injection, injection_patterns = detect_prompt_injection(user_prompt)
        if is_injection:
            detected_patterns.extend([f"prompt_injection: {p}" for p in injection_patterns])
        
        # data exfiltration check
        is_exfil, exfil_reasons = detect_data_exfiltration(
            user_prompt, 
            tool_json.get("parameters", {})
        )
        if is_exfil:
            detected_patterns.extend([f"data_exfil: {r}" for r in exfil_reasons])
        
        return len(detected_patterns) > 0, detected_patterns
    
    def compute_risk_breakdown(
        self,
        structural_valid: bool,
        suspicious_flag: bool,
        suspicious_patterns: List[str],
        judge_safe: bool,
        role_violation: bool
    ) -> Dict[str, int]:
        """
        Compute detailed risk breakdown with weighted scoring
        
        Returns:
            Dictionary with individual and total risk scores
        """
        breakdown = {
            "structural": 0,
            "suspicious": 0,
            "judge": 0,
            "role": 0,
            "prompt_injection": 0,
            "data_exfiltration": 0,
            "total": 0
        }
        
        if not structural_valid:
            breakdown["structural"] = self.risk_weights["structural"]
        
        if suspicious_flag:
            pattern_count = len(suspicious_patterns)
            
            injection_patterns = [p for p in suspicious_patterns if "prompt_injection" in p]
            exfil_patterns = [p for p in suspicious_patterns if "data_exfil" in p]
            basic_patterns = [p for p in suspicious_patterns 
                            if "prompt_injection" not in p and "data_exfil" not in p]
            
            if injection_patterns:
                breakdown["prompt_injection"] = self.risk_weights["prompt_injection"]
            
            if exfil_patterns:
                breakdown["data_exfiltration"] = self.risk_weights["data_exfiltration"]
            
            if basic_patterns:
                breakdown["suspicious"] = min(
                    self.risk_weights["suspicious"],
                    len(basic_patterns) * 10
                )
        
        # Judge verdict
        if not judge_safe:
            breakdown["judge"] = self.risk_weights["judge"]
        
        if role_violation:
            breakdown["role"] = self.risk_weights["role_violation"]
        
        # Calculate total
        breakdown["total"] = sum(breakdown.values())
        
        return breakdown
    
    def assess_severity(self, risk_score: int, max_risk: int) -> str:
        """Determine severity level"""
        if risk_score >= 90:
            return "CRITICAL"
        elif risk_score >= 70:
            return "HIGH"
        elif risk_score > max_risk:
            return "MEDIUM"
        else:
            return "LOW"
    
    def make_decision(
        self, 
        risk_score: int, 
        max_risk: int,
        high_risk_threshold: int = HIGH_RISK_THRESHOLD,
        critical_risk_threshold: int = CRITICAL_RISK_THRESHOLD,
    ) -> Tuple[str, str]:
        """
        Make final decision based on risk score
        
        Returns:
            (decision, severity)
        """
        if risk_score >= critical_risk_threshold:
            return "BLOCKED", "CRITICAL"
        elif risk_score >= high_risk_threshold:
            return "BLOCKED", "HIGH"
        elif risk_score > max_risk:
            return "ESCALATED", "MEDIUM"
        else:
            return "ALLOWED", "LOW"
    
    def generate_block_reason(
        self,
        structural_valid: bool,
        suspicious_patterns: List[str],
        judge_safe: bool,
        role_violation: bool,
        breakdown: Dict[str, int]
    ) -> str:
        """Generate detailed block reason"""
        reasons = []
        
        if not structural_valid:
            reasons.append("Invalid tool structure")
        
        if suspicious_patterns:
            unique_patterns = set(p.split(":")[0] for p in suspicious_patterns)
            reasons.append(f"Suspicious patterns detected: {', '.join(unique_patterns)}")
        
        if not judge_safe:
            reasons.append("Judge determined action is unsafe")
        
        if role_violation:
            reasons.append("User role not authorized for this tool")
        
        if breakdown["prompt_injection"] > 0:
            reasons.append("Potential prompt injection detected")
        
        if breakdown["data_exfiltration"] > 0:
            reasons.append("Potential data exfiltration attempt")
        
        return " | ".join(reasons) if reasons else "Risk threshold exceeded"
    
    def validate_and_assess(
        self,
        tool_json: Dict,
        user_prompt: str,
        judge_verdict: bool,
        role_violation: bool,
        max_risk: int = 50
    ) -> Dict:
        """
        Complete validation and risk assessment pipeline
        
        Returns:
            Complete assessment with decision
        """
        structural_valid, struct_error = self.validate_structure(tool_json)
        
        suspicious_flag, suspicious_patterns = self.detect_suspicious(tool_json, user_prompt)
        
        breakdown = self.compute_risk_breakdown(
            structural_valid,
            suspicious_flag,
            suspicious_patterns,
            judge_verdict,
            role_violation
        )
        
        risk_score = breakdown["total"]
        
        decision, severity = self.make_decision(risk_score, max_risk)
        
        block_reason = None
        if decision in ["BLOCKED", "ESCALATED"]:
            block_reason = self.generate_block_reason(
                structural_valid,
                suspicious_patterns,
                judge_verdict,
                role_violation,
                breakdown
            )
        
        
        logger.debug(
            "Guardrail assessment completed",
            risk_score=risk_score,
            decision=decision,
            severity=severity
        )
        
        return {
            "structural_valid": structural_valid,
            "structural_error": struct_error,
            "suspicious_flag": suspicious_flag,
            "suspicious_patterns": suspicious_patterns,
            "risk_breakdown": breakdown,
            "risk_score": risk_score,
            "decision": decision,
            "severity": severity,
            "block_reason": block_reason
        }


guardrail = GuardrailSystem()

def validate_structure(tool_json: Dict) -> bool:
    """Backward compatible function"""
    is_valid, _ = guardrail.validate_structure(tool_json)
    return is_valid

def detect_suspicious(tool_json: Dict) -> bool:
    """Backward compatible function"""
    is_suspicious, _ = guardrail.detect_suspicious(tool_json)
    return is_suspicious

def compute_risk_breakdown(structural_valid, suspicious_flag, judge_safe, role_violation):
    """Backward compatible function"""
    return guardrail.compute_risk_breakdown(
        structural_valid,
        suspicious_flag,
        [],  
        judge_safe,
        role_violation
    )
