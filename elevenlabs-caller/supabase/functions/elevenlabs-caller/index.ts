// Supabase Edge Function behind the ElevenLabs agent test caller page.
// Keeps the ElevenLabs API key on the server and requires a passcode,
// because every request to "call" places a real, billed phone call.
//
// Secrets (Supabase dashboard → Edge Functions → Secrets):
//   ELEVENLABS_API_KEY  your ElevenLabs API key
//   APP_PASSCODE        the passcode the page asks for

const API = "https://api.elevenlabs.io/v1/convai";
const API_KEY = Deno.env.get("ELEVENLABS_API_KEY") ?? "";
const PASSCODE = Deno.env.get("APP_PASSCODE") ?? "";
const E164 = /^\+[1-9]\d{6,14}$/;

// Numbers without a "+" are treated as Canada/US (+1): 5145551234 or 15145551234.
function normalizeNumber(raw: string) {
  const s = raw.trim();
  const digits = s.replace(/\D/g, "");
  if (s.startsWith("+")) return "+" + digits;
  if (digits.length === 10) return "+1" + digits;
  if (digits.length === 11 && digits.startsWith("1")) return "+" + digits;
  return "";
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-passcode",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

async function elevenlabs(method: string, path: string, body?: unknown) {
  const res = await fetch(API + path, {
    method,
    headers: { "xi-api-key": API_KEY, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data: any;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  return { status: res.status, data };
}

function errorMessage(data: any): string {
  const d = data?.detail ?? data?.message ?? data;
  if (typeof d === "string") return d;
  if (d?.message) return d.message;
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg;
  return JSON.stringify(d);
}

function constantTimeEqual(a: string, b: string) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function listPhoneNumbers() {
  const { status, data } = await elevenlabs("GET", "/phone-numbers");
  if (status !== 200) throw { status, message: errorMessage(data) };
  return (Array.isArray(data) ? data : data.phone_numbers ?? []).map((p: any) => ({
    id: p.phone_number_id,
    number: p.phone_number,
    label: p.label ?? "",
    provider: p.provider,
    agent_id: p.assigned_agent?.agent_id ?? null,
  }));
}

async function setup() {
  const agents: { id: string; name: string }[] = [];
  let cursor = "";
  do {
    const { status, data } = await elevenlabs(
      "GET",
      `/agents?page_size=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    );
    if (status !== 200) throw { status, message: errorMessage(data) };
    for (const a of data.agents ?? []) agents.push({ id: a.agent_id, name: a.name || a.agent_id });
    cursor = data.has_more ? data.next_cursor ?? "" : "";
  } while (cursor);
  return { agents, phone_numbers: await listPhoneNumbers() };
}

async function call(body: any) {
  const number = normalizeNumber(String(body.to_number ?? ""));
  if (!E164.test(number)) {
    throw { status: 400, message: "Enter a 10-digit number, e.g. 514 555 1234" };
  }
  if (!body.agent_id || !body.phone_number_id) {
    throw { status: 400, message: "Pick an agent and a phone number to call from" };
  }
  const phone = (await listPhoneNumbers()).find((p: any) => p.id === body.phone_number_id);
  if (!phone) throw { status: 400, message: "That phone number no longer exists in ElevenLabs" };
  const endpoint = phone.provider === "sip_trunk" ? "sip-trunk" : "twilio";
  const { status, data } = await elevenlabs("POST", `/${endpoint}/outbound-call`, {
    agent_id: body.agent_id,
    agent_phone_number_id: body.phone_number_id,
    to_number: number,
  });
  if (status !== 200 || data.success === false) {
    throw { status: status === 200 ? 502 : status, message: errorMessage(data) };
  }
  return { conversation_id: data.conversation_id ?? null, message: data.message ?? "" };
}

async function conversation(body: any) {
  const id = String(body.conversation_id ?? "");
  if (!/^[A-Za-z0-9_-]+$/.test(id)) throw { status: 400, message: "Bad conversation id" };
  const { status, data } = await elevenlabs("GET", `/conversations/${id}`);
  if (status !== 200) throw { status, message: errorMessage(data) };
  return {
    status: data.status,
    transcript: (data.transcript ?? [])
      .filter((t: any) => t.message)
      .map((t: any) => ({ role: t.role, message: t.message })),
  };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "Use POST" });
  if (!API_KEY || !PASSCODE) return json(500, { error: "Server is missing its settings" });
  if (!constantTimeEqual(req.headers.get("x-passcode") ?? "", PASSCODE)) {
    return json(401, { error: "Wrong passcode" });
  }
  let body: any;
  try {
    body = await req.json();
  } catch {
    return json(400, { error: "Invalid JSON" });
  }
  try {
    switch (body.action) {
      case "setup":
        return json(200, await setup());
      case "call":
        return json(200, await call(body));
      case "conversation":
        return json(200, await conversation(body));
      default:
        return json(400, { error: "Unknown action" });
    }
  } catch (e: any) {
    if (e?.status) return json(e.status, { error: e.message });
    return json(502, { error: `Could not reach ElevenLabs: ${e?.message ?? e}` });
  }
});
