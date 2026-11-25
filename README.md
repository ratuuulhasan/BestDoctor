# Best Doctor

Best Doctor is a local-development healthcare directory and management platform for Bangladesh. Doctors can register, manage their professional profiles and set visiting hours and fees. Hospital managers can maintain their assigned facilities. The source ER diagram is `Best Doctor ER Diagram.png`. See [development progress](DEVELOPMENT_PROGRESS.md) for the implementation sequence.

## Doctor and facility workflows

For the verified full-stack preview on this workstation, open [Best Doctor on port 18081](http://127.0.0.1:18081/). Its Compose project is `bestdoctor-acceptance`. Run commands for this instance with `docker compose -p bestdoctor-acceptance`. For example, create its first administrator interactively with `docker compose -p bestdoctor-acceptance exec web python manage.py createsuperuser`. To restart it later, set `$env:BEST_DOCTOR_WEB_PORT='18081'` in PowerShell and run `docker compose -p bestdoctor-acceptance up --build -d`. The native preview on port 8000 continues to use the original development database.

### Public directory

Open the [homepage](http://127.0.0.1:8000/) or [doctor search](http://127.0.0.1:8000/doctors/) without signing in. Visitors can combine a name, specialty or facility keyword with specialty, division, district and hospital filters. A doctor qualifies geographically through an active consulting chamber or a current hospital affiliation. A filtered hospital and district must match the same location. Directory pages are paginated and support Unicode specialty and place slugs.

Doctor profiles show published professional details, active chambers, consultation fees in BDT, recurring local visiting hours, and upcoming closures. The [public doctor API](http://127.0.0.1:8000/api/v1/directory/doctors/) uses the same search and publication rules. Existing clinician APIs and the [signed-in workspace](http://127.0.0.1:8000/workspace/) retain their access controls. A fresh directory shows empty states until administrators add reference data and approved doctors publish their profiles.

The homepage photograph, `frontend/static/frontend/consultation.jpg`, is an original editorial illustration generated with built-in ImageGen. Generation prompt: “Original editorial photograph, landscape 4:3 crop for a Bangladesh healthcare directory. Warm attentive Bangladeshi woman doctor in her thirties in a white coat and teal blouse with stethoscope, listening to a seated patient at the edge of the foreground, softly sunlit contemporary consultation room, muted teal walls, human and candid, no text, logos or signs.”

1. In Django admin, add divisions, districts, upazilas, areas, specialties and hospital types. Add hospitals and chambers as needed. Doctor registration also works with an empty directory.
2. Open [doctor registration](http://127.0.0.1:8000/doctor/register/). Submit a name, email, BM&DC number and password. The account opens its private doctor dashboard. Returning users can [sign in](http://127.0.0.1:8000/login/).
3. Edit the profile and add qualifications, experience, awards, languages, links, specialty assignments and dated hospital affiliations. New profiles await the Phase 3 verification workflow.
4. Choose an existing chamber or create an independent chamber. In the Chambers section set its fee in BDT. Add weekly visiting sessions and date-specific holidays against that assignment. Consecutive sessions may meet at a boundary. Available sessions for the same doctor must have distinct time intervals on the same weekday.
5. For a hospital manager, a superuser assigns the Hospital Manager group and an active HospitalManager record. Open [managed facilities](http://127.0.0.1:8000/manage/hospitals/) to edit the facility and its chambers. A staff user with the Admin group can maintain directory data in Django admin.

Authenticated read endpoints under `/api/v1/` cover divisions, districts, upazilas, areas, specialties, hospitals and chambers. The doctors endpoint returns the signed-in doctor's own active profile. See Swagger for filter parameters. Phase 4 introduces the public directory.

The Django package and Celery target are `best_doctor`. Existing native installations continue using the database and role from their private `.env`. Fresh installations use `best_doctor` for both. For an existing Compose database, run Compose with the original project name using `docker compose -p <original-project-name>` to reuse its named volume.

## Run on this Windows workstation

The workspace has a Python 3.13 virtual environment. Run these commands in PowerShell from the project root. The native database helper starts a dedicated PostgreSQL cluster on loopback port 55432 and can be run again after a restart.

```powershell
.\.venv\Scripts\python.exe scripts\local_env.py
.\.venv\Scripts\python.exe scripts\local_db.py start
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Create a superuser once, interactively, with your own email and password. Open [administration](http://127.0.0.1:8000/admin/), [API documentation](http://127.0.0.1:8000/api/v1/docs/), or the [database health check](http://127.0.0.1:8000/health/). Stop the web process with Ctrl+C. To stop the native database, run `.\.venv\Scripts\python.exe scripts\local_db.py stop`.

On a fresh workstation, install Python 3.13 and PostgreSQL 19 client and server binaries, including `initdb` and `pg_ctl`. Create the environment before running the commands above.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
```

The environment generator writes random local secrets to a new `.env` and preserves existing values on reruns. Native PostgreSQL stores its data and bootstrap credential under `.local`. The native application role owns the development database and can create the disposable Django test database. Keep the workspace on a local, private disk when storing real credentials or data. Git and Docker exclusions do not control OneDrive sync.

## Local Docker Compose alternative

With Docker Compose and a generated `.env`, run:

```powershell
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test
docker compose down
```

If only Docker is installed, first run `docker run --rm -v "${PWD}:/app" -w /app python:3.13-slim python scripts/local_env.py` in PowerShell. Compose starts a separate PostgreSQL volume, Redis, a migration job, Django, a Celery worker, and Beat. Only the web port is exposed, on loopback. Use one web server at a time on port 8000.

## Authentication and roles

### Subscriptions, invoices and payment verification

1. A superuser or a staff member in the Admin group creates an active annual or lifetime plan in [subscription plan administration](http://127.0.0.1:8000/admin/subscriptions/subscriptionplan/). Enter a price in BDT. Plans can be retired by clearing their active flag. Prices are set by the administrator.
2. The doctor opens [billing](http://127.0.0.1:8000/doctor/billing/), selects a plan, and receives an invoice with the plan name, price, and billing cycle captured at checkout. The doctor can cancel an open invoice before a payment is pending, or submit a transfer reference and amount.
3. An authorized staff reviewer opens [payment review](http://127.0.0.1:8000/review/payments/), checks the reference against their transfer record, and confirms the amount received or rejects the attempt with feedback. A rejected attempt permits a new reference on the same invoice. A reviewer cannot reconcile their own payments. Staff access requires the `payments.review_payment` permission, granted to the Admin group by migration.
4. Verification records the payment event, settles the invoice and grants the term in a single transaction. Annual coverage expires on the displayed date, with February 29 anniversaries falling on February 28 in non-leap years. Buying a renewal before expiry schedules it after the last paid term. Lifetime coverage has an open end date. Doctors can inspect their own past invoices, payment events and coverage dates.
5. For a completed full refund, staff select Verified in the payment queue and record the external refund reference and reason. Recording the refund reverses the corresponding subscription term. Other purchased terms retain their dates. Refund recording does not transfer funds. Local subscriptions do not affect the public directory.

The [Swagger UI](http://127.0.0.1:8000/api/v1/docs/) documents `subscription-plans/`, `subscriptions/`, `invoices/` and `payments/` under `/api/v1/`. Use a fresh checkout UUID for each intended purchase and reuse it on retries. Doctor ownership is resolved from authentication. Payment transaction references and event IDs are unique per provider. Only one open order and one pending payment attempt per invoice can exist.

To exercise the simulated provider, create an invoice for a test doctor and use a separate authorized staff account. Replace the placeholders below. Reuse the same reference and event UUID to test a replay.

```powershell
.\.venv\Scripts\python.exe manage.py simulate_payment <invoice-uuid> --reviewer <staff-email> --reference <test-reference> --event <event-uuid> --result verified
```

The simulator writes to the selected local database. The automated tests create isolated fixtures in Django's test database.

### BM&DC verification and profile publication

Doctors can open [registration verification](http://127.0.0.1:8000/doctor/verification/) from their dashboard and upload a legible JPEG or PNG of their registration evidence. Each submission captures the current registration number. The upload limit is 5 MB and 12 megapixels. The application decodes the image, removes metadata, and stores a normalized JPEG in PostgreSQL with its submission. Evidence is accessible through an authenticated download to the owning doctor and authorized reviewers.

Staff in the Admin group, superusers, and staff explicitly granted `verification.review_evidence` can use the [review queue](http://127.0.0.1:8000/review/verification/) from the administration home. Reviewers manually assess the registration evidence. The reviewer records approval or gives a rejection reason that the doctor can read. A doctor can submit new evidence after rejection. The workflow prevents self-approval and concurrent duplicate submissions.

After approval the doctor can publish or withdraw their public profile from the verification page. Changing the BM&DC number invalidates pending or approved evidence and withdraws publication, including for bulk database updates. Previous submissions and decisions remain available in the history. Publishing makes the profile available through both its direct URL and the public directory.

The versioned API supports multipart submission, scoped list/detail, downloads, decisions, and publication controls under `/api/v1/verifications/`. Profile publication is independent of subscription status.

Django sessions support browser sign-in. API clients can POST an email in the `username` field and a password to `/api/v1/auth/token/`. Send the returned token in `Authorization: Token <token>`. GET `/api/v1/me/` returns the caller's public identity fields and email. POST `/api/v1/auth/revoke/` revokes the caller's token. Browser session logout is available in the admin. The login endpoint throttles requests by client address using Django's process-local cache in this foundation.

Super Admin uses Django superuser status. Migrations initialize Admin, Moderator, Doctor, Patient, Hospital Manager, Representative and Support Staff groups. Domain permissions will be assigned when each domain is implemented. Account creation and privilege changes in the user admin require a superuser.

## Verification

### Community and staff workflows

- Patients can [create an account](http://127.0.0.1:8000/patient/register/), submit a rating and comment on a published doctor's profile, and check the decision in their dashboard. Moderator or Admin staff approve or reject reviews through Django admin. Only approved reviews contribute to the displayed score. Signed-in readers can report a published review.
- Manage blog posts, categories, tags, FAQ entries, and About, Privacy and Terms pages in the CMS section of Django admin. Draft and future-dated content is private. Contact submissions are available to authorized staff. The Site settings section controls the contact introduction.
- Signed-in users can [open a support ticket](http://127.0.0.1:8000/support/). Support Staff see the unassigned queue and their own assignments. Claim a ticket before replying. Owners and assigned staff can close or reopen it.
- For a representative, assign the Representative group and an active RepresentativeProfile. The representative can copy their referral code from their workspace. Doctors can enter it during registration. Administrators review referral status.
- The [notification inbox](http://127.0.0.1:8000/notifications/) supports read status and independent email and in-app preferences. Billing, registration review, review moderation, support replies and subscription reminders generate notifications.

### Reports, audit and background processing

Staff in the Admin group can use the [operations dashboard](http://127.0.0.1:8000/operations/) to review queues, today's settlement and refund totals, and download generated daily CSV reports. PostgreSQL audit triggers record committed changes to selected financial, identity, directory, editorial and moderation tables, including bulk changes. Audit entries retain status fields and actor IDs. Private evidence, passwords and message bodies are excluded. Public activity counts use route names without search text or visitor identities.

Start the local Compose stack to run Redis, a worker and a single Beat scheduler. Email delivery is polled every 30 seconds, expiry reminders hourly, and the previous day's report at 00:10 Asia/Dhaka time. The email outbox retries unsent entries up to five times. Separate successful email transmission and database commits mean a process crash can cause a repeat delivery. The default backend writes mail to the worker console. A local SMTP catcher can be selected with `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, and `EMAIL_PORT` in the development environment.

```powershell
docker compose exec redis redis-cli ping
docker compose exec worker celery -A best_doctor inspect ping
docker compose exec web celery -A best_doctor call analytics.tasks.generate_report
docker compose logs --tail=30 worker beat
```

Compose exposes its web server on localhost port 8000. Set `BEST_DOCTOR_WEB_PORT` to run a separate Compose preview alongside the native server. Use the same Compose project name to reconnect to its existing database and media volumes. Rebuild after editing Python or templates. The native and Compose databases are independent. For results that require background processing, use the Compose web application and its database together.

### Scope of this release

All eight core phases target local development. The assistant and appointments app namespaces are reserved for the optional extensions in the architecture plan. Online booking, a generative assistant, referral payouts, favourites, interactive maps, SMS delivery, and Bangla localization are outside the implemented core. BM&DC evidence and manual payments use staff review. The payment simulator, console mail, and test fixtures support local testing without provider credentials.

### Run the checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file .local/schema.yaml
.\.venv\Scripts\python.exe manage.py test
```

Tests use a separate PostgreSQL database. The dependency inputs are in `pyproject.toml`. After changing them, run `uv lock` and `uv export --frozen --no-emit-project --output-file requirements.lock` to refresh both lock files.
