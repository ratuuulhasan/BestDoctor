ROLE_NAMES = (
    "Admin", "Moderator", "Doctor", "Patient", "Hospital Manager",
    "Representative", "Support Staff",
)


def ensure_roles(sender, using, apps=None, **kwargs):
    group_model = (apps or sender.apps).get_model("auth", "Group")
    for name in ROLE_NAMES:
        group_model.objects.using(using).get_or_create(name=name)
