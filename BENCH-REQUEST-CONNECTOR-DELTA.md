PROPRIETARY — CYAN ECLIPSE TECHNOLOGIES LLC · COMPANY INTELLECTUAL PROPERTY

# Cyan Eclipse Voice — connector delta bench request (custom.voice)

(INT — INTERNAL)

## What is being benched

The Voice Core MCP server as previously benched/built (v0.1). This delta covers ONLY the connector layer added 2026-11-11 under step 1 of the MCP/Tools/Connectors commission: the Muse connector at ~/workspace/custom-connectors/custom.voice/, granting the nine read + shadow-pre-flight tools of SCOPE-MATRIX row 4 and withholding the server's five write tools.

## Claims for the delta

- **C1** — Grant exactness: 9 tools granted (8×T0 + send_evaluate T1-shadow); the 5 withheld tools (consent_record_write, consent_revoke, number_enroll, activity_emit, kill_switch_set) are named in list-tools output under withheld_from_connector and in the manifest with reasons — none silent.
- **C2** — Withheld unreachability: attempts to call kill_switch_set and consent_record_write through the connector are refused client-side before any server call — proven by the server receipt ledger count being identical (2) before and after both attempts.
- **C3** — Human-act fences hold: consent-signing and the kill switch (VOI-MCP-SEC-1/2) cannot be reached through this connector at all; the transcript's one consent record was seeded through the server's native surface, labelled as such.
- **C4** — Shadow pre-flight semantics: send_evaluate ALLOW names the consent_record_id a send receipt must carry; an unconsented subject evaluates DENY at the consent stage; no tool in the connector sends or dials anything. Determinism: consent_check is byte-identical via HOME and CMD routes (canonical hash 1da936b9…).

## Evidence on file

- TRANSCRIPT-20261111.md in the connector directory (seed labelled, ALLOW/DENY paths, refusal + ledger-count proof, determinism).
- Client unit tests: 6/6 OK. Server suite at build: 24 tests OK.

## Verdict requested

PASS / PASS-WITH-CONDITIONS / CONCERN / FAIL on the delta claims above. The connector is BUILT bench-pending; no certified or shipped claim is made for it until this delta verdict lands.

```json
{
 "app": "voice",
 "kind": "connector-delta",
 "claims": [
  {
   "id": "C1",
   "claim": "Grant exactness: 9 tools granted (8\u00d7T0 + send_evaluate T1-shadow); the 5 withheld tools (consent_record_write, consent_revoke, number_enroll, activity_emit, kill_switch_set) are named in list-tools output under withheld_from_connector and in the manifest with reasons \u2014 none silent."
  },
  {
   "id": "C2",
   "claim": "Withheld unreachability: attempts to call kill_switch_set and consent_record_write through the connector are refused client-side before any server call \u2014 proven by the server receipt ledger count being identical (2) before and after both attempts."
  },
  {
   "id": "C3",
   "claim": "Human-act fences hold: consent-signing and the kill switch (VOI-MCP-SEC-1/2) cannot be reached through this connector at all; the transcript's one consent record was seeded through the server's native surface, labelled as such."
  },
  {
   "id": "C4",
   "claim": "Shadow pre-flight semantics: send_evaluate ALLOW names the consent_record_id a send receipt must carry; an unconsented subject evaluates DENY at the consent stage; no tool in the connector sends or dials anything. Determinism: consent_check is byte-identical via HOME and CMD routes (canonical hash 1da936b9\u2026)."
  }
 ]
}
```

© Cyan Eclipse Technologies LLC — Proprietary · Company Intellectual Property

