# ==============================
# main.py
# ==============================

import json
import sys
from typing import Dict, Optional
from database import Database
from guardrail import guardrail
from agent import agent_decide
from judge import judge_action
from config import DEFAULT_MAX_RISK, HIGH_RISK_THRESHOLD, CRITICAL_RISK_THRESHOLD
from logger import logger
from utils import RateLimiter, format_risk_breakdown
from config import RATE_LIMIT_ENABLED, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW

class SentryFlowPipeline:
    """
    Main SentryFlow Lite pipeline.

    This acts as middleware between an AI agent and its tools:
    - takes the original user prompt
    - lets the routing agent propose a tool call (tool + parameters)
    - runs that proposed behavior through the judge + guardrail stack
    - only then would a caller be allowed to actually execute the tool
      based on the final ALLOW/BLOCK/ESCALATE decision.
    """
    
    def __init__(self):
        self.db = Database()
        self.rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW) if RATE_LIMIT_ENABLED else None
    
    def get_or_create_user(self, username: str, role: str = "employee", email: str = None) -> Dict:
        """Get existing user or create new one"""
        user = self.db.get_user(username)
        if not user:
            user_id = self.db.create_user(username, role, email)
            user = self.db.get_user_by_id(user_id)
            logger.info(f"New user created", username=username, role=role)
        return user
    
    def check_rate_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        """Check if user has exceeded rate limit"""
        if not self.rate_limiter:
            return True, None
        return self.rate_limiter.is_allowed(user_id)
    
    def authenticate_or_register_user(
        self,
        username: str,
        role: str,
        email: str,
        password: str
    ) -> Dict:
        """
        Authenticate an existing user or create a new one with a password.
        
        - If the user exists, the password must match.
        - If the user does not exist, a new account is created with the given password.
        """
        # First, try to authenticate existing user
        existing = self.db.get_user(username)
        if existing:
            user = self.db.authenticate_user(username, password)
            if not user:
                raise ValueError("Invalid username or password.")
            return user
        
        # Create new user with password
        user_id = self.db.create_user_with_password(username, role, email, password)
        return self.db.get_user_by_id(user_id)
    
    def process_action(
        self,
        username: str,
        user_role: str,
        prompt: str,
        email: str = None
    ) -> Dict:
        """
        Main processing pipeline for an agent action
        
        Returns:
            Complete result dictionary
        """
        try:
            # Step 1: Get or create user
            user = self.get_or_create_user(username, user_role, email)
            user_id = user["id"]
            role = user["role"]
            
            # Step 2: Check rate limit
            is_allowed, wait_time = self.check_rate_limit(user_id)
            if not is_allowed:
                logger.warning(f"Rate limit exceeded", username=username, wait_time=wait_time)
                return {
                    "success": False,
                    "error": f"Rate limit exceeded. Try again in {wait_time} seconds",
                    "wait_time": wait_time
                }
            
            # Step 3: Create session
            session_id = self.db.create_session(user_id, prompt)
            
            # Step 4: Agent decides on tool and parameters
            logger.info(f"Processing prompt", username=username, prompt_length=len(prompt))
            tool_json = agent_decide(prompt)
            
            # Step 5: Get tool and policy
            tool_record = self.db.get_tool(tool_json["tool"])
            if not tool_record:
                logger.warning(f"Tool not registered", tool_name=tool_json["tool"])
                tool_id = self.db.create_tool(
                    tool_json["tool"],
                    description=tool_json.get("description", "Dynamically created tool"),
                    category=tool_json.get("category", "Dynamic")
                )

                # Set initial risk threshold based on generated risk_level
                risk_level = str(tool_json.get("risk_level", "medium")).lower()
                initial_max_risk = 30 if risk_level == "low" else (70 if risk_level == "high" else DEFAULT_MAX_RISK)

                self.db.create_policy(
                    tool_id,
                    initial_max_risk,
                    ["Admin","Employee"],
                    True
                )
                tool_record = self.db.get_tool(tool_json["tool"])

            policy = self.db.get_policy(tool_record["id"])
            max_risk = policy["max_risk"] if policy else DEFAULT_MAX_RISK
            
            # Step 6: Check role authorization
            role_violation = False
            if policy:
                allowed_roles = json.loads(policy["allowed_roles"])
                if role not in allowed_roles:
                    role_violation = True
                    logger.warning(f"Role violation", username=username, role=role, tool=tool_json["tool"])
            
            # Step 7: Judge evaluation
            judge_safe, judge_reason = judge_action(prompt, tool_json)
            
            # Step 8: Guardrail assessment
            assessment = guardrail.validate_and_assess(
                tool_json,
                prompt,
                judge_safe,
                role_violation,
                max_risk
            )
            
            # Step 9: Log action
            action_data = {
                "session_id": session_id,
                "tool_name": tool_json["tool"],
                "parameters": tool_json["parameters"],
                "structural_valid": assessment["structural_valid"],
                "suspicious_flag": assessment["suspicious_flag"],
                "judge_verdict": "SAFE" if judge_safe else "UNSAFE",
                "risk_score": assessment["risk_score"],
                "final_decision": assessment["decision"],
                "username": username
            }
            
            action_id = self.db.log_action(action_data)
            
            # Step 10: Log risk breakdown
            self.db.log_risk_breakdown(action_id, assessment["risk_breakdown"])
            
            # Step 11: Log blocked action if needed
            if assessment["decision"] in ["BLOCKED", "ESCALATED"]:
                self.db.log_blocked(
                    action_id,
                    assessment["block_reason"],
                    assessment["severity"]
                )
                
                if assessment["decision"] == "BLOCKED":
                    logger.log_blocked(
                        action_id,
                        assessment["block_reason"],
                        assessment["severity"],
                        username
                    )
            
            # Step 12: Close session
            self.db.close_session(session_id)
            
            # Prepare result
            result = {
                "success": True,
                "action_id": action_id,
                "session_id": session_id,
                "user": {
                    "username": username,
                    "role": role
                },
                "tool_json": tool_json,
                "assessment": {
                    "structural_valid": assessment["structural_valid"],
                    "suspicious_flag": assessment["suspicious_flag"],
                    "suspicious_patterns": assessment["suspicious_patterns"],
                    "judge_safe": judge_safe,
                    "judge_reason": judge_reason,
                    "role_violation": role_violation,
                    "risk_breakdown": assessment["risk_breakdown"],
                    "risk_score": assessment["risk_score"],
                    "decision": assessment["decision"],
                    "severity": assessment["severity"],
                    "block_reason": assessment.get("block_reason")
                },
                "policy": {
                    "max_risk": max_risk,
                    "allowed_roles": json.loads(policy["allowed_roles"]) if policy else []
                }
            }
            
            logger.log_action(
                action_id=action_id,
                decision=assessment["decision"],
                risk_score=assessment["risk_score"],
                user=username,
                tool=tool_json["tool"]
            )
            
            return result
            
        except Exception as e:
            logger.error_with_context(e, f"Pipeline processing failed for user {username}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_dashboard(self, username: str) -> Dict:
        """Get dashboard data for a user"""
        try:
            user = self.db.get_user(username)
            if not user:
                return {"error": "User not found"}
            
            stats = self.db.get_user_stats(user["id"])
            sessions = self.db.get_user_sessions(user["id"], limit=5)
            
            return {
                "user": user,
                "stats": stats,
                "recent_sessions": sessions
            }
        except Exception as e:
            logger.error_with_context(e, f"Failed to get dashboard for {username}")
            return {"error": str(e)}
    
    def get_analytics(self) -> Dict:
        """Get system analytics"""
        try:
            tool_stats = self.db.get_tool_usage_stats()
            recent_actions = self.db.get_recent_actions(limit=20)
            high_risk_actions = self.db.get_high_risk_actions(threshold=70, limit=10)
            
            return {
                "tool_stats": tool_stats,
                "recent_actions": recent_actions,
                "high_risk_actions": high_risk_actions
            }
        except Exception as e:
            logger.error_with_context(e, "Failed to get analytics")
            return {"error": str(e)}

def main():
    """Simple CLI demo for SentryFlow Lite"""
    print("=" * 60)
    print("SentryFlow Lite - Agent Tool Guardrail")
    print("=" * 60)
    
    pipeline = SentryFlowPipeline()
    
    # Get user information
    username = input("\nEnter username (default: test_user): ").strip() or "test_user"
    role = input("Enter role [admin/employee/intern] (default: employee): ").strip() or "employee"
    
    # Get prompt
    prompt = input("\nEnter your prompt: ").strip()
    
    if not prompt:
        print("Error: Prompt cannot be empty")
        return
    
    print("\n" + "=" * 60)
    print("Processing...")
    print("=" * 60)
    
    # Process action
    result = pipeline.process_action(username, role, prompt)
    
    # Display results
    if not result["success"]:
        print(f"\nERROR: {result['error']}")
        return
    
    print("\nAGENT OUTPUT:")
    print(json.dumps(result["tool_json"], indent=2))
    
    print("\nASSESSMENT:")
    assessment = result["assessment"]
    print(f"  • Structural Valid: {'yes' if assessment['structural_valid'] else 'no'}")
    print(f"  • Suspicious Flag: {'yes' if assessment['suspicious_flag'] else 'no'}")
    print(f"  • Judge Verdict: {'SAFE' if assessment['judge_safe'] else 'UNSAFE'}")
    print(f"  • Role Violation: {'yes' if assessment['role_violation'] else 'no'}")
    
    if assessment['suspicious_patterns']:
        print(f"\n  Detected Patterns:")
        for pattern in assessment['suspicious_patterns'][:5]:  # Show first 5
            print(f"    - {pattern}")
    
    print("\nRISK BREAKDOWN:")
    breakdown = assessment['risk_breakdown']
    for key, value in breakdown.items():
        if key != "total" and value > 0:
            print(f"  • {key.replace('_', ' ').title()}: {value}")
    print(f"  • Total Score: {breakdown['total']}")
    
    # Final decision
    decision = assessment['decision']
    severity = assessment['severity']
    
    print("\n" + "=" * 60)
    if decision == "ALLOWED":
        print("DECISION: ALLOWED")
    elif decision == "ESCALATED":
        print("DECISION: ESCALATED FOR REVIEW")
    else:
        print("DECISION: BLOCKED")
    
    print(f"Risk Score: {assessment['risk_score']} | Severity: {severity}")
    
    if assessment['block_reason']:
        print(f"Reason: {assessment['block_reason']}")
    
    print("=" * 60)
    
    print(f"\nAction ID: {result['action_id']}")
    print(f"Session ID: {result['session_id']}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        logger.error_with_context(e, "Main function failed")
        print(f"\nError: {e}")
        sys.exit(1)
