# ==============================
# logger.py
# ==============================

import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from config import LOG_FILE, LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT

class SentryFlowLogger:
    """Enhanced logger with multiple handlers and structured logging"""
    
    _instances = {}
    
    def __new__(cls, name="sentryflow"):
        if name not in cls._instances:
            cls._instances[name] = super().__new__(cls)
        return cls._instances[name]
    
    def __init__(self, name="sentryflow"):
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT
        )
        console_handler.setFormatter(console_formatter)
        
        # File Handler (Rotating)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT
        )
        file_handler.setFormatter(file_formatter)
        
        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def _format_extra(self, **kwargs):
        """Format extra context information"""
        # Only include non-logging kwargs in the formatted string
        logging_keys = {"exc_info", "stack_info", "extra", "stacklevel"}
        context_kwargs = {k: v for k, v in kwargs.items() if k not in logging_keys}
        if not kwargs:
            return ""
        if not context_kwargs:
            return ""
        return " | " + " | ".join(f"{k}={v}" for k, v in context_kwargs.items())
    
    def info(self, message, **kwargs):
        """Log info level message with optional context"""
        extra_info = self._format_extra(**kwargs)
        # Log message with formatted context only; ignore arbitrary kwargs
        self.logger.info(f"{message}{extra_info}")
    
    def warning(self, message, **kwargs):
        """Log warning level message with optional context"""
        extra_info = self._format_extra(**kwargs)
        self.logger.warning(f"{message}{extra_info}")
    
    def error(self, message, **kwargs):
        """Log error level message with optional context"""
        extra_info = self._format_extra(**kwargs)
        self.logger.error(f"{message}{extra_info}")
    
    def debug(self, message, **kwargs):
        """Log debug level message with optional context"""
        extra_info = self._format_extra(**kwargs)
        self.logger.debug(f"{message}{extra_info}")
    
    def critical(self, message, **kwargs):
        """Log critical level message with optional context"""
        extra_info = self._format_extra(**kwargs)
        self.logger.critical(f"{message}{extra_info}")
    
    def log_action(self, action_id, decision, risk_score, user, tool):
        """Structured logging for actions"""
        self.info(
            f"Action processed",
            action_id=action_id,
            decision=decision,
            risk_score=risk_score,
            user=user,
            tool=tool
        )
    
    def log_blocked(self, action_id, reason, severity, user):
        """Structured logging for blocked actions"""
        self.warning(
            f"Action blocked",
            action_id=action_id,
            reason=reason,
            severity=severity,
            user=user
        )
    
    def log_error_with_context(self, error, context=None):
        """Log error with full context"""
        error_msg = f"Error occurred: {str(error)}"
        if context:
            error_msg += f" | Context: {context}"
        self.error(error_msg, exc_info=True)
    
    # Backward-compatible alias used elsewhere in the codebase
    def error_with_context(self, error, context=None):
        """Alias for log_error_with_context to maintain backward compatibility"""
        self.log_error_with_context(error, context)

# Global logger instance
logger = SentryFlowLogger()

# Convenience functions for backward compatibility
def log_info(message, **kwargs):
    logger.info(message, **kwargs)

def log_warning(message, **kwargs):
    logger.warning(message, **kwargs)

def log_error(message, **kwargs):
    logger.error(message, **kwargs)

def log_debug(message, **kwargs):
    logger.debug(message, **kwargs)

def error_with_context(error, context=None):
    """Module-level convenience wrapper matching existing usage"""
    logger.log_error_with_context(error, context)
