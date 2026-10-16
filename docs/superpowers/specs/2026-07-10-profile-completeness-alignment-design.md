# Profile Completeness Alignment Design

## Goal

Make every backend consumer use the same definition of profile completeness:
a standard profile dimension is filled only when it contains meaningful content.
The normalized placeholder `{ "status": "unknown", "evidence": [] }` is not
meaningful content.

## Scope

- Move the meaningful-dimension predicate and completeness calculation into
  `backend.app.services.profile_schema` so they have one authoritative home.
- Use that shared calculation in both the profile API and cockpit aggregation.
- Update the persistence API regression expectation for a one-dimension update
  from six filled dimensions and 100% to one filled dimension and 16.7%.
- Add regression coverage proving placeholder dimensions are excluded and the
  profile and cockpit views report the same percentage.
- Add a development-log entry under `开发日志` after implementation and
  verification.

## Data Flow

1. Incoming updates are normalized to the fixed six-dimension schema.
2. Missing dimensions remain present as explicit `unknown` placeholders.
3. The shared helper inspects all six standard dimensions and counts only
   meaningful values.
4. Profile API returns `filled_dimensions`, `total_dimensions`, and rounded
   `completeness` from the shared result.
5. Cockpit uses the same shared result for its `completeness` field.

Meaningful dictionary content is any non-placeholder field, a non-`unknown`
status, or non-empty evidence. Non-empty strings and other truthy scalar values
remain meaningful for backward compatibility.

## Error and Compatibility Behavior

- Empty profiles still report 0% completeness.
- Fully populated demo profiles still report 100%.
- Legacy fields continue to be normalized and mapped exactly as before.
- Response shapes and schema version do not change.

## Tests

- Unit tests for empty placeholders, status/evidence content, and substantive
  dictionary fields.
- Persistence API test expects `1 / 6` and `16.7%` after updating only
  `knowledge_base`.
- Cockpit regression test feeds the same normalized one-dimension profile and
  expects `16.7%`.
- Run the focused profile/cockpit tests, then the complete `tests/b` suite if
  the focused checks pass.
