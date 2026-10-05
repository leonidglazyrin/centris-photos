# ElevenLabs agent test caller

A small local web page for testing an ElevenLabs outbound-calling agent. Type a phone number, press **Call**, and ElevenLabs dials it and runs the agent flow you built in the ElevenLabs portal. The page shows the call status and the transcript as the call goes.

No dependencies: Python 3 only.

## Setup

You need three values from the ElevenLabs portal:

| Variable | Where to find it |
|---|---|
| `ELEVENLABS_API_KEY` | Profile → API keys (the key needs Conversational AI access) |
| `ELEVENLABS_AGENT_ID` | Agents → your agent → the ID under its name (`agent_…`) |
| `ELEVENLABS_PHONE_NUMBER_ID` | Phone Numbers → the number to call from (`phnum_…`). Import a Twilio or SIP-trunk number there first if you don't have one. |

## Run

```bash
export ELEVENLABS_API_KEY=sk_...
export ELEVENLABS_AGENT_ID=agent_...
export ELEVENLABS_PHONE_NUMBER_ID=phnum_...
python3 elevenlabs-caller/server.py
```

Then open http://localhost:8000, enter a number with its country code (e.g. `+1 514 555 1234`) and press **Call**.

## Notes

- Every call is a real phone call and is billed by ElevenLabs and your phone provider.
- The server only listens on `localhost`, because it holds your API key. Don't expose it to the internet as is.
- Twilio and SIP-trunk numbers are both supported; the server detects which one your phone number uses.
- Set `PORT` to use a port other than 8000.
