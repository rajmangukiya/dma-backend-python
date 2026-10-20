from enum import StrEnum

from src.users.enums import UserRole


class Permission(StrEnum):
    # Values match the Node API and the frontend's types/permission
    MANAGE_COMPANIES = "companies:manage"  # platform super admin only
    MANAGE_USERS = "users:manage"
    VIEW_DOCUMENT_SKELETONS = "document-skeletons:view"
    MANAGE_DOCUMENT_SKELETONS = "document-skeletons:manage"
    VIEW_JOURNEYS = "journeys:view"
    MANAGE_JOURNEYS = "journeys:manage"  # journeys, segments, documents in segments
    MANAGE_DOCUMENT_DATA = "documents:data"  # uploads and manual field values


_COMPANY_READ = [Permission.VIEW_DOCUMENT_SKELETONS, Permission.VIEW_JOURNEYS]

ROLE_PERMISSIONS: dict[UserRole, list[Permission]] = {
    UserRole.SUPER_ADMIN: [Permission.MANAGE_COMPANIES],
    UserRole.ADMIN: [
        Permission.MANAGE_USERS,
        *_COMPANY_READ,
        Permission.MANAGE_DOCUMENT_SKELETONS,
        Permission.MANAGE_JOURNEYS,
        Permission.MANAGE_DOCUMENT_DATA,
    ],
    UserRole.SKELETON_DESIGNER: [*_COMPANY_READ, Permission.MANAGE_DOCUMENT_SKELETONS],
    UserRole.OPERATIONS: [
        *_COMPANY_READ,
        Permission.MANAGE_JOURNEYS,
        Permission.MANAGE_DOCUMENT_DATA,
    ],
    UserRole.VIEWER: _COMPANY_READ,
}


def permissions_for(role: UserRole) -> list[Permission]:
    return ROLE_PERMISSIONS.get(role, [])
