from django.db import migrations


def grant_review(apps, schema_editor):
    alias = schema_editor.connection.alias
    types = apps.get_model("contenttypes", "ContentType").objects.using(alias)
    kind, _ = types.get_or_create(app_label="verification", model="doctorverification")
    permission, _ = apps.get_model("auth", "Permission").objects.using(alias).get_or_create(
        content_type=kind, codename="review_evidence",
        defaults={"name": "Can review private registration evidence"},
    )
    group = apps.get_model("auth", "Group").objects.using(alias).get(name="Admin")
    group.permissions.add(permission)


# Registration changes can originate from admin forms, imports or bulk updates.
# Invalidate the old approval in the same transaction as the identity change.
GUARD = """
CREATE FUNCTION best_doctor_registration_guard() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.user_id <> NEW.user_id AND EXISTS (
            SELECT 1 FROM verification_doctorverification WHERE doctor_id = NEW.id
        ) THEN
            RAISE EXCEPTION 'A profile with verification evidence cannot change owners.'
                USING ERRCODE = '23514';
        END IF;
        IF OLD.bmdc_number IS DISTINCT FROM NEW.bmdc_number THEN
            INSERT INTO verification_verificationhistory
                (verification_id, old_status, new_status, remarks, created_at, actor_id)
            SELECT id, status, 'superseded', 'Registration identity changed.', CURRENT_TIMESTAMP, NULL
            FROM verification_doctorverification
            WHERE doctor_id = NEW.id AND status IN ('pending', 'approved');

            UPDATE verification_doctorverification SET status = 'superseded'
            WHERE doctor_id = NEW.id AND status IN ('pending', 'approved');
            NEW.is_verified := FALSE;
            NEW.is_published := FALSE;
        END IF;
    END IF;

    IF NEW.is_verified AND NOT EXISTS (
        SELECT 1 FROM verification_doctorverification
        WHERE doctor_id = NEW.id AND registration_number = NEW.bmdc_number AND status = 'approved'
    ) THEN
        NEW.is_verified := FALSE;
    END IF;
    IF NOT NEW.is_active OR NOT NEW.is_verified THEN
        NEW.is_published := FALSE;
    END IF;
    RETURN NEW;
END;
$body$;
CREATE TRIGGER registration_guard BEFORE INSERT OR UPDATE ON doctors_doctorprofile
FOR EACH ROW EXECUTE FUNCTION best_doctor_registration_guard();
UPDATE doctors_doctorprofile SET is_verified = FALSE, is_published = FALSE
WHERE is_verified OR is_published;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("verification", "0001_initial"),
        ("accounts", "0002_directory_admin_permissions"),
    ]
    operations = [
        migrations.RunPython(grant_review, migrations.RunPython.noop),
        migrations.RunSQL(GUARD, """
            DROP TRIGGER registration_guard ON doctors_doctorprofile;
            DROP FUNCTION best_doctor_registration_guard();
        """),
    ]
