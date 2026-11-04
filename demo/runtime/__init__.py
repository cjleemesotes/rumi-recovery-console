"""Parent-side runtime: storage, child processes, State snapshots, orchestration.

Nothing in this package imports Rumi or ``demo.cashier``; every interaction with
Rumi history happens in a fresh ``demo.worker`` child process. Import the
specific submodule you need; this package exports nothing itself.
"""
