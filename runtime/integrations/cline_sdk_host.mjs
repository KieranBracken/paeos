#!/usr/bin/env node

import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { isAbsolute } from "node:path";
import { pathToFileURL } from "node:url";

const PROTOCOL_VERSION = "paeos-worker-admission/1";
const MAX_FRAME_BYTES = 1_048_576;

class ProtocolError extends Error {}

function normalizedStartError(error) {
  const name = error instanceof Error ? error.name : "UnknownError";
  const message = error instanceof Error ? error.message : "";
  const text = `${name} ${message}`.toUpperCase();
  if (/AUTH|UNAUTH|OAUTH|CREDENTIAL|TOKEN|KEYCHAIN|SECITEM/.test(text)) {
    return "AUTH_FAILED";
  }
  if (/RATE[ _-]?LIMIT|TOO MANY REQUEST|\b429\b/.test(text)) {
    return "RATE_LIMITED";
  }
  if (/QUOTA|PASSLIMIT|FREE.?MODEL.?LIMIT/.test(text)) {
    return "QUOTA_EXHAUSTED";
  }
  if (/MODEL.*(NOT|UNAVAILABLE)|NOT.*MODEL/.test(text)) {
    return "MODEL_UNAVAILABLE";
  }
  if (/PROVIDER.*(UNAVAILABLE|NOT FOUND)|UNAVAILABLE/.test(text)) {
    return "PROVIDER_UNAVAILABLE";
  }
  return undefined;
}

function stableStringify(value) {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number" && Number.isFinite(value)) return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  throw new ProtocolError("non-JSON value");
}

function exactKeys(value, expected, label) {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (stableStringify(actual) !== stableStringify(wanted)) {
    throw new ProtocolError(`${label} schema mismatch`);
  }
}

class FrameReader {
  constructor(stream) {
    this.iterator = stream[Symbol.asyncIterator]();
    this.buffer = Buffer.alloc(0);
  }

  async exact(size) {
    while (this.buffer.length < size) {
      const { value, done } = await this.iterator.next();
      if (done) throw new ProtocolError("EOF before terminal");
      this.buffer = Buffer.concat([this.buffer, value]);
    }
    const result = this.buffer.subarray(0, size);
    this.buffer = this.buffer.subarray(size);
    return result;
  }

  async read() {
    const header = await this.exact(4);
    const length = header.readUInt32BE(0);
    if (length <= 0 || length > MAX_FRAME_BYTES) throw new ProtocolError("frame size invalid");
    const bytes = await this.exact(length);
    let value;
    try {
      value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    } catch {
      throw new ProtocolError("invalid JSON frame");
    }
    if (value === null || Array.isArray(value) || typeof value !== "object") {
      throw new ProtocolError("frame payload must be object");
    }
    if (stableStringify(value) !== bytes.toString("utf8")) {
      throw new ProtocolError("non-canonical frame");
    }
    return value;
  }
}

function writeFrame(value) {
  const payload = Buffer.from(stableStringify(value), "utf8");
  if (payload.length <= 0 || payload.length > MAX_FRAME_BYTES) {
    throw new ProtocolError("frame size invalid");
  }
  const header = Buffer.alloc(4);
  header.writeUInt32BE(payload.length);
  process.stdout.write(Buffer.concat([header, payload]));
}

