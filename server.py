#!/usr/bin/env python3
"""Eclipse Voice Core MCP — v0.1.0, phase V0 (Consent Registry +
Number Registry).

Powered by Cyan Eclipse Technologies (cetech.ai).

Descriptor: Eclipse Voice Core — the Consent Registry and Number
Registry every Eclipse telephony adapter obeys.

Family descriptor: one Consent Registry and Number Registry
govern every call and text across carriers, business phone
systems, and AI voice platforms. No adapter dials or sends
without a consent record with provenance and an Agent Wallet
mandate; revocation propagates to every adapter instantly. It
never touches emergency services, never spoofs a caller ID,
never fabricates consent, and never lets an AI voice pretend to
be a human.

This server owns (spec eclipse-voice-family-spec-20261025
sections 5-8):
  * the Consent Registry — provenance-bound records (a record
    without provenance is VOID), one-way revocation that
    propagates at check time, DNC overlays + calling windows as
    versioned data with provenance;
  * the Number Registry — enrolled numbers only (unenrolled =
    nonexistent), per-number registration state (A2P 10DLC,
    toll-free verification, STIR/SHAKEN, branded ID) deciding
    sendability per channel/scope;
  * the send gate — consent first, then the Wallet-shaped
    mandate; a receipt carrying a consent_record_id is writable
    only when consent ALLOWs, otherwise the attempt produces a
    violation record and nothing else (spec 8.3);
  * the family receipt ledger — append-only, hash-chained;
  * the family kill switch — owner-gated in both directions:
    kill_switch_set changes state only for a call carrying the
    owner credential (env ECLIPSE_VOICE_CORE_OWNER_TOKEN, never
    persisted); refused attempts are receipted as
    kill_switch_refused and change nothing (FND-a091616531).

ADAPTER SEAM (V0 fixture form, stated plainly): adapters import
core_engine from this directory and evaluate against the SHARED
family state file, loaded fresh at every call. Adapters hold no
consent copies, so a revocation lands everywhere at the next
check. The production form is a live registry service behind
this same tool surface (V1, behind the owner Twilio account +
counsel gate).

V0 SCOPE: fixtures only. No carrier account, no real numbers, no
calls placed, no texts sent, and no certification claimed —
bench pending.

Transport: MCP over stdio (newline-delimited JSON-RPC 2.0),
stdlib only. State: $ECLIPSE_VOICE_CORE_STATE or
./data/state.json beside this file, seeded from fixtures.json.
"""
import hmac
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import core_engine as eng  # noqa: E402
from core_engine import ToolError  # noqa: E402

STATE_PATH = Path(os.environ.get(
    "ECLIPSE_VOICE_CORE_STATE", HERE / "data" / "state.json"))
FIXTURES_PATH = HERE / "fixtures.json"

# The family kill switch is owner-gated (FND-a091616531): the
# owner credential lives only in the server process environment
# under this name — never in state, fixtures, or receipts.
OWNER_TOKEN_ENV = "ECLIPSE_VOICE_CORE_OWNER_TOKEN"


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    state = eng.empty_state()
    seed = json.loads(FIXTURES_PATH.read_text())
    state["config"].update(seed.get("config", {}))
    state["dnc_lists"] = seed.get("dnc_lists", [])
    state["windows"] = seed.get("windows", [])
    for rec in seed.get("numbers", []):
        state["numbers"][rec["number_id"]] = rec
    save_state(state)
    return state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))


# ------------------------------------------------------------------- tools
def t_consent_check(state, args):
    return eng.consent_check(state, args["subject"], args["channel"],
                             args["scope"], args.get("at_time"))


def t_consent_record_write(state, args):
    return eng.consent_record_write(state, args)


def t_consent_revoke(state, args):
    return eng.consent_revoke(state, args)


def t_consent_history(state, args):
    return eng.consent_history(state, args["subject"])


