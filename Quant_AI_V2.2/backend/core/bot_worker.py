"""
Compatibility Facade Shim for BotWorker.
Re-exports BotOrchestrator under the canonical name BotWorker to ensure 100%
backwards compatibility for all legacy UI controllers, tests, and audit scripts.
"""

from backend.core.bot_orchestrator import BotOrchestrator, WorkerSignals

# Canonical alias
BotWorker = BotOrchestrator

__all__ = ["BotWorker", "BotOrchestrator", "WorkerSignals"]
