from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SKELETON_DESIGNER = "skeleton_designer"
    OPERATIONS = "operations"
    VIEWER = "viewer"
