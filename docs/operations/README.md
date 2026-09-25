# Operations

`GET /room/overview` exposes early workload counts. Workflow events enter a persistent transactional outbox and can be dispatched in development through `/operations/outbox/dispatch` (admin only). PostgreSQL/Redis compose services exist; Redis workers, DLQ and production logging remain next work.
