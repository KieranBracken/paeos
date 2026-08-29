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
    const sessionId = input.config.sessionId;
    setTimeout(async () => {
      try {
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
        const decision = await input.capabilities.requestToolApproval({
          callId: "tool-call-001",
          toolName: "editor",
          input: { path: "/sandbox/artifact.txt", old_text: "old", new_text: "new" },
        });
        this.emit({ type: "session_ended", sessionId, result: { approved: decision.approved } });
      } catch (error) {
        this.emit({ type: "session_failed", sessionId, errorClass: error.name });
      }
    }, 0);
    return {
      sessionId,
      manifest: { provider: input.config.providerId, model: input.config.modelId },
      manifestPath: `/profile/sessions/${sessionId}/manifest.json`,
      messagesPath: `/profile/sessions/${sessionId}/messages.json`,
    };
  }

  async abort(sessionId) {
    this.emit({ type: "session_aborted", sessionId });
  }

  async stop(sessionId) {
    this.emit({ type: "session_stopped", sessionId });
  }
}
