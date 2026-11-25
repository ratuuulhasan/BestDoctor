from django.db import migrations


def setup(apps, schema_editor):
    db = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group").objects.using(db)
    types = apps.get_model("contenttypes", "ContentType").objects.using(db)
    permissions = apps.get_model("auth", "Permission").objects.using(db)

    def grant(role, label, model, actions):
        group, _ = Group.get_or_create(name=role)
        kind, _ = types.get_or_create(app_label=label, model=model)
        for action in actions:
            perm, _ = permissions.get_or_create(content_type=kind, codename=f"{action}_{model}",
                                               defaults={"name": f"Can {action} {model}"})
            group.permissions.add(perm)

    for role in ("Moderator", "Admin"):
        grant(role, "reviews", "review", ("view", "change"))
        grant(role, "reviews", "reviewreport", ("view",))
    for role in ("Support Staff", "Admin"):
        grant(role, "support", "supportticket", ("view", "change"))
        grant(role, "support", "contactmessage", ("view", "change"))
    for model in ("blogcategory", "blogtag", "blogpost", "page", "faq", "faqcategory"):
        grant("Admin", "cms", model, ("view", "add", "change"))
    for label, model in (("core", "sitesetting"), ("accounts", "representativeprofile")):
        grant("Admin", label, model, ("view", "add", "change"))
    grant("Admin", "referrals", "referral", ("view", "change"))

    pages = apps.get_model("cms", "Page").objects.using(db)
    for slug, title, content in [
        ("about", "About Best Doctor", "Best Doctor helps people in Bangladesh find doctors, hospitals and consulting chambers. Doctors submit registration evidence before publishing a profile."),
        ("privacy", "Privacy policy", "Published profiles and approved review comments are publicly visible. Registration evidence is available to its owner and authorized reviewers. Account information, support conversations and billing records are restricted by role. Use Contact to ask about your information."),
        ("terms", "Terms of use", "Use the directory to find professional profiles and visiting information. Confirm hours and fees with the chamber before visiting. Submit accurate information and share only your own experience in reviews. Keep private medical details out of public comments."),
    ]:
        pages.get_or_create(slug=slug, defaults={"title": title, "content": content, "published": True})
    category, _ = apps.get_model("cms", "FAQCategory").objects.using(db).get_or_create(name="Using the directory")
    apps.get_model("cms", "FAQ").objects.using(db).get_or_create(
        category=category, question="How can I check a doctor's visiting hours?",
        defaults={"answer": "Open the doctor’s profile and look under Chambers and visiting hours. Check scheduled closures and contact the chamber to confirm."},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"), ("cms", "0001_initial"), ("reviews", "0001_initial"),
        ("support", "0001_initial"), ("referrals", "0001_initial"),
        ("accounts", "0003_patientprofile_representativeprofile"),
    ]
    operations = [migrations.RunPython(setup, migrations.RunPython.noop)]
