# Routers package
from .auth import router as auth_router, set_db as set_auth_db
from .members import router as members_router, set_db as set_members_db
from .admin import router as admin_router, set_db as set_admin_db
from .counselor import router as counselor_router, set_db as set_counselor_db
from .courses import router as courses_router, set_db as set_courses_db
from .disputes import router as disputes_router, set_db as set_disputes_db
from .messages import router as messages_router, set_db as set_messages_db
from .credit import router as credit_router, set_db as set_credit_db
from .staff import router as staff_router, set_db as set_staff_db
from .reports import router as reports_router, set_db as set_reports_db
from .content import router as content_router, set_db as set_content_db
from .programs import router as programs_router, set_db as set_programs_db
from .financial_counseling import router as fc_router, set_db as set_fc_db

def initialize_routers(database):
    """Initialize all routers with database reference"""
    set_auth_db(database)
    set_members_db(database)
    set_admin_db(database)
    set_counselor_db(database)
    set_courses_db(database)
    set_disputes_db(database)
    set_messages_db(database)
    set_credit_db(database)
    set_staff_db(database)
    set_reports_db(database)
    set_content_db(database)
    set_programs_db(database)
    set_fc_db(database)

all_routers = [
    auth_router,
    members_router,
    admin_router,
    counselor_router,
    courses_router,
    disputes_router,
    messages_router,
    credit_router,
    staff_router,
    reports_router,
    content_router,
    programs_router,
    fc_router
]