def t_dnc_status(state, args):
    return eng.dnc_status(state, args.get("subject"),
                          args.get("at_time"))


def t_window_check(state, args):
    return eng.window_check(state, args.get("jurisdiction"),
                            args["channel"], args["scope"],
                            args.get("at_time"))


def t_number_list(state, args):
    return {"numbers": [eng.number_public(r)
                        for r in state["numbers"].values()],
            "count": len(state["numbers"])}


def t_number_get(state, args):
    rec = eng.find_number(state, args["number_ref"])
    if rec is None:
        raise ToolError(
            f"NUMBER_NOT_ENROLLED: {args['number_ref']} does not "
            "exist to this family (spec 6)")
    return {"number": eng.number_public(rec)}


def t_number_enroll(state, args):
    return eng.number_enroll(state, args)


def t_number_health_report(state, args):
    if args.get("number_id") and args["number_id"] not in state["numbers"]:
        raise ToolError(f"NUMBER_NOT_ENROLLED: {args['number_id']}")
    return eng.number_health_report(state, args.get("number_id"))


def t_send_evaluate(state, args):
    return eng.send_evaluate(
        state, channel=args["channel"], from_ref=args["from_ref"],
        subject=args["subject"], scope=args["scope"],
        platform=args.get("platform", "twilio"),
        mandate=args.get("mandate"),
        estimated_cost=args.get("estimated_cost", 0),
        at_time=args.get("at_time"),
        confirm_token=args.get("confirm_token"))


def t_activity_emit(state, args):
    return eng.activity_emit(state, args)


def t_kill_switch(state, args):
    engaged = bool(args.get("engaged"))
    # Owner gate (FND-a091616531): engaging and disengaging alike
    # require the owner credential. A freeze anyone can lift is
    # not a freeze; a freeze no one can set in an emergency is
    # its own hazard — the owner is the actor for both. Refused
    # attempts are receipted and change nothing.
    expected = os.environ.get(OWNER_TOKEN_ENV, "")
    provided = args.get("owner_token")
    if not expected:
        eng.emit_receipt(state, "kill_switch_refused", {
            "engaged": engaged, "scope": "family",
            "reason": "owner_token_not_configured"})
        raise ToolError(
            "KILL_SWITCH_OWNER_TOKEN_NOT_CONFIGURED: this server "
            f"has no owner credential in ${OWNER_TOKEN_ENV}; "
            "kill-switch changes are refused until one is set")
    if not isinstance(provided, str) or not provided:
        eng.emit_receipt(state, "kill_switch_refused", {
            "engaged": engaged, "scope": "family",
            "reason": "owner_token_missing"})
        raise ToolError(
            "KILL_SWITCH_OWNER_TOKEN_REQUIRED: kill_switch_set "
            "requires the owner credential (owner_token)")
    if not hmac.compare_digest(provided, expected):
        eng.emit_receipt(state, "kill_switch_refused", {
            "engaged": engaged, "scope": "family",
            "reason": "owner_token_invalid"})
        raise ToolError(
            "KILL_SWITCH_OWNER_TOKEN_INVALID: the supplied "
            "owner_token does not match the owner credential")
    state["config"]["family_kill_switch"] = engaged
    receipt = eng.emit_receipt(state, "kill_switch_set",
                               {"engaged": engaged, "scope": "family",
                                "actor": "owner"})
    return {"family_kill_switch": engaged,
            "receipt_seq": receipt["seq"]}


def t_receipt_list(state, args):
    limit = args.get("limit")
    receipts = state["receipts"]
    if limit is not None:
        receipts = receipts[-int(limit):]
    return {"receipts": receipts, "count": len(state["receipts"]),
            "chain_valid": eng.verify_receipt_chain(state["receipts"])}


