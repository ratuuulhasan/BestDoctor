from django.db import migrations


DIRECTORY_APPS = ("locations", "specialties", "doctors", "hospitals", "chambers")


def grant_directory_access(apps, schema_editor):
    """Grant the Admin role directory maintenance rights when this phase is installed."""
    alias = schema_editor.connection.alias
    groups = apps.get_model("auth", "Group").objects.using(alias)
    permissions = apps.get_model("auth", "Permission").objects.using(alias)
    types = apps.get_model("contenttypes", "ContentType").objects.using(alias)
    group, _ = groups.get_or_create(name="Admin")
    for label in DIRECTORY_APPS:
        for model in apps.get_app_config(label).get_models():
            name = model._meta.model_name
            content_type, _ = types.get_or_create(app_label=label, model=name)
            for action in ("view", "add", "change"):
                permission, _ = permissions.get_or_create(
                    content_type=content_type, codename=f"{action}_{name}",
                    defaults={"name": f"Can {action} {model._meta.verbose_name}"},
                )
                group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("doctors", "0002_initial"),
        ("chambers", "0002_initial"),
    ]
    operations = [migrations.RunPython(grant_directory_access, migrations.RunPython.noop)]
