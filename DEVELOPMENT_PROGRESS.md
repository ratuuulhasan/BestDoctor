# Best Doctor development progress

## Local release handover

All eight core phases are implemented. The native application uses the existing project database at [localhost:8000](http://127.0.0.1:8000/). The validated Linux Compose stack uses its own local database, media volume, Redis broker, worker and Beat at [localhost:18081](http://127.0.0.1:18081/). No host or domain was provisioned. The optional extensions listed in the original plan remain separate.

Phase 6 completed patient registration, moderated ratings, reporting, support ownership and queues, CMS publishing, contact messages, representative referrals, notification preferences and site settings. Access defaults and starter information pages are installed through migrations. Four cross-role community tests cover those workflows.

Phase 7 added an operations dashboard, daily financial and directory CSV reports, activity counts, database audit triggers, durable email processing and subscription expiry reminders. Redis returned PONG, a Linux Celery worker responded to inspection, and a dispatched report task wrote its result to PostgreSQL. Beat dispatched recurring delivery jobs and the worker completed them. Email delivery defaults to the local console.

Phase 8 verified clean installation, migration consistency and OpenAPI validation. The final suite passed all 58 tests on native PostgreSQL and inside Linux Compose. It includes a single cross-role journey from doctor registration and approval through public discovery, invoice settlement, patient moderation, private ticket handling, audit attribution and profile withdrawal. Headless Chrome checked eight public and account pages at 390, 768 and 1440 pixels, keyboard skip navigation and confirmation dialog cancellation. Both localhost health checks passed.

## Phase 1 — foundation and identity

The repository initially contained the ER diagram. The approved architecture uses a modular Django monolith with one PostgreSQL database, Django templates for the website, DRF for API clients, and Celery with Redis for background work.

Implemented:

- Project settings, environment-generated secrets, PostgreSQL-only runtime and test configuration, local database helpers, and dependency locks.
- Custom email-based user in the first accounts migration. Case-insensitive uniqueness is enforced by PostgreSQL. Django Groups represent the seven ordinary roles, and superuser status represents Super Admin.
- Admin account forms, restricted account administration, session and token authentication, token revocation, request throttling, caller identity endpoint, health check, OpenAPI schema and Swagger UI.
- Local Docker Compose definitions for Django, PostgreSQL, Redis, worker, and Beat.
- Ten tests covering authentication, form validation, unique email, permissions, role initialization, API identity, token revocation, throttling, health and schema.

Native validation used Python 3.13.17, Django 5.2.19, DRF 3.18.3 and PostgreSQL 19.0. Initial migrations applied successfully and the ten PostgreSQL-backed tests passed. The installed PostgreSQL service required credentials, so development and testing used a dedicated cluster on port 55432. Docker Compose and live Redis/Celery execution remain unverified on this workstation.

## Phase history

Phase 2 implemented doctor registration and profile editing, hierarchical locations and specialties, hospital and chamber management, independent chambers, consultation fees, visiting schedules, holidays, and scoped read APIs. Separate through models retain employment dates, specialty priority and per-chamber fees. Schedule writes lock the doctor row to serialize competing updates across chambers. Staff review and public publication are reserved for Phase 3.

The display name is **Best Doctor**, the Python package is `best_doctor`, and the distribution is `best-doctor`. Phase 2 migrations applied to the existing development database. All 23 Django tests passed against PostgreSQL, migration drift checks passed, and OpenAPI validation completed without warnings.

| Phase | Scope | Status |
|---|---|---|
| 2 | Locations, specialties, doctors, hospital affiliations, chamber assignments, schedules and doctor dashboard | Complete |
| 3 | BM&DC evidence, staff decisions, history, publication eligibility | Complete |
| 4 | Public directory, search, locality pages, original responsive interface | Complete |
| 5 | Subscription terms, invoices, settlement, renewals, refunds | Complete |
| 6 | Reviews, moderation, CMS, support, notifications and referrals | Complete |
| 7 | Administrative reporting, API coverage, background delivery and scheduling | Complete |
| 8 | End-to-end verification, responsive checks, local handover | Complete |

Phase 5 added administrator-priced annual and lifetime plans, the doctor billing workspace, scoped financial APIs, a staff reconciliation queue, full refund recording and a local payment simulator. Invoice lines preserve the issued price. Early renewals append a term and replayed settlements reuse the recorded decision. PostgreSQL constraints, transactions and per-doctor row locks protect concurrent purchases, settlements and refunds. Recurring expiry reminders remain scheduled for Phase 7.

All four Phase 5 migrations applied locally. Twelve billing tests passed, including concurrent settlement, conflicting simulated events, access control, amount/currency mismatch, rejected payments, leap-year renewal and full refund replay. All 51 project tests passed on PostgreSQL. The OpenAPI schema validated without warnings, and migration drift and pending-migration checks passed.

Phase 4 added anonymous doctor search, standalone hospital and specialty directories, division and district pages, public doctor profiles with fees, sessions and upcoming closures, and a paginated public search API. HTML and API queries share the Phase 3 publication rules. Seven new tests cover search, combined filters, dated affiliations, privacy, Unicode landing pages and pagination. All 39 PostgreSQL-backed tests passed, the OpenAPI schema validated, and migration checks found no changes. The homepage was inspected at mobile, tablet and desktop sizes. The five main public entry pages fit a 390-pixel emulated mobile viewport without horizontal overflow.

Phase 3 added the private evidence store, reviewer queue, approval and rejection with feedback, resubmission, decision history, authenticated verification APIs and doctor-controlled publication. PostgreSQL invalidates prior evidence when the registration changes. Nine verification tests include competing submissions on separate database connections. All 32 project tests passed on PostgreSQL, both verification migrations applied, and the OpenAPI and migration drift checks passed.

Implement the domain apps with their first functional modules. Preserve explicit doctor–specialty, hospital–doctor, hospital–manager and doctor–chamber relationships. Scope ownership checks in both querysets and mutations. Keep schedule and holiday records on doctor–chamber assignments. Snapshot the registration number for each verification and purchased terms for each subscription. Use atomic workflow changes and idempotent payment events. Optional booking, assistant, rewards, favourites, maps, and localization are deferred.
