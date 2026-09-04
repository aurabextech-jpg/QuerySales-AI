import httpClient from './httpClient';
import { API_BASE, getAuthToken } from './httpClient';

export type StreamEventType =
  | 'run_id'
  | 'agent'
  | 'tool'
  | 'token'
  | 'done'
  | 'error';

export interface StreamEvent {
  type: StreamEventType;
  data: string;
}

export type StreamCallback = (event: StreamEvent) => void;

export const agentApi = {
  initializeWorkflow: async (prompt: string, isSimulation: boolean) => {
    const response = await httpClient.post('/api/runs', {
      workflow_type: 'chat',
      mode: isSimulation ? 'simulation' : 'real',
    });
    return {
      run_id: response.data.id,
      status: response.data.status,
      simulation_mode: response.data.mode === 'simulation',
    };
  },

  chat: async (
    messages: Array<{ role: string; content: string }>,
    runId?: string,
  ) => {
    const response = await httpClient.post('/api/chat', {
      messages,
      run_id: runId,
    });
    return {
      message: response.data.message,
      run_id: response.data.run_id,
    };
  },

  /**
   * POST /api/chat/stream
   *
   * The Vercel Python runtime buffers responses, so the backend returns a
   * structured JSON payload instead of real-time SSE:
   *   {
   *     run_id: string,
   *     status: 'completed' | 'error',
   *     steps:  Array<{ type: 'agent' | 'tool_start' | 'tool_result', ... }>,
   *     message: string
   *   }
   *
   * To preserve the streaming UX in the chat, we replay the steps and stream
   * the final message token-by-token through the same StreamCallback the UI
   * already consumes.
   */
  chatStream: (
    messages: Array<{ role: string; content: string }>,
    onEvent: StreamCallback,
    runId?: string,
  ): (() => void) => {
    let aborted = false;
    const timers: ReturnType<typeof setTimeout>[] = [];

    const wait = (ms: number) =>
      new Promise<void>(resolve => {
        const t = setTimeout(() => resolve(), ms);
        timers.push(t);
      });

    const controller = new AbortController();

    const run = async () => {
      try {
        const token = getAuthToken();
        const res = await fetch(`${API_BASE}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ messages, run_id: runId }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const errText = await res.text().catch(() => '');
          throw new Error(`HTTP ${res.status}: ${errText || res.statusText}`);
        }

        const data = await res.json();
        if (__DEV__) console.log('[chatStream] response:', data);
        if (aborted) return;

        if (data.run_id) {
          onEvent({ type: 'run_id', data: String(data.run_id) });
        }

        const steps: Array<Record<string, any>> = Array.isArray(data.steps)
          ? data.steps
          : [];

        for (const step of steps) {
          if (aborted) return;

          switch (step.type) {
            case 'agent':
              onEvent({ type: 'agent', data: String(step.agent ?? '') });
              await wait(250);
              break;
            case 'tool_start':
              onEvent({ type: 'tool', data: String(step.tool ?? '') });
              await wait(300);
              break;
            case 'tool_result':
              // Surface tool name briefly; final content is delivered via `message`
              if (step.tool) {
                onEvent({ type: 'tool', data: String(step.tool) });
                await wait(150);
              }
              break;
            default:
              break;
          }
        }

        const finalMessage: string = String(data.message ?? '');
        if (finalMessage) {
          // Stream the message word-by-word for a typewriter effect.
          const tokens = finalMessage.split(/(\s+)/);
          for (const tok of tokens) {
            if (aborted) return;
            if (!tok) continue;
            onEvent({ type: 'token', data: tok });
            await wait(20);
          }
        }

        if (!aborted) {
          onEvent({ type: 'done', data: finalMessage });
        }
      } catch (err: any) {
        if (aborted) return;
        const msg =
          err?.name === 'AbortError'
            ? 'Stream aborted.'
            : err?.message || 'Network error during stream.';
        if (__DEV__) console.log('[chatStream] error:', msg);
        onEvent({ type: 'error', data: msg });
      }
    };

    run();

    return () => {
      aborted = true;
      timers.forEach(clearTimeout);
      try {
        controller.abort();
      } catch (_) {
        /* noop */
      }
    };
  },

  executeStep: async (runId: string, action: Record<string, unknown>) => {
    const response = await httpClient.post('/api/chat', {
      messages: [{ role: 'user', content: JSON.stringify(action) }],
      run_id: runId,
    });
    return {
      run_id: runId,
      status: 'in_progress',
      step_result: { success: true, message: response.data.message },
    };
  },

  getTraceLogs: async (runId: string) => {
    const response = await httpClient.get(`/api/workflows/${runId}/logs`);
    return response.data;
  },

  getOutcomeMetrics: async (runId: string) => {
    const response = await httpClient.get(`/api/workflows/${runId}/outcome`);
    return response.data;
  },
};
