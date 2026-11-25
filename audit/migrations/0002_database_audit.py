from django.db import migrations


# These tables carry directory, identity, editorial and financial decisions.
# Copy only whitelisted status fields. Never serialize evidence or message bodies.
TABLES = (
    "accounts_user", "accounts_user_groups", "accounts_user_user_permissions",
    "auth_group_permissions", "accounts_representativeprofile", "doctors_doctorprofile",
    "hospitals_hospital", "hospitals_hospitalmanager", "chambers_chamberschedule",
    "verification_doctorverification", "subscriptions_subscriptionplan", "subscriptions_subscription",
    "payments_payment", "payments_invoice", "payments_refund", "reviews_review", "reviews_reviewreport",
    "support_supportticket", "cms_page", "cms_blogpost", "core_sitesetting", "referrals_referral",
)
FUNCTION = """
CREATE FUNCTION best_doctor_audit_row() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    before_state jsonb := '{}'::jsonb;
    after_state jsonb := '{}'::jsonb;
    field text;
    old_row jsonb;
    new_row jsonb;
BEGIN
    IF TG_OP <> 'INSERT' THEN old_row := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN new_row := to_jsonb(NEW); END IF;
    FOREACH field IN ARRAY ARRAY['status','is_staff','is_superuser','is_active','is_verified',
                                 'is_published','published','closed','resolved','user_id','group_id',
                                 'permission_id','assigned_to_id'] LOOP
        IF old_row ? field THEN before_state := before_state || jsonb_build_object(field,old_row->field); END IF;
        IF new_row ? field THEN after_state := after_state || jsonb_build_object(field,new_row->field); END IF;
    END LOOP;
    INSERT INTO audit_auditlog(actor_id, operation, table_name, object_id, changes, created_at)
    VALUES(NULLIF(current_setting('best_doctor.actor', true),'')::bigint, TG_OP, TG_TABLE_NAME,
           COALESCE((new_row->>'id')::bigint,(old_row->>'id')::bigint),
           jsonb_build_object('before',before_state,'after',after_state), CURRENT_TIMESTAMP);
    RETURN NULL;
END;
$$;
CREATE FUNCTION best_doctor_keep_audit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Audit entries are append only' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER keep_audit BEFORE UPDATE OR DELETE ON audit_auditlog
FOR EACH ROW EXECUTE FUNCTION best_doctor_keep_audit();
"""


def grant_reports(apps, schema_editor):
    alias = schema_editor.connection.alias
    group = apps.get_model("auth", "Group").objects.using(alias).get(name="Admin")
    for label, model in [("audit", "auditlog"), ("audit", "activitylog"), ("analytics", "dailyreport")]:
        kind, _ = apps.get_model("contenttypes", "ContentType").objects.using(alias).get_or_create(
            app_label=label, model=model)
        perm, _ = apps.get_model("auth", "Permission").objects.using(alias).get_or_create(
            content_type=kind, codename=f"view_{model}", defaults={"name": f"Can view {model}"})
        group.permissions.add(perm)


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"), ("analytics", "0001_initial"), ("core", "0002_community_setup"),
        ("verification", "0002_registration_guards"), ("payments", "0003_billing_integrity"),
    ]
    operations = [
        migrations.RunPython(grant_reports, migrations.RunPython.noop),
        migrations.RunSQL(
            FUNCTION + "".join(f"CREATE TRIGGER audit_row AFTER INSERT OR UPDATE OR DELETE ON {table} "
                               "FOR EACH ROW EXECUTE FUNCTION best_doctor_audit_row();" for table in TABLES),
            "".join(f"DROP TRIGGER audit_row ON {table};" for table in TABLES)
            + "DROP TRIGGER keep_audit ON audit_auditlog; DROP FUNCTION best_doctor_keep_audit();"
            + "DROP FUNCTION best_doctor_audit_row();",
        ),
    ]
