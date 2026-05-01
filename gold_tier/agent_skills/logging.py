"""
Compatibility shim — the project spec lists agent_skills/logging.py.
All real implementation lives in audit_logger.py to avoid shadowing the stdlib.
"""

from .audit_logger import AuditLogger  # noqa: F401  re-export

__all__ = ["AuditLogger"]
