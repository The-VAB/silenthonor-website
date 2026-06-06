# Middleware package
from .auth_middleware import (
    get_current_user,
    get_current_admin,
    get_current_counselor,
    get_current_staff,
    check_brute_force,
    record_failed_attempt,
    clear_failed_attempts,
    set_db as set_auth_db
)
from .logging_middleware import (
    RequestLoggingMiddleware,
    log_audit_event,
    AUDIT_ACTIONS,
    logger,
    set_db as set_logging_db
)

def initialize_middleware(database):
    """Initialize all middleware with database reference"""
    set_auth_db(database)
    set_logging_db(database)
