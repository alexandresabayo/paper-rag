/**
 * Minimal Server-Sent-Events client for a POST-based stream.
 *
 * The browser's native `EventSource` only supports GET requests, so it
 * can't be used against `POST /api/research/query` (ISSUE-015,
 * AGENT_TASKS.md). This is the standard workaround: a manual `fetch` +
 * `ReadableStream` reader that parses the same `event: .../data: ...`
 * framing `EventSource` would have handled for us.
 */

async function streamSse(url, body, onEvent, { signal } = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    let detail = response.statusText;
    try {
      const errBody = await response.json();
      detail = errBody.detail ? JSON.stringify(errBody.detail) : detail;
    } catch {
      /* response wasn't JSON - keep statusText */
    }
    throw new Error(`${response.status} ${detail}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE messages are separated by a blank line.
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const rawMessage = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseMessage(rawMessage);
      if (parsed) onEvent(parsed);
    }
  }
}

function parseMessage(raw) {
  let event = "message";
  const dataLines = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice("data:".length).trim());
  }
  if (!dataLines.length) return null;
  const rawData = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(rawData) };
  } catch {
    return { event, data: rawData };
  }
}

export { streamSse };
