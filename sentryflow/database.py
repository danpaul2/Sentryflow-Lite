

import mysql.connector
from mysql.connector import pooling, Error
import json
from contextlib import contextmanager
from typing import Optional, Dict, List, Any
from config import DB_CONFIG, ENABLE_CACHE, CACHE_TTL
from logger import logger
from functools import lru_cache
import time
from utils import hash_password, verify_password

class DatabasePool:
    """Database connection pool manager"""
    
    _pool = None
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._pool is None:
            try:
                self._pool = pooling.MySQLConnectionPool(**DB_CONFIG)
                logger.info("Database connection pool initialized", pool_size=DB_CONFIG['pool_size'])
            except Error as e:
                logger.error(f"Failed to create connection pool: {e}")
                raise
    
    def get_connection(self):
        """Get a connection from the pool"""
        try:
            return self._pool.get_connection()
        except Error as e:
            logger.error(f"Failed to get connection from pool: {e}")
            raise

class Database:
    """Enhanced database operations with connection pooling and error handling"""
    
    def __init__(self):
        self.pool = DatabasePool()
        self.conn = None
        self.cursor = None
        try:
            self._ensure_core_tools()
            self._ensure_auth_schema()
        except Error:
     
            pass
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor with automatic cleanup"""
        conn = None
        cursor = None
        try:
            conn = self.pool.get_connection()
       
            cursor = conn.cursor(dictionary=True, buffered=True)
            yield cursor, conn
        except Error as e:
            if conn:
                conn.rollback()
            logger.error_with_context(e, "Database operation failed")
            raise
        finally:
            if cursor:
                try:
                    while True:
                        has_more = cursor.nextset()
                        if not has_more:
                            break
                        cursor.fetchall()
                except Exception:
                    pass
                cursor.close()
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch: str = 'one') -> Optional[Any]:
        """
        Execute a query with error handling
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: 'one', 'all', or 'none'
        """
        with self.get_cursor() as (cursor, conn):
            cursor.execute(query, params or ())
            
            if fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'all':
                return cursor.fetchall()
            elif fetch == 'none':
                conn.commit()
                return cursor.lastrowid
    

    def _ensure_core_tools(self) -> None:
        """
        Ensure core tools and basic policies exist.
        This makes the app work even if schema seed inserts weren't run.
        """
        try:
            existing = self.execute_query(
                "SELECT COUNT(*) AS cnt FROM tools",
                fetch='one'
            )
        except Error:
            # Likely schema not created yet
            return
        
        if not existing or existing.get("cnt", 0) > 0:
            return
        
        # Insert core tools
        tools = [
            ("send_email", "Send an external email", "communication"),
            ("search_web", "Search information online", "information"),
            ("create_report", "Generate internal report", "documents"),
        ]
        for name, desc, category in tools:
            try:
                self.execute_query(
                    """
                    INSERT IGNORE INTO tools (tool_name, description, category)
                    VALUES (%s, %s, %s)
                    """,
                    (name, desc, category),
                    fetch='none'
                )
            except Error:
                continue

    def _ensure_auth_schema(self) -> None:
        """
        Ensure authentication-related schema exists (e.g. password_hash column).
        Safe to run repeatedly; it is a no-op if everything is already in place.
        """
        try:
            # Check for password_hash column on users table
            column = self.execute_query(
                "SHOW COLUMNS FROM users LIKE 'password_hash'",
                fetch='one'
            )
        except Error:
            # users table may not exist yet; let schema.sql handle it
            return
        
        if column:
            return
        
        # Try to add the missing column
        try:
            self.execute_query(
                "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL",
                fetch='none'
            )
            logger.info("Added password_hash column to users table for authentication support")
        except Error as e:
            logger.error(f"Failed to add password_hash column: {e}")

    # ==========================================
    # USER OPERATIONS
    # ==========================================
    
    @lru_cache(maxsize=128)
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user by username (cached)"""
        query = "SELECT * FROM users WHERE username=%s"
        return self.execute_query(query, (username,), fetch='one')
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        query = "SELECT * FROM users WHERE id=%s"
        return self.execute_query(query, (user_id,), fetch='one')
    
    def create_user(self, username: str, role: str, email: str = None) -> int:
        """Create a new user"""
        query = """
        INSERT INTO users (username, role, email)
        VALUES (%s, %s, %s)
        """
        try:
            user_id = self.execute_query(query, (username, role, email), fetch='none')
            logger.info(f"User created", username=username, role=role, user_id=user_id)
            # Invalidate cache
            self.get_user.cache_clear()
            return user_id
        except Error as e:
            logger.error(f"Failed to create user: {e}", username=username)
            raise
    
    def create_user_with_password(self, username: str, role: str, email: str, password: str) -> int:
        """Create a new user with a hashed password."""
        password_hash = hash_password(password)
        query = """
        INSERT INTO users (username, role, email, password_hash)
        VALUES (%s, %s, %s, %s)
        """
        try:
            user_id = self.execute_query(query, (username, role, email, password_hash), fetch='none')
            logger.info("User created with password", username=username, role=role, user_id=user_id)
            self.get_user.cache_clear()
            return user_id
        except Error as e:
            logger.error(f"Failed to create user with password: {e}", username=username)
            raise
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate a user by username and password."""
        user = self.get_user(username)
        if not user:
            return None
        
        stored_hash = user.get("password_hash")
        if not stored_hash:
            return None
        
        if verify_password(password, stored_hash):
            return user
        return None
    
    def update_user_role(self, user_id: int, new_role: str) -> bool:
        """Update user role"""
        query = "UPDATE users SET role=%s WHERE id=%s"
        try:
            self.execute_query(query, (new_role, user_id), fetch='none')
            self.get_user.cache_clear()
            logger.info(f"User role updated", user_id=user_id, new_role=new_role)
            return True
        except Error as e:
            logger.error(f"Failed to update user role: {e}", user_id=user_id)
            return False
    
    # ==========================================
    # SESSION OPERATIONS
    # ==========================================
    
    def create_session(self, user_id: int, prompt: str) -> int:
        """Create a new session"""
        query = """
        INSERT INTO sessions (user_id, original_prompt)
        VALUES (%s, %s)
        """
        try:
            session_id = self.execute_query(query, (user_id, prompt), fetch='none')
            logger.debug(f"Session created", session_id=session_id, user_id=user_id)
            return session_id
        except Error as e:
            logger.error(f"Failed to create session: {e}", user_id=user_id)
            raise
    
    def close_session(self, session_id: int) -> bool:
        """Close a session"""
        query = "UPDATE sessions SET session_status='closed' WHERE id=%s"
        try:
            self.execute_query(query, (session_id,), fetch='none')
            logger.debug(f"Session closed", session_id=session_id)
            return True
        except Error as e:
            logger.error(f"Failed to close session: {e}", session_id=session_id)
            return False
    
    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get session details"""
        query = "SELECT * FROM sessions WHERE id=%s"
        return self.execute_query(query, (session_id,), fetch='one')
    
    def get_user_sessions(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get recent sessions for a user"""
        query = """
        SELECT * FROM sessions 
        WHERE user_id=%s 
        ORDER BY created_at DESC 
        LIMIT %s
        """
        return self.execute_query(query, (user_id, limit), fetch='all') or []
    
    # ==========================================
    # TOOL OPERATIONS
    # ==========================================
    
    @lru_cache(maxsize=64)
    def get_tool(self, tool_name: str) -> Optional[Dict]:
        """Get tool by name (cached)"""
        query = "SELECT * FROM tools WHERE tool_name=%s AND is_active=1"
        return self.execute_query(query, (tool_name,), fetch='one')
    
    def get_all_tools(self, active_only: bool = True) -> List[Dict]:
        """Get all tools"""
        query = "SELECT * FROM tools"
        if active_only:
            query += " WHERE is_active=1"
        return self.execute_query(query, fetch='all') or []
    
    def create_tool(self, tool_name: str, description: str, category: str) -> int:
        """Create a new tool definition."""
        query = """
        INSERT INTO tools (tool_name, description, category, is_active)
        VALUES (%s, %s, %s, 1)
        """
        try:
            tool_id = self.execute_query(query, (tool_name, description, category), fetch='none')
            # Clear any cached tool lookups
            self.get_tool.cache_clear()
            logger.info("Tool created", tool_id=tool_id, tool_name=tool_name, category=category)
            return tool_id
        except Error as e:
            logger.error(f"Failed to create tool: {e}", tool_name=tool_name)
            raise
    
    def toggle_tool(self, tool_id: int, is_active: bool) -> bool:
        """Enable or disable a tool"""
        query = "UPDATE tools SET is_active=%s WHERE id=%s"
        try:
            self.execute_query(query, (is_active, tool_id), fetch='none')
            self.get_tool.cache_clear()
            logger.info(f"Tool toggled", tool_id=tool_id, is_active=is_active)
            return True
        except Error as e:
            logger.error(f"Failed to toggle tool: {e}", tool_id=tool_id)
            return False
    
    # ==========================================
    # POLICY OPERATIONS
    # ==========================================
    
    @lru_cache(maxsize=64)
    def get_policy(self, tool_id: int) -> Optional[Dict]:
        """Get policy for a tool (cached)"""
        query = "SELECT * FROM policies WHERE tool_id=%s"
        return self.execute_query(query, (tool_id,), fetch='one')
    
    def update_policy(self, tool_id: int, max_risk: int = None, 
                     allowed_roles: List[str] = None) -> bool:
        """Update tool policy"""
        updates = []
        params = []
        
        if max_risk is not None:
            updates.append("max_risk=%s")
            params.append(max_risk)
        
        if allowed_roles is not None:
            updates.append("allowed_roles=%s")
            params.append(json.dumps(allowed_roles))
        
        if not updates:
            return False
        
        params.append(tool_id)
        query = f"UPDATE policies SET {', '.join(updates)} WHERE tool_id=%s"
        
        try:
            self.execute_query(query, tuple(params), fetch='none')
            self.get_policy.cache_clear()
            logger.info(f"Policy updated", tool_id=tool_id)
            return True
        except Error as e:
            logger.error(f"Failed to update policy: {e}", tool_id=tool_id)
            return False
    
    def create_policy(self, tool_id: int, max_risk: int, allowed_roles: List[str], require_judge_check: bool = True) -> bool:
        """Create a new policy entry for a tool."""
        query = """
        INSERT INTO policies (tool_id, max_risk, allowed_roles, require_judge_check)
        VALUES (%s, %s, %s, %s)
        """
        try:
            self.execute_query(
                query,
                (tool_id, max_risk, json.dumps(allowed_roles), require_judge_check),
                fetch='none'
            )
            # Clear cache so new policy is visible immediately
            self.get_policy.cache_clear()
            logger.info("Policy created", tool_id=tool_id, max_risk=max_risk, allowed_roles=allowed_roles)
            return True
        except Error as e:
            logger.error(f"Failed to create policy: {e}", tool_id=tool_id)
            return False
    
    # ==========================================
    # ACTION LOGGING
    # ==========================================
    
    def log_action(self, data: Dict) -> int:
        """Log an agent action"""
        query = """
        INSERT INTO agent_actions
        (session_id, tool_name, parameters,
         structural_valid, suspicious_flag,
         judge_verdict, risk_score, final_decision)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """
        try:
            action_id = self.execute_query(query, (
                data["session_id"],
                data["tool_name"],
                json.dumps(data["parameters"]),
                data["structural_valid"],
                data["suspicious_flag"],
                data["judge_verdict"],
                data["risk_score"],
                data["final_decision"]
            ), fetch='none')
            
            logger.log_action(
                action_id=action_id,
                decision=data["final_decision"],
                risk_score=data["risk_score"],
                user=data.get("username", "unknown"),
                tool=data["tool_name"]
            )
            
            return action_id
        except Error as e:
            logger.error(f"Failed to log action: {e}")
            raise
    
    def log_risk_breakdown(self, action_id: int, breakdown: Dict) -> bool:
        """Log risk breakdown for an action"""
        query = """
        INSERT INTO risk_logs
        (action_id,
         structural_score,
         suspicious_score,
         judge_score,
         role_violation_score,
         prompt_injection_score,
         data_exfiltration_score,
         total_score,
         detected_patterns)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        try:
            self.execute_query(query, (
                action_id,
                breakdown["structural"],
                breakdown["suspicious"],
                breakdown["judge"],
                breakdown["role"],
                breakdown.get("prompt_injection", 0),
                breakdown.get("data_exfiltration", 0),
                breakdown["total"],
                json.dumps([]),  # placeholder until patterns are stored here
            ), fetch='none')
            return True
        except Error as e:
            logger.error(f"Failed to log risk breakdown: {e}", action_id=action_id)
            return False
    
    def log_blocked(self, action_id: int, reason: str, severity: str) -> bool:
        """Log a blocked action"""
        query = """
        INSERT INTO blocked_actions
        (action_id, block_reason, severity)
        VALUES (%s,%s,%s)
        """
        try:
            self.execute_query(query, (action_id, reason, severity), fetch='none')
            return True
        except Error as e:
            logger.error(f"Failed to log blocked action: {e}", action_id=action_id)
            return False
    
    # ==========================================
    # ANALYTICS & REPORTING
    # ==========================================
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get statistics for a user"""
        query = """
        SELECT 
            COUNT(*) as total_actions,
            SUM(CASE WHEN final_decision='ALLOWED' THEN 1 ELSE 0 END) as allowed,
            SUM(CASE WHEN final_decision='BLOCKED' THEN 1 ELSE 0 END) as blocked,
            SUM(CASE WHEN final_decision='ESCALATED' THEN 1 ELSE 0 END) as escalated,
            AVG(risk_score) as avg_risk_score
        FROM agent_actions a
        JOIN sessions s ON a.session_id = s.id
        WHERE s.user_id=%s
        """
        result = self.execute_query(query, (user_id,), fetch='one')
        return result or {}
    
    def get_recent_actions(self, limit: int = 50, decision: str = None) -> List[Dict]:
        """Get recent actions with optional filtering"""
        query = """
        SELECT a.*, s.user_id, u.username, u.role
        FROM agent_actions a
        JOIN sessions s ON a.session_id = s.id
        JOIN users u ON s.user_id = u.id
        """
        params = []
        
        if decision:
            query += " WHERE a.final_decision=%s"
            params.append(decision)
        
        query += " ORDER BY a.created_at DESC LIMIT %s"
        params.append(limit)
        
        return self.execute_query(query, tuple(params), fetch='all') or []
    
    def get_tool_usage_stats(self) -> List[Dict]:
        """
        Get usage statistics by tool.

        Prefer the materialized analytics view if it exists; fall back to
        aggregating directly from agent_actions when the view is missing.
        """
        try:
            # View defined in schema.sql as tool_usage_stats
            query = "SELECT * FROM tool_usage_stats ORDER BY usage_count DESC"
            return self.execute_query(query, fetch='all') or []
        except Error:
            # Fallback: compute basic stats directly
            query = """
            SELECT 
                tool_name,
                COUNT(*) as usage_count,
                SUM(CASE WHEN final_decision='BLOCKED' THEN 1 ELSE 0 END) as blocked_count,
                AVG(risk_score) as avg_risk_score
            FROM agent_actions
            GROUP BY tool_name
            ORDER BY usage_count DESC
            """
            return self.execute_query(query, fetch='all') or []
    
    def get_high_risk_actions(self, threshold: int = 70, limit: int = 20) -> List[Dict]:
        """
        Get high-risk actions.

        Prefer the high_risk_actions view if available; otherwise fall back
        to querying directly from agent_actions joined with users/sessions.
        """
        try:
            query = """
            SELECT *
            FROM high_risk_actions
            WHERE risk_score >= %s
            ORDER BY risk_score DESC, created_at DESC
            LIMIT %s
            """
            return self.execute_query(query, (threshold, limit), fetch='all') or []
        except Error:
            query = """
            SELECT a.*, s.user_id, u.username, u.role
            FROM agent_actions a
            JOIN sessions s ON a.session_id = s.id
            JOIN users u ON s.user_id = u.id
            WHERE a.risk_score >= %s
            ORDER BY a.risk_score DESC, a.created_at DESC
            LIMIT %s
            """
            return self.execute_query(query, (threshold, limit), fetch='all') or []
