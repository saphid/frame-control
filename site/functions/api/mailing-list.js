// Private signup storage on the existing Cloudflare Pages site. No email sender
// or third-party mailing account is needed to collect explicit opt-ins.
import { hashIp } from "../../lib/feedback.js";

export const UPDATE = `INSERT INTO mailing_list (subscriber_id, rev, email)
  VALUES (?, ?, ?)
  ON CONFLICT(subscriber_id) DO UPDATE SET rev = excluded.rev,
    email = excluded.email, updated_at = CURRENT_TIMESTAMP
  WHERE excluded.rev > mailing_list.rev`;

const json = (status, data) => new Response(JSON.stringify(data), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});

export async function onRequestPost({ request, env }) {
  // This endpoint is called by the app's Python server, never a browser form.
  // Reject cross-site browser submissions instead of enabling CORS.
  if (request.headers.has("origin")) return json(403, { error: "Use Frame Control's mailing list setting." });
  if (!env.MAILING_LIST) return json(503, { error: "Mailing list storage is not configured yet." });
  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    return json(415, { error: "Send JSON." });
  }
  let input;
  try {
    const reader = request.body?.getReader();
    if (!reader) return json(400, { error: "Send JSON." });
    const chunks = [];
    let length = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > 2048) {
        await reader.cancel();
        return json(413, { error: "Request too large." });
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    input = JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return json(400, { error: "Send JSON." });
  }
  if (!input || typeof input.token !== "string" || !/^[a-f0-9]{64}$/.test(input.token) ||
      !Number.isSafeInteger(input.rev) || input.rev < 1 ||
      typeof input.email !== "string" || typeof input.updates !== "boolean") {
    return json(400, { error: "Invalid mailing list choice." });
  }
  const email = input.email.trim();
  if ((input.updates && (!email || email.length > 254 || !/^[^@\s]+@[^@\s]+\.[^@\s.]+$/.test(email))) ||
      (!input.updates && email)) {
    return json(400, { error: "An email needs explicit opt-in; withdraw with an empty email." });
  }
  try {
    // Reuse the site's existing rate-limit namespace and secret salt. Never
    // store raw IP addresses, email addresses, or capabilities in rate-limit keys.
    if (env.FEEDBACK_RL && env.GITHUB_TOKEN) {
      const who = await hashIp(request.headers.get("cf-connecting-ip") || "unknown", env.GITHUB_TOKEN);
      const key = `mailing:ip:${who}:${Math.floor(Date.now() / 3600e3)}`;
      const count = Number(await env.FEEDBACK_RL.get(key)) || 0;
      if (count >= 30) return json(429, { error: "Please try again later." });
      await env.FEEDBACK_RL.put(key, String(count + 1), { expirationTtl: 3900 });
    }
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input.token));
    const id = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
    await env.MAILING_LIST.prepare(UPDATE).bind(id, input.rev, email || null).run();
    return json(200, { ok: true });
  } catch {
    // No address, token, request body, or storage error details in logs/responses.
    return json(503, { error: "Couldn't save just now. Frame Control will retry." });
  }
}

export const onRequest = () => json(405, { error: "POST only." });
