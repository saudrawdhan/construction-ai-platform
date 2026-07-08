from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    EXECUTIVE = "executive"
    PROJECT_MANAGER = "project_manager"
    SITE_ENGINEER = "site_engineer"
    PROCUREMENT_OFFICER = "procurement_officer"
    QA_QC = "qa_qc"
    VIEWER = "viewer"


ALL_ROLES: list[str] = [role.value for role in Role]
