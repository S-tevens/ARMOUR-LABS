# Plain-language incident explanations

Every incident card shows an **In plain words** summary above the raw evidence. It says what happened, why the system thinks so and what the next step is, in a few short sentences.

## Two writers, one input

| Writer | When | Network needed |
|---|---|---|
| **Template** | Always available. Used when there is no key, when Gemini does not answer, or when its answer fails the checks below | No |
| **Gemini** | Only when `GEMINI_API_KEY` is set | Yes |

Both see only the incident's own data: severity, classification, status, affected devices, which detectors raised an alert, and the evidence lines. Nothing else about the system is sent. The data is simulated, so no real grid or personal data leaves the machine.

The card always says who wrote the text ("Generated from the evidence below" or "Written by Gemini (model) from the evidence below") and reminds the reader to check it against the evidence. A small Gemini mark appears beside that line only when Gemini wrote the text.

## Guard rails on the Gemini answer

- The instructions tell it to use only the supplied facts, to invent no numbers, devices, causes or actions, and to say plainly when the cause is unknown.
- Every number in its answer must already appear in the facts. If one does not, the answer is rejected and the template is shown.
- The call runs in the background. The page shows the template at once and swaps in the Gemini text when it arrives (usually a few seconds, longer when the model is busy).
- One call per incident state (a change of status, classification or evidence count counts as a new state). After a failed attempt it does not retry for 45 seconds.
- Several models are tried in turn if one is busy or unavailable.

It is an explanation of the evidence, not a new detection. It does not change any score or classification.

## Setup

Set the key in your own terminal before starting the backend. Never put it in a file in the repo.

```powershell
$env:GEMINI_API_KEY = "your-key"
uvicorn main:app --port 8000
```

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | not set | Turns on Gemini. Without it only the template is used |
| `GEMINI_MODEL` | `gemini-flash-latest`, then `gemini-3.8-flash`, then `gemini-3.5-flash-lite` | Use one specific model instead |

Model names change often, and some become unavailable to new keys. The list above can be overridden without a code change.

## API

`GET /incidents/{id}/explanation?district=...` and `GET /city/incidents/{id}/explanation` return
`{text, source ("template" | "gemini"), model, pending, gemini_configured, note?}`. `pending` is true while a Gemini answer is on its way.
