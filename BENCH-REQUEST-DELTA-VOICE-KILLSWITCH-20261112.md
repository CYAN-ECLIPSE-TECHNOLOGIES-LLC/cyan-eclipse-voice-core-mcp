PROPRIETARY — CYAN ECLIPSE TECHNOLOGIES LLC · COMPANY INTELLECTUAL PROPERTY

(INT — INTERNAL) BENCH REQUEST — DELTA — Cyan Eclipse Voice Core MCP — kill-switch owner gate (RockEmSockEm FND-a091616531)

Date: 2026-11-12 · Requester: fix lane (owner commission 2026-11-12 21:06 PT) · Subject build: eclipse-voice-core-mcp @ 0334a7e (droplet maintenance home == GitHub origin/main) · Prior subject: the Voice Core MCP server as benched at 8efbf7e (connector delta, 2026-11-11/12) · Scope of this delta: ONE tool's actor gate. Nothing else in the server changed.

Finding closed by this delta: RockEmSockEm FND-a091616531 (INV-VOICE-KILL-001, CWE-862) — kill_switch_set disengaged the family freeze with no owner token. Disposition walk state: CONFIRMED (RockEm receipts 1703-1705, 2026-11-13T05:13Z). Slate: VOICE-18 (Cyan Eclipse Voice project).

Claims for judgement

VKS-C1. Tokenless kill_switch_set is refused in BOTH directions (engage and disengage), the refusal is receipted (kill_switch_refused), and the freeze state is unchanged.
VKS-C2. A wrong owner token is refused in both directions, receipted, state unchanged.
VKS-C3. The correct owner token engages and disengages the switch; the success receipt (kill_switch_set) records actor "owner" and never the credential.
VKS-C4. A server with no owner credential configured refuses every kill-switch change (fail-closed), receipted with reason owner_token_not_configured.
VKS-C5. The credential is never persisted: it appears in no state file, fixture, or receipt (checked by byte scan of the receipt ledger after owner-path calls).
VKS-C6. Freeze semantics unchanged: what the freeze blocks (send paths under an engaged family switch) and the 2026-11-11 mid-call teardown ruling are untouched by this delta — the only change is the actor gate on kill_switch_set, plus its schema/description and the tools-manifest inputs line.

Evidence

E1. Reproduction (pre-fix, RockEmSockEm test copy over stdio, scratch state): tokenless kill_switch_set {engaged:true} succeeded (receipt_seq 1); tokenless {engaged:false} succeeded (receipt_seq 2); final state disengaged. The defect, observed before any code change.
E2. Reproduce-first tests: tests/test_voice_core.py class KillSwitchOwnerGate (4 tests naming FND-a091616531) — red against the pre-fix server (1 failure + 3 errors), green post-fix. Full suite post-fix: 28/28 OK (baseline 24 + 4 new); python3 smoke.py: SMOKE PASSED.
E3. End-to-end stdio probes against the refreshed RockEm test copy of the FIXED build: (A) unconfigured server — engage attempt refused KILL_SWITCH_OWNER_TOKEN_NOT_CONFIGURED, state unchanged, one kill_switch_refused receipt; (B) credential configured — tokenless engage refused REQUIRED, wrong-token engage refused INVALID, owner-token engage OK, tokenless disengage refused REQUIRED, wrong-token disengage refused INVALID, owner-token disengage OK (receipt_seq 6); receipt types in order: refused, refused, set, refused, refused, set.
E4. RockEmSockEm: test copy refreshed to 0334a7e, build record advanced (changeset server.py, tests/test_voice_core.py, tools-manifest.json), fingerprint re-derived at commit 0334a7e. The engine CLI would not force the target off cadence (not due in schedule, delta, and change trigger modes); its own re-probe of INV-VOICE-KILL-001 rides the next scheduled cycle (timer, 6h cadence). Named here so the bench does not read E3 as an engine verdict.
E5. Diff of record: commit 0334a7e (3 files, +146/−24 across server.py, tests/test_voice_core.py, tools-manifest.json). core_engine.py untouched.

Design note for the judge: the credential follows the server's existing environment pattern (ECLIPSE_VOICE_CORE_STATE precedent) as ECLIPSE_VOICE_CORE_OWNER_TOKEN, compared in constant time. A refusal emits its receipt BEFORE raising, and the server's persist-on-error-only-if-receipts-grew rule keeps the refusal durable while no other state moves. The Muse connector manifest already classes kill_switch_set as a human act, not granted (SCOPE-MATRIX row 4); this gate is the server-side enforcement of that same fence, and it binds every stdio caller, not only the connector.

Requested verdict class: delta bench of VKS-C1..C6 at fixture/test-instance scope.

© Cyan Eclipse Technologies LLC — Proprietary · Company Intellectual Property
