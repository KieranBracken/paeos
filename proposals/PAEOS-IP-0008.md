# PAEOS-IP-0008: Universal WorkerTransport Architecture & MCP Namespace Hygiene

**Status:** PROPOSED / RATIFIED BY FOUNDER  
**Author:** Co-Lead Architectural Review & Antigravity  
**Date:** 2026-07-31  

---

## 1. Problem Statement

1. **Namespace Collision**:  
   The current top-level `mcp/` directory in the repository collides with the official Python `mcp` SDK (`import mcp`), creating import ambiguity between local PAEOS MCP servers and third-party MCP SDK dependencies.

2. **Vendor Coupling Risk**:  
   Directly coupling PAEOS Phase 3 / R5 self-hosting runs to Anthropic's MCP SDK or Claude CLI violates PAEOS's core architectural principle: **every external technology must be an adapter, never a core dependency**. PAEOS is an operating system for *any* worker runtime (Claude, Gemini, GPT, local LLMs, SSH workers, Docker, remote humans).

---

## 2. Proposed Architecture

### A. Namespace Hygiene
Rename the local `mcp/` directory to:
```text
runtime/transports/mcp/
```
This clearly demotes MCP from a top-level subsystem to a transport adapter within `runtime/`.

### B. Universal `WorkerTransport` Protocol
Define a vendor-agnostic abstraction for worker interaction in `runtime/transport.py`:

```python
from typing import Protocol, Optional
from runtime.task_package import TaskPackage, TaskResult

class WorkerTransport(Protocol):
    def submit(self, task_package: TaskPackage) -> str:
        """Submit a task package to a worker, returning a dispatch/session ID."""
        ...

    def status(self, dispatch_id: str) -> str:
        """Check status of a dispatched task."""
        ...

    def receive(self, dispatch_id: str) -> Optional[TaskResult]:
        """Receive the result artifact and evidence from a worker."""
        ...
```

---

## 3. R5 Subtask Sequencing (R5.1 → R5.2 → R5.3)

1. **R5.1 (Transport Abstraction & File Transport)**:
   - Rename `mcp/` to `runtime/transports/mcp/`.
   - Introduce `WorkerTransport` protocol in `runtime/transport.py`.
   - Move existing file-based evidence/task execution behind `FileWorkerTransport`.
   - Zero vendor SDK dependencies added to core.

2. **R5.2 (Claude CLI Transport)**:
   - Wrap `runtime/claude_code.py` (`ClaudeCodeRuntime`) as `ClaudeCliWorkerTransport` implementing `WorkerTransport`.

3. **R5.3 (MCP Transport)**:
   - Implement `McpWorkerTransport` in `runtime/transports/mcp/` using the official `mcp` SDK as an isolated transport adapter.

---

## 4. Invariants Preserved
- **K1 / FR-3**: Strict gate verification unaffected (Court and Adversary adjudicate evidence identically regardless of transport).
- **Z0/Z1 Frozen**: Kernel untouched (F2-SOFT).
- **Universal Worker Independence**: Runtime depends solely on `WorkerTransport`, never on vendor SDKs or specific CLI tools.