TOOLS = {
    "consent_check": (
        t_consent_check,
        "Decide whether one subject may be contacted on one channel "
        "for one scope right now — the single consent verdict every "
        "telephony adapter must use. Use before any call or text; "
        "use send_evaluate instead when a send also needs mandate "
        "and number checks. Read-only: writes nothing, no receipt. "
        "The verdict layers, in order: a governing provenance-bearing "
        "consent record (a record without provenance is void and "
        "never authorizes; broader scopes do not imply narrower ones "
        "— the governing record is matched by scope rank), DNC "
        "overlay (the internal list binds every scope; national/state "
        "lists bind marketing and conversational; stale DNC data "
        "denies marketing checks), and the calling window for "
        "marketing/conversational scopes (an unknown timezone counts "
        "as outside and denies). Channels are voice, sms, voice+sms; "
        "scopes are transactional, conversational, marketing. "
        "at_time (ISO 8601) defaults to now. Returns the verdict "
        "object: decision ALLOW or DENY, a machine-readable reason, "
        "consent_record_id when a record governs, and dnc_check / "
        "window_check sub-verdicts when those layers ran.",
        {"subject": {"type": "string", "description": "Who would be contacted — the identifier consent records are keyed by (phone number or subject id, as recorded)."},
         "channel": {"type": "string", "description": "voice, sms, or voice+sms. A voice+sms record covers either single channel."},
         "scope": {"type": "string", "description": "transactional, conversational, or marketing — the purpose class of the contact."},
         "at_time": {"type": "string", "description": "ISO 8601 evaluation time for window and DNC-freshness checks; defaults to now."}},
        ["subject", "channel", "scope"]),
    "consent_record_write": (
        t_consent_record_write,
        "Write a NEW consent record into the Consent Registry. Use "
        "when consent was captured from a person through a real "
        "channel; use consent_revoke to end consent and "
        "consent_check to query it. Mutating and persistent: stores "
        "the record as active and appends a hash-chained receipt. "
        "Provenance is mandatory — the provenance object must carry "
        "at least one non-empty key among url, document_ref, "
        "call_ref, form_id; a write without provenance is refused, "
        "nothing is stored, and the attempt is receipted as a "
        "violation. Records are never edited after writing: a "
        "duplicate (same subject, channel, scope, captured_at, "
        "source) is refused as already existing. channel must be "
        "voice, sms, or voice+sms; scope transactional, "
        "conversational, or marketing; source one of web_form, "
        "signed_doc, recorded_call, in_person, platform_import, "
        "other. Returns {consent, receipt_seq} with the assigned "
        "consent_id.",
        {"subject": {"type": "string", "description": "Who consented — the identifier future consent_check calls will use."},
         "channel": {"type": "string", "description": "voice, sms, or voice+sms."},
         "scope": {"type": "string", "description": "transactional, conversational, or marketing."},
         "purpose": {"type": "string", "description": "The purpose as captured, verbatim capture context. Required."},
         "source": {"type": "string", "description": "Capture channel: web_form, signed_doc, recorded_call, in_person, platform_import, or other. Required."},
         "captured_at": {"type": "string", "description": "ISO 8601 time consent was captured. Required and must parse."},
         "provenance": {"type": "object", "description": "Evidence of capture; must include at least one non-empty of url, document_ref, call_ref, form_id or the write is refused as void."},
         "method_detail": {"type": "object", "description": "How capture happened (form text shown, script version), stored as supplied."},
         "jurisdiction_hint": {"type": "string", "description": "Jurisdiction used for calling-window evaluation on later checks."},
         "recorded_by": {"type": "string", "description": "Who or what recorded the consent; defaults to 'operator' in the record history."}},
        ["subject", "channel", "scope", "purpose", "source",
         "captured_at", "provenance"]),
    "consent_revoke": (
        t_consent_revoke,
        "Revoke consent — one record by consent_id, or every active "
        "record for a subject when consent_id is omitted. Use the "
        "moment a person opts out, by any channel; use "
        "consent_record_write for new consent and consent_history "
        "to inspect the trail. Mutating, persistent, and receipted. "
        "Revocation is total and one-way: there is no un-revoke, "
        "and re-consent requires a brand-new record with new "
        "provenance via consent_record_write. Because adapters hold "
        "no consent copies, the revocation takes effect at the next "
        "consent_check everywhere. revocation_source is required "
        "and must be one of opt_out_keyword, voice_request, "
        "dnc_match, owner_action, carrier_signal. Returns "
        "{revoked, receipt_seq} listing the consent_ids revoked.",
        {"consent_id": {"type": "string", "description": "Revoke exactly this record; omit to revoke all active records for subject."},
         "subject": {"type": "string", "description": "Revoke every active record for this subject (used when consent_id is omitted)."},
         "revocation_source": {"type": "string", "description": "opt_out_keyword, voice_request, dnc_match, owner_action, or carrier_signal. Required."}},
        ["revocation_source"]),
    "consent_history": (
        t_consent_history,
        "Read the full consent trail for one subject: every record "
        "ever written for them, each with its append-only status "
        "history (recorded, revoked events). Use to audit a "
        "subject's consent before a send decision or an opt-out "
        "dispute; use consent_check when you need a verdict rather "
        "than the trail. Read-only. Records are returned sorted by "
        "captured_at, including revoked ones — history is never "
        "rewritten. Returns {subject, records, count}.",
        {"subject": {"type": "string", "description": "Subject identifier exactly as recorded by consent_record_write."}}, ["subject"]),
    "dnc_status": (
        t_dnc_status,
        "Read the Do-Not-Contact overlay datasets loaded in this "
        "registry — each list's id, kind, version, provenance, and "
        "freshness — and, when subject is given, whether that "
        "subject matches a list. Use to check DNC data health "
        "before relying on marketing consent checks; use "
        "consent_check for a full contact verdict (it applies DNC "
        "as one layer). Read-only. There is deliberately no tool "
        "that removes a subject from a DNC list. at_time (ISO 8601, "
        "default now) drives the freshness evaluation. Returns the "
        "dataset status object, with a subject match section when "
        "subject is supplied.",
        {"subject": {"type": "string", "description": "Optional subject identifier to test against the loaded lists."},
         "at_time": {"type": "string", "description": "ISO 8601 evaluation time for list freshness; defaults to now."}},
        []),
    "window_check": (
        t_window_check,
        "Evaluate whether contacting at at_time falls inside the "
        "legal calling window for a jurisdiction, channel, and "
        "scope, from the registry's versioned jurisdiction rule "
        "data. Use for a window-only question; use consent_check "
        "for the full verdict (it runs this check itself for "
        "marketing and conversational scopes). Read-only. An "
        "unknown jurisdiction or timezone is treated as outside "
        "the window — the safe answer is the returned answer, with "
        "reason unknown_timezone. jurisdiction may be omitted, in "
        "which case no rule can match and the result is outside. "
        "Returns {inside, reason, ...} naming the rule evaluated.",
        {"jurisdiction": {"type": "string", "description": "Jurisdiction code the rule data is keyed by, e.g. a state or country code as loaded in the fixtures."},
         "channel": {"type": "string", "description": "voice, sms, or voice+sms. Required."},
         "scope": {"type": "string", "description": "transactional, conversational, or marketing. Required."},
         "at_time": {"type": "string", "description": "ISO 8601 time to evaluate; defaults to now."}},
        ["channel", "scope"]),
    "number_list": (
        t_number_list,
        "List every enrolled number in the Number Registry with "
        "its registration state and its per-channel/per-scope "
        "sendability matrix. Use to see what sending identities "
        "exist; use number_get for one number and "
        "number_health_report for spam-label and blocking detail. "
        "Read-only, takes no parameters. Unenrolled numbers do not "
        "exist to this server family — a number absent here cannot "
        "send, and send_evaluate denies it by name. Returns "
        "{numbers, count}.",
        {}, []),
    "number_get": (
        t_number_get,
        "Fetch one enrolled number by number_id or by E.164 "
        "number, with registration state and the sendability "
        "matrix. Use when you know the number's id or E.164; use "
        "number_list to browse the registry. Read-only. An "
        "unenrolled reference is an error (NUMBER_NOT_ENROLLED), "
        "not an empty result — unenrolled numbers do not exist to "
        "this family. Returns {number}.",
        {"number_ref": {"type": "string", "description": "A number_id (e.g. 'num_...') or the full E.164 string (e.g. '+15551234567')."}}, ["number_ref"]),
    "number_enroll": (
        t_number_enroll,
        "Enroll a phone number into the Number Registry (operator "
        "act, fixture form in this build). Use when a number is "
        "provisioned on a platform and must become sendable "
        "subject to its registration state; use number_get or "
        "number_list to read the registry. Mutating, persistent, "
        "and receipted. This registers the number locally only — "
        "it provisions nothing with any carrier; live provisioning "
        "is a separate adapter surface not in this build. e164 "
        "must be E.164 ('+' followed by digits) and unique in the "
        "registry; capabilities must be drawn from voice_in, "
        "voice_out, sms_in, sms_out, mms, fax. Registration "
        "defaults describe an unregistered number (A2P 10DLC "
        "unregistered, branded ID not enrolled), which is NOT "
        "sendable for most scopes until registration data says "
        "otherwise. Returns {number, receipt_seq} with the public "
        "number view including its sendability matrix.",
        {"e164": {"type": "string", "description": "The number in E.164 format, e.g. '+15551234567'. Required; must start with '+' followed by digits only."},
         "number_id": {"type": "string", "description": "Registry id to assign; defaults to a hash-derived 'num_...' id from the e164."},
         "platform": {"type": "string", "description": "Platform the number lives on; defaults to 'twilio'."},
         "account_ref": {"type": "string", "description": "Platform account reference the number belongs to."},
         "capabilities": {"type": "array",
                          "items": {"type": "string"}, "description": "Subset of voice_in, voice_out, sms_in, sms_out, mms, fax."},
         "owner_purpose": {"type": "string", "description": "What the number is for; defaults to 'support'."},
         "registration": {"type": "object", "description": "Registration state object: a2p_10dlc {brand_state, campaign_state, linked}, toll_free_verification, stir_shaken, branded_id. Missing pieces default to unregistered states."},
         "spam_labels": {"type": "array",
                         "items": {"type": "object"}, "description": "Known spam-label observations to seed the number's health record."},
         "status": {"type": "string", "description": "Registry status; defaults to 'active'."}}, ["e164"]),
    "number_health_report": (
        t_number_health_report,
        "Report spam-label observations, registration state, and "
        "exactly what is send-blocked and why — for one number by "
        "number_id, or fleet-wide when number_id is omitted. Use "
        "to diagnose why a number cannot send; use number_get for "
        "the plain registry record. Read-only and reporting-only: "
        "this tool never suggests evading spam labels or carrier "
        "filtering. An unenrolled number_id is an error "
        "(NUMBER_NOT_ENROLLED). Returns {numbers, count}.",
        {"number_id": {"type": "string", "description": "Restrict the report to this enrolled number_id; omit for every enrolled number."}}, []),
    "send_evaluate": (
        t_send_evaluate,
        "Evaluate — never execute — a proposed send through both "
        "gates in order and return the verdict an adapter must "
        "obey. Gate order: family kill switch, then a live "
        "consent_check, then Number Registry enrollment and "
        "sendability for from_ref, then the mandate (Agent "
        "Wallet-shaped: expiry, platform allowlist, destination "
        "allowlist, cost cap, approval threshold). Use before any "
        "adapter sends; use consent_check alone for a consent-only "
        "question. This tool sends nothing and places no call — it "
        "returns a decision only — but it is not side-effect free: "
        "every evaluation appends a hash-chained receipt, and a "
        "consent failure additionally writes a violation record. "
        "Decisions: ALLOW (carries the consent_record_id the "
        "eventual send receipt must carry, plus send_ref), DENY "
        "(with the stage that stopped it: kill_switch, consent, "
        "number, or mandate, and a machine-readable reason), or "
        "APPROVAL_REQUIRED when estimated_cost exceeds the "
        "mandate's approval_threshold — re-call with confirm_token "
        "set to the returned confirm_token_form ('confirm-send-' + "
        "send_ref) to complete the evaluation. platform defaults "
        "to 'twilio'; estimated_cost defaults to 0.",
        {"channel": {"type": "string", "description": "voice, sms, or voice+sms."},
         "from_ref": {"type": "string", "description": "Sending number: an enrolled number_id or E.164. Unenrolled senders are denied at the number stage."},
         "subject": {"type": "string", "description": "Recipient identifier, exactly as consent records key it."},
         "scope": {"type": "string", "description": "transactional, conversational, or marketing."},
         "platform": {"type": "string", "description": "Sending platform name, checked against the mandate's platform allowlist; defaults to 'twilio'."},
         "mandate": {"type": "object", "description": "Wallet-shaped mandate object: mandate_id, expires_at (ISO 8601, required inside the object — a mandate without a future expiry is denied), platforms[], destinations[], cap, approval_threshold. Omitting the mandate entirely is a mandate-stage DENY."},
         "estimated_cost": {"type": "number", "description": "Estimated send cost in the mandate's currency units, compared against cap and approval_threshold; defaults to 0."},
         "at_time": {"type": "string", "description": "ISO 8601 evaluation time for consent window/DNC and mandate expiry; defaults to now."},
         "confirm_token": {"type": "string", "description": "For an APPROVAL_REQUIRED verdict, re-call with the exact token the verdict returned ('confirm-send-<send_ref>')."}},
        ["channel", "from_ref", "subject", "scope"]),
    "activity_emit": (
        t_activity_emit,
        "Record one normalized telephony activity event — call, "
        "sms, or voicemail — as the emission door into the "
        "Customer Graph. Use when an adapter handled (or tried to "
        "handle) an activity; blocked attempts emit too, with "
        "disposition blocked_consent or blocked_window, so the "
        "record shows refusals as well as completions. Mutating, "
        "persistent, and receipted. References only, never media: "
        "pass recording_ref / transcript_ref identifiers, not "
        "audio or text content. kind must be call, sms, or "
        "voicemail; direction inbound or outbound; disposition one "
        "of answered, missed, voicemail, failed, blocked_consent, "
        "blocked_window. Returns {activity, receipt_seq} with the "
        "assigned activity_id.",
        {"kind": {"type": "string", "description": "call, sms, or voicemail."},
         "direction": {"type": "string", "description": "inbound or outbound."},
         "occurred_at": {"type": "string", "description": "ISO 8601 time the activity occurred. Required."},
         "parties": {"type": "object", "description": "Who was involved (from/to identifiers), stored as supplied."},
         "platform_ref": {"type": "object", "description": "Platform reference for the activity (platform + its native id). Required."},
         "duration_s": {"type": "number", "description": "Duration in seconds for calls; omit for sms."},
         "disposition": {"type": "string", "description": "answered, missed, voicemail, failed, blocked_consent, or blocked_window."},
         "recording_ref": {"type": "string", "description": "Identifier of the recording, if any — a reference, never the media itself."},
         "transcript_ref": {"type": "string", "description": "Identifier of the transcript, if any — a reference, never the text itself."},
         "consent_ref": {"type": "string", "description": "consent_record_id the activity relied on, when applicable."},
         "receipt_ref": {"type": "string", "description": "Related send receipt reference, when applicable."}},
        ["kind", "direction", "occurred_at", "platform_ref",
         "disposition"]),
    "kill_switch_set": (
        t_kill_switch,
        "Set the family-wide kill switch for all telephony sends. "
        "Use to freeze sending across every adapter instantly "
        "(engaged=true) or to release the freeze (engaged=false). "
        "Owner-gated: every call, engaging or disengaging, must "
        "carry owner_token matching the owner credential the "
        "server process holds (env ECLIPSE_VOICE_CORE_OWNER_TOKEN); "
        "a call with no owner_token, a wrong one, or any call "
        "while no credential is configured is refused with a "
        "KILL_SWITCH_OWNER_TOKEN error, receipted as "
        "kill_switch_refused, and changes nothing. Mutating, "
        "persistent, and receipted on success. While engaged, "
        "every send_evaluate returns DENY at the kill_switch "
        "stage; read-only tools (consent history, number "
        "registry, receipts) keep working. The switch does not "
        "delete or alter consent records or numbers. Returns "
        "{family_kill_switch, receipt_seq}.",
        {"engaged": {"type": "boolean", "description": "true engages the freeze; false releases it."},
         "owner_token": {"type": "string", "description": "The owner credential for the kill switch, checked against the server process's ECLIPSE_VOICE_CORE_OWNER_TOKEN. Required for every call, engaging or disengaging; never stored in state or receipts."}}, ["engaged", "owner_token"]),
    "receipt_list": (
        t_receipt_list,
        "List the family receipt ledger — append-only, "
        "hash-chained receipts for consent writes and revocations, "
        "number enrollments, send evaluations, violation records, "
        "activity emissions, and kill-switch changes — and report "
        "whether the chain still verifies. Use to audit what "
        "happened across the family; there is no per-receipt get "
        "tool. Read-only. limit returns only the most recent N "
        "receipts while count always reports the full ledger "
        "length. Returns {receipts, count, chain_valid}.",
        {"limit": {"type": "integer", "description": "Return only the most recent N receipts; omit for the whole ledger."}}, []),
}