async function fileHash(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

function validateStart(message) {
  exactKeys(
    message,
    ["invocation_id", "payload", "protocol_version", "sequence", "type"],
    "start",
  );
  if (
    message.protocol_version !== PROTOCOL_VERSION ||
    message.type !== "start" ||
    message.sequence !== 0 ||
    typeof message.invocation_id !== "string" ||
    !message.invocation_id
  ) {
    throw new ProtocolError("invalid start binding");
  }
  exactKeys(
    message.payload,
    [
      "backend_mode",
      "core_entrypoint",
      "core_sha256",
      "cwd",
      "max_declared_model_turns",
      "model_id",
      "prompt",
      "provider_id",
      "sdk_entrypoint",
      "sdk_sha256",
      "session_id",
    ],
    "start payload",
  );
  const payload = message.payload;
  if (
    payload.backend_mode !== "local" ||
    !Number.isInteger(payload.max_declared_model_turns) ||
    payload.max_declared_model_turns <= 0
  ) {
    throw new ProtocolError("backend or turn contract invalid");
  }
  for (const key of [
    "core_entrypoint",
    "core_sha256",
    "cwd",
    "model_id",
    "prompt",
    "provider_id",
    "sdk_entrypoint",
    "sdk_sha256",
    "session_id",
  ]) {
    if (typeof payload[key] !== "string" || !payload[key]) {
      throw new ProtocolError("start field invalid");
    }
  }
  if (!isAbsolute(payload.sdk_entrypoint) || !isAbsolute(payload.core_entrypoint)) {
    throw new ProtocolError("qualified entrypoint must be absolute");
  }
  return payload;
}

async function main() {
  const reader = new FrameReader(process.stdin);
  const start = await reader.read();
  const config = validateStart(start);
  if (
    (await fileHash(config.sdk_entrypoint)) !== config.sdk_sha256 ||
    (await fileHash(config.core_entrypoint)) !== config.core_sha256
  ) {
    throw new ProtocolError("qualified entrypoint hash mismatch");
  }

  const sdk = await import(pathToFileURL(config.sdk_entrypoint).href);
  const coreModule = await import(pathToFileURL(config.core_entrypoint).href);
  const ClineCore = sdk.ClineCore ?? coreModule.ClineCore;
  if (typeof ClineCore?.create !== "function") throw new ProtocolError("ClineCore unavailable");

  let sequence = 0;
  let commandSequence = 1;
  let currentTurn = 1;
  let attemptOrdinal = 0;
  let terminal = false;
  const invocationId = start.invocation_id;
  const sessionId = config.session_id;
  const emit = (type, payload = {}, includeSession = true) => {
    if (terminal) throw new ProtocolError("post-terminal event");
    const event = {
      invocation_id: invocationId,
      payload,
      protocol_version: PROTOCOL_VERSION,
      sequence: sequence++,
      type,
    };
    if (includeSession) event.session_id = sessionId;
    writeFrame(event);
    if (["terminal", "failure", "cancelled"].includes(type)) terminal = true;
  };

  emit("hello", { host: "cline_sdk_host", host_protocol: 1 }, false);

  const observedFetch = async (input, init) => {
    if (currentTurn > config.max_declared_model_turns) {
      throw new ProtocolError("declared model-turn budget exhausted");
    }
    attemptOrdinal += 1;
    const correlationId = randomUUID();
    const turnId = `turn-${currentTurn}`;
    emit("provider_attempt_started", {
      attempt_ordinal: attemptOrdinal,
      correlation_id: correlationId,
      started_monotonic_ns: process.hrtime.bigint().toString(),
      turn_id: turnId,
    });
    if (attemptOrdinal > 1) {
      emit("provider_attempt_finished", {
        attempt_ordinal: attemptOrdinal,
        correlation_id: correlationId,
        finished_monotonic_ns: process.hrtime.bigint().toString(),
        status_class: "blocked_retry",
        turn_id: turnId,
      });
      throw new ProtocolError("retry budget exhausted");
    }
    try {
      const response = await globalThis.fetch(await input, init);
      emit("provider_attempt_finished", {
        attempt_ordinal: attemptOrdinal,
        correlation_id: correlationId,
        finished_monotonic_ns: process.hrtime.bigint().toString(),
        status_class: `${Math.floor(response.status / 100)}xx`,
        turn_id: turnId,
      });
      return response;
    } catch (error) {
      emit("provider_attempt_finished", {
        attempt_ordinal: attemptOrdinal,
        correlation_id: correlationId,
        finished_monotonic_ns: process.hrtime.bigint().toString(),
        status_class: "transport_error",
        turn_id: turnId,
      });
      throw error;
    }
  };

  let core;
  const forwardTool = async (request) => {
    const callId = request.callId;
    if (typeof callId !== "string" || typeof request.toolName !== "string") {
      throw new ProtocolError("tool request identity missing");
    }
    emit("tool_request", {
      call_id: callId,
      input: request.input ?? {},
      tool_name: request.toolName,
    });
    const response = await reader.read();
    const expectedKeys = [
      "invocation_id",
      "payload",
      "protocol_version",
      "sequence",
      "session_id",
      "type",
    ];
    exactKeys(response, expectedKeys, "tool response");
    if (
      response.protocol_version !== PROTOCOL_VERSION ||
      response.invocation_id !== invocationId ||
      response.sequence !== commandSequence++ ||
      response.session_id !== sessionId
    ) {
      throw new ProtocolError("tool response binding mismatch");
    }
    if (response.type === "cancel") {
      await core.abort(sessionId);
      emit("cancelled", { side_effect_certainty: "UNKNOWN" });
      throw new ProtocolError("cancelled");
    }
    if (response.type !== "tool_response") throw new ProtocolError("duplicate start or command");
    exactKeys(response.payload, ["approved", "call_id", "result"], "tool response payload");
    if (response.payload.call_id !== callId || typeof response.payload.approved !== "boolean") {
      throw new ProtocolError("tool response call mismatch");
    }
    currentTurn += 1;
    attemptOrdinal = 0;
    return { approved: response.payload.approved, result: response.payload.result };
  };

  core = await ClineCore.create({ backendMode: "local", fetch: observedFetch });
  let resolveTerminal;
  const terminalEvent = new Promise((resolve) => {
    resolveTerminal = resolve;
  });
  const unsubscribe = core.subscribe((event) => {
    if (["session_ended", "session_failed"].includes(event?.type)) resolveTerminal(event);
  });
  const capabilities = {
    requestToolApproval: forwardTool,
    toolExecutors: {
      editor: (input) => forwardTool({ callId: randomUUID(), input, toolName: "editor" }),
      run_commands: (input) =>
        forwardTool({ callId: randomUUID(), input, toolName: "run_commands" }),
    },
  };
  let result;
  try {
    result = await core.start({
      capabilities,
      config: {
        cwd: config.cwd,
        disableMcpSettingsTools: true,
        enableAgentTeams: false,
        enableSpawnAgent: false,
        enableTools: true,
        modelId: config.model_id,
        providerId: config.provider_id,
        sessionId,
        systemPrompt:
          "You are the PAEOS implementation worker. Execute only the bound probe task " +
          "through approved tools; never self-ratify, audit, promote, or widen scope.",
      },
      prompt: config.prompt,
      toolPolicies: {
        editor: { autoApprove: false, enabled: true },
        run_commands: { autoApprove: false, enabled: true },
      },
    });
  } catch (error) {
    const dataRoot = process.env.CLINE_DATA_DIR;
    if (typeof dataRoot !== "string" || !isAbsolute(dataRoot)) {
      throw new ProtocolError("profile data root unavailable for start failure");
    }
    const sessionRoot = `${dataRoot}/sessions/${sessionId}`;
    const manifestPath = `${sessionRoot}/manifest.json`;
    const messagesPath = `${sessionRoot}/messages.json`;
    await mkdir(sessionRoot, { recursive: true });
    await writeFile(
      manifestPath,
      JSON.stringify({
        backend_mode: "local",
        capabilities: {
          disable_mcp_settings_tools: true,
          enable_agent_teams: false,
          enable_spawn_agent: false,
          enabled_tools: ["editor", "run_commands"],
        },
        messages_path: messagesPath,
        model: config.model_id,
        provider: config.provider_id,
        session_id: sessionId,
      }),
    );
    await writeFile(messagesPath, JSON.stringify({ messages: [], sessionId }));
    emit("session_created", { manifest_path: manifestPath, messages_path: messagesPath });
    const failurePayload = {
      error_class: error instanceof Error ? error.name : "UnknownError",
    };
    const normalizedError = normalizedStartError(error);
    if (normalizedError !== undefined) {
      failurePayload.normalized_error = normalizedError;
    }
    if (
      error &&
      typeof error === "object" &&
      "normalizedError" in error &&
      typeof error.normalizedError === "string"
    ) {
      failurePayload.normalized_error = error.normalizedError;
    }
    emit("failure", failurePayload);
    return;
  }
  if (result.sessionId !== sessionId) throw new ProtocolError("session identity mismatch");
  emit("session_created", {
    manifest_path: result.manifestPath,
    messages_path: result.messagesPath,
  });
  emit("capability_snapshot", {
    backend_mode: "local",
    disable_mcp_settings_tools: true,
    enable_agent_teams: false,
    enable_spawn_agent: false,
    enabled_tools: ["editor", "run_commands"],
  });

  const ended = await terminalEvent;
  emit("session_snapshot", {
    event_type: ended.type,
    manifest_path: result.manifestPath,
    messages_path: result.messagesPath,
  });
  const terminalPayload = { result: ended.result ?? {}, status: ended.type };
  if (["AUTH_FAILED", "RATE_LIMITED", "QUOTA_EXHAUSTED"].includes(ended.normalizedError)) {
    terminalPayload.normalized_error = ended.normalizedError;
  }
  emit(ended.type === "session_failed" ? "failure" : "terminal", terminalPayload);
  unsubscribe();
  await core.stop(sessionId);
}

main()
  .then(() => {
    process.stdin.destroy();
  })
  .catch((error) => {
    process.stdin.destroy();
    process.stderr.write(`cline-sdk-host:${error.name}\n`);
    process.exitCode = 1;
  });
