-- ==========================================
-- CREATE DATABASE
-- ==========================================

CREATE DATABASE IF NOT EXISTS sentryflow;
USE sentryflow;

-- ==========================================
-- USERS TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    role ENUM('admin','employee','intern') NOT NULL,
    email VARCHAR(150),
    password_hash VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- SESSIONS TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    original_prompt TEXT NOT NULL,
    session_status ENUM('active','closed') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (session_status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- TOOLS TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS tools (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tool_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tool_name (tool_name),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- POLICIES TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS policies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tool_id INT NOT NULL,
    max_risk INT NOT NULL DEFAULT 50,
    allowed_roles JSON NOT NULL,
    require_judge_check BOOLEAN DEFAULT TRUE,
    require_approval BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (tool_id) REFERENCES tools(id)
        ON DELETE CASCADE,
    INDEX idx_tool_id (tool_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- AGENT ACTIONS TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS agent_actions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    parameters JSON NOT NULL,
    structural_valid BOOLEAN,
    suspicious_flag BOOLEAN,
    judge_verdict ENUM('SAFE','UNSAFE'),
    risk_score INT,
    final_decision ENUM('ALLOWED','BLOCKED','ESCALATED'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
        ON DELETE CASCADE,
    INDEX idx_session_id (session_id),
    INDEX idx_tool_name (tool_name),
    INDEX idx_risk_score (risk_score),
    INDEX idx_final_decision (final_decision),
    INDEX idx_created_at (created_at),
    INDEX idx_composite_decision (final_decision, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- RISK LOGS TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS risk_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_id INT NOT NULL,
    structural_score INT DEFAULT 0,
    suspicious_score INT DEFAULT 0,
    judge_score INT DEFAULT 0,
    role_violation_score INT DEFAULT 0,
    prompt_injection_score INT DEFAULT 0,
    data_exfiltration_score INT DEFAULT 0,
    total_score INT,
    detected_patterns JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id)
        ON DELETE CASCADE,
    INDEX idx_action_id (action_id),
    INDEX idx_total_score (total_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- BLOCKED ACTIONS TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS blocked_actions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_id INT NOT NULL,
    block_reason TEXT,
    severity ENUM('LOW','MEDIUM','HIGH','CRITICAL'),
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by INT NULL,
    reviewed_at TIMESTAMP NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (action_id) REFERENCES agent_actions(id)
        ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_action_id (action_id),
    INDEX idx_severity (severity),
    INDEX idx_reviewed (reviewed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- AUDIT LOG TABLE (for compliance)
-- ==========================================

CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INT,
    old_value JSON,
    new_value JSON,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_action_type (action_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================
-- SAMPLE DATA FOR TESTING
-- ==========================================

-- Insert Tools
INSERT IGNORE INTO tools (tool_name, description, category)
VALUES
('send_email', 'Send an external email', 'communication'),
('search_web', 'Search information online', 'information'),
('create_report', 'Generate internal report', 'documents'),
('file_upload', 'Upload files to storage', 'files'),
('database_query', 'Query database records', 'data');

-- Insert Users
INSERT IGNORE INTO users (username, role, email)
VALUES
('admin_user', 'admin', 'admin@company.com'),
('employee_user', 'employee', 'employee@company.com'),
('intern_user', 'intern', 'intern@company.com'),
('demo_user', 'employee', 'demo@company.com');

-- Insert Policies
-- send_email → only admin & employee allowed, max risk 40
INSERT IGNORE INTO policies (tool_id, max_risk, allowed_roles, require_judge_check)
SELECT id, 40, '["admin","employee"]', TRUE
FROM tools WHERE tool_name = 'send_email';

-- search_web → all roles allowed, max risk 70
INSERT IGNORE INTO policies (tool_id, max_risk, allowed_roles, require_judge_check)
SELECT id, 70, '["admin","employee","intern"]', FALSE
FROM tools WHERE tool_name = 'search_web';

-- create_report → all roles allowed, max risk 60
INSERT IGNORE INTO policies (tool_id, max_risk, allowed_roles, require_judge_check)
SELECT id, 60, '["admin","employee","intern"]', TRUE
FROM tools WHERE tool_name = 'create_report';

-- file_upload → only admin & employee, max risk 50
INSERT IGNORE INTO policies (tool_id, max_risk, allowed_roles, require_judge_check)
SELECT id, 50, '["admin","employee"]', TRUE
FROM tools WHERE tool_name = 'file_upload';

-- database_query → only admin, max risk 30
INSERT IGNORE INTO policies (tool_id, max_risk, allowed_roles, require_judge_check)
SELECT id, 30, '["admin"]', TRUE
FROM tools WHERE tool_name = 'database_query';

-- ==========================================
-- VIEWS FOR ANALYTICS
-- ==========================================

-- View: User activity summary
CREATE OR REPLACE VIEW user_activity_summary AS
SELECT 
    u.id AS user_id,
    u.username,
    u.role,
    COUNT(DISTINCT s.id) AS total_sessions,
    COUNT(a.id) AS total_actions,
    SUM(CASE WHEN a.final_decision = 'ALLOWED' THEN 1 ELSE 0 END) AS allowed_actions,
    SUM(CASE WHEN a.final_decision = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked_actions,
    SUM(CASE WHEN a.final_decision = 'ESCALATED' THEN 1 ELSE 0 END) AS escalated_actions,
    AVG(a.risk_score) AS avg_risk_score,
    MAX(a.risk_score) AS max_risk_score
FROM users u
LEFT JOIN sessions s ON u.id = s.user_id
LEFT JOIN agent_actions a ON s.id = a.session_id
WHERE u.is_active = TRUE
GROUP BY u.id, u.username, u.role;

-- View: Tool usage statistics
CREATE OR REPLACE VIEW tool_usage_stats AS
SELECT 
    t.id AS tool_id,
    t.tool_name,
    t.category,
    COUNT(a.id) AS usage_count,
    SUM(CASE WHEN a.final_decision = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked_count,
    SUM(CASE WHEN a.final_decision = 'ALLOWED' THEN 1 ELSE 0 END) AS allowed_count,
    AVG(a.risk_score) AS avg_risk_score,
    MAX(a.risk_score) AS max_risk_score
FROM tools t
LEFT JOIN agent_actions a ON t.tool_name = a.tool_name
WHERE t.is_active = TRUE
GROUP BY t.id, t.tool_name, t.category;

-- View: High-risk actions summary
CREATE OR REPLACE VIEW high_risk_actions AS
SELECT 
    a.id AS action_id,
    a.session_id,
    u.username,
    u.role,
    a.tool_name,
    a.risk_score,
    a.final_decision,
    r.detected_patterns,
    b.severity,
    b.block_reason,
    a.created_at
FROM agent_actions a
JOIN sessions s ON a.session_id = s.id
JOIN users u ON s.user_id = u.id
LEFT JOIN risk_logs r ON a.id = r.action_id
LEFT JOIN blocked_actions b ON a.id = b.action_id
WHERE a.risk_score >= 70
ORDER BY a.risk_score DESC, a.created_at DESC;

-- ==========================================
-- STORED PROCEDURES
-- ==========================================

DELIMITER //

-- Procedure: Get user statistics
CREATE PROCEDURE IF NOT EXISTS GetUserStats(IN p_user_id INT)
BEGIN
    SELECT 
        COUNT(DISTINCT s.id) AS total_sessions,
        COUNT(a.id) AS total_actions,
        SUM(CASE WHEN a.final_decision = 'ALLOWED' THEN 1 ELSE 0 END) AS allowed,
        SUM(CASE WHEN a.final_decision = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked,
        SUM(CASE WHEN a.final_decision = 'ESCALATED' THEN 1 ELSE 0 END) AS escalated,
        AVG(a.risk_score) AS avg_risk_score,
        MAX(a.created_at) AS last_action
    FROM sessions s
    LEFT JOIN agent_actions a ON s.id = a.session_id
    WHERE s.user_id = p_user_id;
END //

-- Procedure: Clean old sessions
CREATE PROCEDURE IF NOT EXISTS CleanOldSessions(IN days_old INT)
BEGIN
    DELETE FROM sessions 
    WHERE session_status = 'closed' 
    AND created_at < DATE_SUB(NOW(), INTERVAL days_old DAY);
    
    SELECT ROW_COUNT() AS deleted_count;
END //

DELIMITER ;

-- ==========================================
-- DONE
-- ==========================================
