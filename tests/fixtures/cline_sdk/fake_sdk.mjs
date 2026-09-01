import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

export class ClineCore {
  static async create(options = {}) {
    return new ClineCore(options);
  }

  constructor(options) {
    this.options = options;
    this.listeners = new Set();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit(event) {
    for (const listener of this.listeners) listener(event);
  }

  async start(input) {
    if (typeof input.config.systemPrompt !== "string" || !input.config.systemPrompt.trim()) {
      throw new TypeError("systemPrompt is required");
    }
    const sessionId = input.config.sessionId;
    const probe = input.prompt.startsWith("PAEOS_SDK_PROBE:")
      ? JSON.parse(input.prompt.slice("PAEOS_SDK_PROBE:".length))
      : null;
    if (probe?.probe_id === "probe-start-throws") {
      throw new Error("synthetic start failure");
    }
    if (probe?.probe_id === "probe-start-auth-error") {
      const error = new Error("credentials require reauthentication");
      error.name = "OAuthReauthRequiredError";
      throw error;
    }
    let manifestPath = `/profile/sessions/${sessionId}/${sessionId}.json`;
    let messagesPath = `/profile/sessions/${sessionId}/${sessionId}.messages.json`;
    if (probe) {
      const sessionRoot = join(process.env.CLINE_DATA_DIR, "sessions", sessionId);
      await mkdir(sessionRoot, { recursive: true });
      manifestPath = join(sessionRoot, `${sessionId}.json`);
      messagesPath = join(sessionRoot, `${sessionId}.messages.json`);
      await writeFile(
        manifestPath,
        JSON.stringify({
          backend_mode: input.config.backendMode ?? "local",
          capabilities: {
            disable_mcp_settings_tools: input.config.disableMcpSettingsTools,
            enable_agent_teams:
              probe.probe_id === "probe-manifest-capabilities"
                ? true
                : input.config.enableAgentTeams,
            enable_spawn_agent: input.config.enableSpawnAgent,
            enabled_tools: ["editor", "run_commands"],
          },
          messages_path: messagesPath,
          model:
            probe.probe_id === "probe-manifest-model"
              ? "cline-pass/deepseek-v4"
              : input.config.modelId,
          provider:
            probe.probe_id === "probe-manifest-provider"
              ? "other-provider"
              : input.config.providerId,
          session_id:
            probe.probe_id === "probe-manifest-session" ? "other-session" : sessionId,
        }),
      );
      await writeFile(
        messagesPath,
        JSON.stringify({
          messages: [
            {
              modelInfo: { id: input.config.modelId, provider: input.config.providerId },
              role: "assistant",
            },
          ],
          sessionId,
        }),
      );
    }
    if (probe?.probe_id === "probe-early-provider-attempt") {
      await this.options.fetch(new Request("data:application/json,%7B%7D"));
      this.emit({
        type: "session_ended",
        sessionId,
        result: {
          model: { id: input.config.modelId, provider: input.config.providerId },
        },
      });
      return { sessionId, manifestPath, messagesPath };
    }
    if (probe?.probe_id === "probe-ended-event") {
      this.emit({
        type: "ended",
        payload: { sessionId, reason: "completed", ts: Date.now() },
      });
      return {
        sessionId,
        manifestPath,
        messagesPath,
        result: { model: { id: input.config.modelId, provider: input.config.providerId } },
      };
    }
    setTimeout(async () => {
      try {
        if (probe?.probe_id === "probe-timeout-unfinished") {
          await this.options.fetch(new Promise(() => {}));
          return;
        }
        if (probe?.probe_id === "probe-auth-failed") {
          this.emit({
            type: "session_failed",
            sessionId,
            normalizedError: "AUTH_FAILED",
          });
          return;
        }
        await this.options.fetch(
          new Request("data:application/json,%7B%7D", {
            headers: {
              Authorization: "Bearer synthetic-secret-never-serialize",
              "X-Prompt": "private-prompt-never-serialize",
            },
          }),
        );
        if (input.prompt.includes("double-fetch-before-tool")) {
          await this.options.fetch(new Request("data:application/json,%7B%7D"));
        }
        if (probe?.probe_id === "probe-hidden-retry") {
          await this.options.fetch(new Request("data:application/json,%7B%7D"));
        }
        const unauthorized = probe?.probe_id.startsWith("probe-unauthorized-")
          ? probe.probe_id.slice("probe-unauthorized-".length)
          : null;
        const decision = await input.capabilities.requestToolApproval({
          callId: "tool-call-001",
          toolName: unauthorized ?? "editor",
          input: probe
            ? {
                path: probe.artifact_path,
                old_text: probe.initial_text,
                new_text: probe.expected_text,
              }
            : { path: "/sandbox/artifact.txt", old_text: "old", new_text: "new" },
        });
        if (probe && !unauthorized) {
          await this.options.fetch(new Request("data:application/json,%7B%7D"));
          const expansions = {
            cd: `cd / && ${probe.verification_command}`,
            extra: `${probe.verification_command} --extra`,
            pipe: `${probe.verification_command} | true`,
            redirection: `${probe.verification_command} > result.txt`,
            separator: `${probe.verification_command}; true`,
            substitution: `${probe.verification_command} $(whoami)`,
          };
          const expansionKind = probe.probe_id.startsWith("probe-expansion-")
            ? probe.probe_id.slice("probe-expansion-".length)
            : null;
          const verification = await input.capabilities.requestToolApproval({
            callId: "tool-call-002",
            toolName: "run_commands",
            input: { commands: [expansions[expansionKind] ?? probe.verification_command] },
          });
          this.emit({
            type: "session_ended",
            sessionId,
            result: {
              approved: decision.approved && verification.approved,
              model: { id: input.config.modelId, provider: input.config.providerId },
            },
          });
        } else {
          this.emit({ type: "session_ended", sessionId, result: { approved: decision.approved } });
        }
      } catch (error) {
        this.emit({ type: "session_failed", sessionId, errorClass: error.name });
      }
    }, 0);
    return {
      sessionId,
      manifest: { provider: input.config.providerId, model: input.config.modelId },
      manifestPath,
      messagesPath,
    };
  }

  async abort(sessionId) {
    this.emit({ type: "session_aborted", sessionId });
  }

  async stop(sessionId) {
    this.emit({ type: "session_stopped", sessionId });
  }
}
