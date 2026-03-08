

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from main import SentryFlowPipeline
from database import Database
from config import APP_TITLE, APP_ICON, APP_TAGLINE, PAGE_CONFIG
from logger import logger


st.set_page_config(**PAGE_CONFIG)


@st.cache_resource
def get_pipeline():
    return SentryFlowPipeline()

@st.cache_resource
def get_database():
    return Database()

pipeline = get_pipeline()
db = get_database()

st.markdown("""
<style>
    .stAlert {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .risk-score-low {
        color: #28a745;
        font-weight: bold;
    }
    .risk-score-medium {
        color: #ffc107;
        font-weight: bold;
    }
    .risk-score-high {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "test_prompt" not in st.session_state:
    st.session_state.test_prompt = ""
if "page" not in st.session_state:
    st.session_state.page = "Sign Up"

with st.sidebar:
    st.title(f"{APP_ICON} SentryFlow Lite")
    st.markdown("### Middleware for agent tool calls")
    st.caption(APP_TAGLINE)
    
    pages = ["Sign Up", "Home", "Test Action", "Analytics", "Users", "Settings"]
    current_page = st.session_state.page
    try:
        current_index = pages.index(current_page)
    except ValueError:
        current_index = 0
    
    page = st.radio(
        "Navigation",
        pages,
        index=current_index,
        label_visibility="collapsed"
    )
    st.session_state.page = page
    
    st.divider()
    
    # User profile in sidebar
    current_user = st.session_state.get("current_user")
    if current_user:
        user = current_user
        st.markdown(f"**Current User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].title()}")
        
        if st.button("Logout", use_container_width=True):
            del st.session_state.current_user
            st.rerun()


if page == "Sign Up":
    st.title("Create an Account")
    st.markdown(
        "Create a SentryFlow Lite account. After signing up, go to the Home page "
        "and log in with your new credentials."
    )
    
    with st.form("signup_form"):
        username = st.text_input("Username")
        role = st.selectbox("Role", ["admin", "employee", "intern"])
        email = st.text_input("Email (optional)")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        submit_signup = st.form_submit_button("Sign Up", use_container_width=True)
    
    if submit_signup:
        if not username or not password or not confirm_password:
            st.error("Username and both password fields are required.")
        elif password != confirm_password:
            st.error("Passwords do not match.")
        else:
            existing_user = db.get_user(username)
            if existing_user:
                st.error("That username is already taken. Please choose another.")
            else:
                try:
                    db.create_user_with_password(username, role, email, password)
                except Exception as e:
                    st.error(f"Failed to create account: {e}")
                else:
                    st.success("Account created successfully. You can now log in from the Home page.")
                    st.session_state.page = "Home"
                    st.experimental_rerun()


elif page == "Home":
    st.title(f"{APP_ICON} SentryFlow Lite Dashboard")
    st.markdown(
        "**Sits between your agent and its tools, catching out-of-scope or unsafe "
        "tool calls before they run.**"
    )
    
    if not st.session_state.current_user:
        st.info("Please log in to continue")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            with st.form("login_form"):
                username = st.text_input("Username", value="demo_user")
                role = st.selectbox("Role", ["admin", "employee", "intern"])
                email = st.text_input("Email (optional)")
                password = st.text_input("Password", type="password")
                
                submit_login = st.form_submit_button("Login", use_container_width=True)
                if submit_login:
                    if not username or not password:
                        st.error("Username and password are required.")
                    else:
                        try:
                            user = db.authenticate_user(username, password)
                            if not user:
                                raise ValueError("Invalid username or password.")
                        except ValueError as e:
                            st.error(str(e))
                        except Exception:
                            st.error("Login failed due to an internal error.")
                        else:
                            st.session_state.current_user = user
                            st.success(f"Welcome, {username}!")
                            st.rerun()
        
        with col2:
            st.markdown("### Quick Info")
            st.markdown("""
            **Roles:**
            - Admin: Full access
            - Employee: Standard access
            - Intern: Limited access
            """)
    
    else:
        user = st.session_state.current_user
        
        st.markdown("### Your Activity")
        
        stats = db.get_user_stats(user["id"]) or {}
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_actions_raw = stats.get("total_actions") or 0
        allowed_raw = stats.get("allowed") or 0
        blocked_raw = stats.get("blocked") or 0
        avg_risk_raw = stats.get("avg_risk_score")
        
        with col1:
            try:
                total_actions = int(total_actions_raw)
            except (TypeError, ValueError):
                total_actions = 0
            st.metric("Total Actions", total_actions)
        
        with col2:
            try:
                allowed = int(allowed_raw)
            except (TypeError, ValueError):
                allowed = 0
            st.metric("Allowed", allowed, delta=None, delta_color="normal")
        
        with col3:
            try:
                blocked = int(blocked_raw)
            except (TypeError, ValueError):
                blocked = 0
            st.metric("Blocked", blocked, delta=None, delta_color="inverse")
        
        with col4:
            try:
                avg_risk = float(avg_risk_raw) if avg_risk_raw is not None else 0.0
            except (TypeError, ValueError):
                avg_risk = 0.0
            st.metric("Avg Risk Score", f"{avg_risk:.1f}")
        
        st.divider()
        
        st.markdown("### Recent Sessions")
        sessions = db.get_user_sessions(user["id"], limit=5)
        
        if sessions:
            for session in sessions:
                with st.expander(f"Session {session['id']} - {session['created_at']}", expanded=False):
                    st.markdown(f"**Prompt:** {session['original_prompt']}")
                    st.markdown(f"**Status:** {session['session_status']}")
        else:
            st.info("No sessions yet. Try testing an action!")
        
        st.divider()
        
        st.markdown("### Quick Actions")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Test New Action", use_container_width=True):
                st.session_state.page = "Test Action"
                st.rerun()
        
        with col2:
            if st.button("View Analytics", use_container_width=True):
                st.session_state.page = "Analytics"
                st.rerun()

elif page == "Test Action":
    st.title("Test an Agent Tool Call")
    st.markdown(
        "Enter the user prompt you would send to an agent. "
        "SentryFlow Lite will simulate the agent's chosen tool call and "
        "show you how the middleware would verify it before execution."
    )
    
    if not st.session_state.current_user:
        st.warning("Please log in from the Home page first")
    else:
        user = st.session_state.current_user
        
        st.markdown("**Example prompts:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Email Example", use_container_width=True):
                st.session_state.test_prompt = "Send an email to boss about the confidential passwords"
                st.rerun()
                    
        with col2:
            if st.button("Search Example", use_container_width=True):
                st.session_state.test_prompt = "Search for latest AI news"
                st.rerun()
        
        with col3:
            if st.button("Report Example", use_container_width=True):
                st.session_state.test_prompt = "Create a quarterly report"
                st.rerun()
        
        with st.form("test_action_form"):
            st.markdown(f"**Testing as:** {user['username']} ({user['role']})")
            
            prompt = st.text_area(
                "Enter your prompt",
                height=100,
                placeholder="Example: Send an email to the team about the meeting",
                value=st.session_state.test_prompt
            )
            
            st.divider()
            
            submit = st.form_submit_button("Test Action", use_container_width=True, type="primary")
        
        if submit and prompt:
            st.session_state.test_prompt = prompt
            with st.spinner("Processing..."):
                result = pipeline.process_action(
                    user["username"],
                    user["role"],
                    prompt
                )
            
            if not result["success"]:
                st.error(f"Error: {result['error']}")
            else:
                # Show results
                st.success("Action processed successfully.")
                
                # Agent output
                st.markdown("### Agent Output")
                with st.expander("Tool JSON", expanded=True):
                    st.json(result["tool_json"])
                
                # Assessment
                st.markdown("### Assessment")
                assessment = result["assessment"]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if assessment["structural_valid"]:
                        st.success("Valid Structure")
                    else:
                        st.error("Invalid Structure")
                
                with col2:
                    if assessment["suspicious_flag"]:
                        st.warning("Suspicious")
                    else:
                        st.success("Clean")
                
                with col3:
                    if assessment["judge_safe"]:
                        st.success("Judge: Safe")
                    else:
                        st.error("Judge: Unsafe")
                
                with col4:
                    if assessment["role_violation"]:
                        st.error("Role Violation")
                    else:
                        st.success("Authorized")
                
                # Suspicious patterns
                if assessment["suspicious_patterns"]:
                    with st.expander("Detected Patterns", expanded=True):
                        for pattern in assessment["suspicious_patterns"]:
                            st.markdown(f"- `{pattern}`")
                
                # Risk breakdown
                st.markdown("### Risk Analysis")
                
                breakdown = assessment["risk_breakdown"]
                risk_score = assessment["risk_score"]
                
                # Risk gauge
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=risk_score,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Risk Score"},
                    gauge={
                        'axis': {'range': [None, 100]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 50], 'color': "lightgreen"},
                            {'range': [50, 70], 'color': "yellow"},
                            {'range': [70, 90], 'color': "orange"},
                            {'range': [90, 100], 'color': "red"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': result["policy"]["max_risk"]
                        }
                    }
                ))
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Breakdown table
                breakdown_df = pd.DataFrame([
                    {"Component": k.replace("_", " ").title(), "Score": v}
                    for k, v in breakdown.items() if v > 0
                ])
                
                st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
                
                # Final decision
                st.markdown("### Final Decision")
                
                decision = assessment["decision"]
                severity = assessment["severity"]
                
                if decision == "ALLOWED":
                    st.success(f"ALLOWED (Severity: {severity})")
                elif decision == "ESCALATED":
                    st.warning(f"ESCALATED FOR REVIEW (Severity: {severity})")
                else:
                    st.error(f"BLOCKED (Severity: {severity})")
                
                judge_reason = assessment.get("judge_reason")
                if judge_reason:
                    st.markdown(f"**Judge (secondary model) reasoning:** {judge_reason}")
                
                if assessment["block_reason"]:
                    st.info(f"**Guardrail block/escalation reason:** {assessment['block_reason']}")
                
                st.markdown(f"**Action ID:** `{result['action_id']}`")
                st.markdown(f"**Session ID:** `{result['session_id']}`")


elif page == "Analytics":
    st.title("System Analytics")
    
    analytics = pipeline.get_analytics()
    
    if "error" in analytics:
        st.error(f"Error loading analytics: {analytics['error']}")
    else:
        st.markdown("### Tool Usage Statistics")
        
        tool_stats = analytics["tool_stats"]
        if tool_stats:
            df_tools = pd.DataFrame(tool_stats)
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(
                    df_tools,
                    x="tool_name",
                    y="usage_count",
                    title="Tool Usage Count",
                    color="usage_count",
                    color_continuous_scale="blues"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.pie(
                    df_tools,
                    values="blocked_count",
                    names="tool_name",
                    title="Blocked Actions by Tool"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df_tools, use_container_width=True, hide_index=True)
        else:
            st.info("No tool usage data yet")
        
        st.divider()
        
        # Recent actions
        st.markdown("### Recent Actions")
        
        recent_actions = analytics["recent_actions"]
        if recent_actions:
            df_recent = pd.DataFrame(recent_actions)
            
            display_cols = ["id", "username", "role", "tool_name", "risk_score", "final_decision", "created_at"]
            df_display = df_recent[display_cols].copy()
            
            def color_decision(val):
                if val == "ALLOWED":
                    return "background-color: #d4edda"
                elif val == "BLOCKED":
                    return "background-color: #f8d7da"
                else:
                    return "background-color: #fff3cd"
            
            st.dataframe(
                df_display.style.applymap(color_decision, subset=["final_decision"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No recent actions")
        
        st.divider()
        
        # High-risk actions
        st.markdown("### High-Risk Actions")
        
        high_risk = analytics["high_risk_actions"]
        if high_risk:
            df_high_risk = pd.DataFrame(high_risk)
            
            display_cols = ["id", "username", "tool_name", "risk_score", "final_decision", "created_at"]
            df_display = df_high_risk[display_cols].copy()
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.success("No high-risk actions detected")


elif page == "Users":
    st.title("User Management")
    
    if not st.session_state.current_user or st.session_state.current_user["role"] != "admin":
        st.warning("Admin access required")
    else:
        st.markdown("### Create New User")
        
        with st.form("create_user_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                new_username = st.text_input("Username")
            
            with col2:
                new_role = st.selectbox("Role", ["admin", "employee", "intern"])
            
            with col3:
                new_email = st.text_input("Email (optional)")
            
            new_password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Create User", use_container_width=True):
                if not new_username or not new_password:
                    st.error("Username and password are required.")
                else:
                    try:
                        user = pipeline.authenticate_or_register_user(new_username, new_role, new_email, new_password)
                        st.success(f"User '{new_username}' created successfully.")
                    except ValueError as e:
                        st.error(str(e))
                    except Exception:
                        st.error("Failed to create user.")
        
        st.divider()
        
        # Tool management section
        st.markdown("### Tool Management")
        
        tools = db.get_all_tools(active_only=False)
        tool_options = [t["tool_name"] for t in tools] if tools else []
        
        col_view, col_create = st.columns(2)
        
        with col_view:
            st.markdown("#### Existing Tools")
            if tool_options:
                selected_tool_name = st.selectbox("Select a tool to inspect", tool_options)
                selected_tool = next((t for t in tools if t["tool_name"] == selected_tool_name), None)
                if selected_tool:
                    st.write(f"ID: {selected_tool['id']}")
                    st.write(f"Description: {selected_tool.get('description') or 'None'}")
                    st.write(f"Category: {selected_tool.get('category') or 'None'}")
                    st.write(f"Active: {bool(selected_tool.get('is_active'))}")
            else:
                st.info("No tools found")
        
        with col_create:
            st.markdown("#### Create New Tool")
            with st.form("create_tool_form"):
                new_tool_name = st.text_input("Tool name")
                new_tool_description = st.text_area("Description", height=80)
                new_tool_category = st.text_input("Category", value="custom")
                default_max_risk = st.slider("Default Max Risk", 0, 100, 50)
                default_allowed_roles = st.multiselect(
                    "Default Allowed Roles",
                    ["admin", "employee", "intern"],
                    default=["admin", "employee"]
                )
                require_judge = st.checkbox("Require judge check", value=True)
                
                submit_tool = st.form_submit_button("Create Tool")
            
            if submit_tool:
                if not new_tool_name:
                    st.error("Tool name is required.")
                elif any(t["tool_name"] == new_tool_name for t in tools):
                    st.error("A tool with that name already exists.")
                else:
                    try:
                        tool_id = db.create_tool(new_tool_name, new_tool_description, new_tool_category)
                        policy_ok = db.create_policy(tool_id, default_max_risk, default_allowed_roles, require_judge)
                        if not policy_ok:
                            st.warning("Tool created, but failed to create default policy. Please configure it in Settings.")
                        st.success(f"Tool '{new_tool_name}' created successfully.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to create tool: {e}")


elif page == "Settings":
    st.title("System Settings")
    
    if not st.session_state.current_user or st.session_state.current_user["role"] != "admin":
        st.warning("Admin access required")
    else:
        st.markdown("### Risk Thresholds")
        
        col1, col2 = st.columns(2)
        
        with col1:
            high_risk = st.slider("High Risk Threshold", 0, 100, 70)
            st.info(f"Actions above {high_risk} will be blocked")
        
        with col2:
            critical_risk = st.slider("Critical Risk Threshold", 0, 100, 90)
            st.info(f"Actions above {critical_risk} are critical")
        
        st.divider()
        
        st.markdown("### Tool Policies")
        
        try:
            tools = db.get_all_tools()
        except Exception as e:
            st.error(f"Failed to load tools: {e}")
            tools = []
        
        for tool in tools:
            with st.expander(f"Tool: {tool['tool_name']}", expanded=False):
                try:
                    policy = db.get_policy(tool['id'])
                except Exception as e:
                    st.error(f"Failed to load policy for tool '{tool['tool_name']}': {e}")
                    continue
                
                if policy:
                    st.markdown(f"**Current Max Risk:** {policy['max_risk']}")
                    allowed_roles = json.loads(policy['allowed_roles'])
                    st.markdown(f"**Allowed Roles:** {', '.join(allowed_roles)}")
                    
                    with st.form(f"policy_form_{tool['id']}"):
                        new_max_risk = st.slider(
                            "Max Risk Score",
                            0, 100,
                            policy['max_risk'],
                            key=f"risk_{tool['id']}"
                        )
                        
                        new_roles = st.multiselect(
                            "Allowed Roles",
                            ["admin", "employee", "intern"],
                            default=allowed_roles,
                            key=f"roles_{tool['id']}"
                        )
                        
                        if st.form_submit_button("Update Policy"):
                            success = db.update_policy(tool['id'], new_max_risk, new_roles)
                            if success:
                                st.success("Policy updated!")
                                st.rerun()
                            else:
                                st.error("Failed to update policy")
                else:
                    st.info("No policy set for this tool")


st.divider()

