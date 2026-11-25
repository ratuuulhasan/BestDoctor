from django.db import migrations


def grant_billing_permissions(apps, schema_editor):
    db = schema_editor.connection.alias
    admin = apps.get_model("auth", "Group").objects.using(db).get(name="Admin")
    types = apps.get_model("contenttypes", "ContentType").objects.using(db)
    permissions = apps.get_model("auth", "Permission").objects.using(db)
    for app, model, codes in (
        ("payments", "payment", ("review_payment",)),
        ("subscriptions", "subscriptionplan", ("add_subscriptionplan", "change_subscriptionplan", "view_subscriptionplan")),
    ):
        content, _ = types.get_or_create(app_label=app, model=model)
        for code in codes:
            perm, _ = permissions.get_or_create(content_type=content, codename=code,
                                               defaults={"name": code.replace("_", " ").capitalize()})
            admin.permissions.add(perm)


# Invoice lines and decision history are accounting snapshots.
IMMUTABLE = (
    "payments_invoiceitem", "payments_paymentevent", "payments_refund",
    "subscriptions_subscriptionhistory",
)
INSTALL = """
CREATE FUNCTION best_doctor_ledger_readonly() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Issued ledger entries are immutable' USING ERRCODE = '23514';
END;
$$;
CREATE FUNCTION best_doctor_invoice_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.doctor_id <> (SELECT doctor_id FROM subscriptions_subscription WHERE id=NEW.subscription_id) THEN
        RAISE EXCEPTION 'Invoice owner must match subscription' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND (to_jsonb(OLD) - 'status') <> (to_jsonb(NEW) - 'status') THEN
        RAISE EXCEPTION 'Issued invoice terms are immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_invoice BEFORE INSERT OR UPDATE ON payments_invoice
FOR EACH ROW EXECUTE FUNCTION best_doctor_invoice_guard();
CREATE FUNCTION best_doctor_payment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(OLD) - 'status' - 'paid_at') <> (to_jsonb(NEW) - 'status' - 'paid_at') THEN
        RAISE EXCEPTION 'Payment references and amounts are immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_payment BEFORE UPDATE ON payments_payment
FOR EACH ROW EXECUTE FUNCTION best_doctor_payment_guard();
CREATE FUNCTION best_doctor_term_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.doctor_id, NEW.plan_id, NEW.billing_cycle) IS DISTINCT FROM
       (OLD.doctor_id, OLD.plan_id, OLD.billing_cycle)
       OR (OLD.status IN ('paid', 'refunded') AND
           (NEW.start_date, NEW.end_date) IS DISTINCT FROM (OLD.start_date, OLD.end_date)) THEN
        RAISE EXCEPTION 'Purchased terms cannot be rewritten' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_subscription BEFORE UPDATE ON subscriptions_subscription
FOR EACH ROW EXECUTE FUNCTION best_doctor_term_guard();
CREATE FUNCTION best_doctor_billing_owner_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.user_id <> OLD.user_id AND EXISTS (SELECT 1 FROM payments_invoice WHERE doctor_id=OLD.id) THEN
        RAISE EXCEPTION 'A profile with invoices cannot change owners' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_billing_owner BEFORE UPDATE OF user_id ON doctors_doctorprofile
FOR EACH ROW EXECUTE FUNCTION best_doctor_billing_owner_guard();
"""
REMOVE = """
DROP TRIGGER guard_invoice ON payments_invoice;
DROP FUNCTION best_doctor_invoice_guard();
DROP TRIGGER guard_payment ON payments_payment;
DROP FUNCTION best_doctor_payment_guard();
DROP TRIGGER guard_subscription ON subscriptions_subscription;
DROP FUNCTION best_doctor_term_guard();
DROP TRIGGER guard_billing_owner ON doctors_doctorprofile;
DROP FUNCTION best_doctor_billing_owner_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("payments", "0002_initial"), ("accounts", "0002_directory_admin_permissions")]
    operations = [
        migrations.RunPython(grant_billing_permissions, migrations.RunPython.noop),
        migrations.RunSQL(
            INSTALL + "".join(
                f"CREATE TRIGGER immutable_entry BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION best_doctor_ledger_readonly();" for table in IMMUTABLE
            ),
            REMOVE + "".join(f"DROP TRIGGER immutable_entry ON {table};" for table in IMMUTABLE)
            + "DROP FUNCTION best_doctor_ledger_readonly();",
        ),
    ]
