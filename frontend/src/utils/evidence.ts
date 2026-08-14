import type { EvidenceRecord, ReplayEvent } from "../api/client";
import { asRecord, textual } from "./presentation";

export function recordAtOrBefore(
  events: ReplayEvent[],
  cursor: number,
  evidenceType: string,
): EvidenceRecord | null {
  for (let index = Math.min(cursor, events.length - 1); index >= 0; index -= 1) {
    const evidence = events[index]?.evidence;
    if (evidence?.evidence_type === evidenceType) return evidence;
  }
  return null;
}

export function valveCommandAtOrBefore(
  events: ReplayEvent[],
  cursor: number,
): EvidenceRecord | null {
  for (let index = Math.min(cursor, events.length - 1); index >= 0; index -= 1) {
    const evidence = events[index]?.evidence;
    if (evidence?.evidence_type !== "protocol_semantic_event") continue;
    if (textual(asRecord(evidence.payload).point_id) === "control_valve_command_percent")
      return evidence;
  }
  return null;
}

export function evidenceByType(events: ReplayEvent[], type: string): EvidenceRecord | null {
  return events.find((item) => item.evidence?.evidence_type === type)?.evidence ?? null;
}
