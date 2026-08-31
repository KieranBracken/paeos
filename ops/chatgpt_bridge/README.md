# Retired GUI bridge

The former browser-driven bridge is retired and intentionally fail-closed.  Its old polling,
remote-debugging, clipboard, and frontmost-terminal behavior could not bind a response to a
transaction or provide durable PAEOS evidence.  The entrypoints in this directory now exit with
status `2` before performing any external side effect.

Do not start these helpers and do not add them to cron.  Use the canonical state-root-bound
control plane instead:

```bash
PYTHONPATH=. uv run python ops/control_plane_watchdog.py \
  --state-root /path/to/state-root
```

The watchdog is a run-once, read-only observer.  It emits a JSON recovery proposal; a coordinator
must validate the fencing token, transaction state, and evidence before applying any transition.
For interactive PAEOS work, use the protocol-backed runtime in
`runtime/integrations/chat_bridge.py`, which writes through the immutable bridge transaction
store rather than targeting whichever terminal happens to be focused.

`cline_wrapper.sh` is retained only as historical output-capture tooling.  It is not a control
plane and must not be used to transmit prompts or responses.