# Capability denylist, stated in code (spec 10): this core holds
# no emergency-services surface, no caller-ID surface, and no
# consent-editing surface at any tier.
FORBIDDEN_TOOL_NAMES = {
    "emergency_call", "e911_config", "e911_address_write",
    "test_911", "caller_id_set", "caller_id_spoof",
    "display_name_set", "consent_edit", "consent_unrevoke",
    "consent_fabricate", "dnc_remove", "number_release",
}


def tool_list():
    return [{"name": name, "description": description,
             "inputSchema": {"type": "object", "properties": props,
                             "required": required}}
            for name, (_, description, props, required) in TOOLS.items()]


def handle(req: dict):
    method, rid = req.get("method", ""), req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": req.get("params", {}).get(
                "protocolVersion", "2025-03-26"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "eclipse-voice-core",
                           "version": "0.1.0"}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"tools": tool_list()}}
    if method == "tools/call":
        name = req["params"]["name"]
        args = req["params"].get("arguments", {})
        if name in FORBIDDEN_TOOL_NAMES or name not in TOOLS:
            return {"jsonrpc": "2.0", "id": rid, "error": {
                "code": -32602,
                "message": f"unknown or line-forbidden tool {name}"}}
        state = load_state()
        receipts_before = len(state["receipts"])
        try:
            out = TOOLS[name][0](state, args)
            save_state(state)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text",
                             "text": json.dumps(out, indent=1)}]}}
        except ToolError as exc:
            # A refused write may still have receipted a violation
            # (consent_record_write, spec 5.2): persist exactly that
            # growth, nothing else.
            if len(state["receipts"]) > receipts_before:
                save_state(state)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text",
                             "text": json.dumps({"error": str(exc)})}],
                "isError": True}}
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid, "error": {
            "code": -32601, "message": f"method not found: {method}"}}
    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle(json.loads(line))
        except Exception as exc:  # never crash the transport
            response = {"jsonrpc": "2.0", "id": None, "error": {
                "code": -32603, "message": str(exc)}}
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
