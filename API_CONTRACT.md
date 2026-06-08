# MySlates Sync API Contract

## Attendance
**Endpoint:** POST /attendance/create/
**Required fields:**
- legacy_student_id (string) — e.g. "MS613085"
- status (string) — "present", "absent", "late", "excused", "unknown"
- marked_at (datetime) — ISO format e.g. "2026-06-08T10:00:00Z"

**Optional fields:**
- legacy_teacher_id (string)
- legacy_class_ref (string)
- legacy_subject_ref (string)

## Assignments
**Endpoint:** POST /assignments/create/
...