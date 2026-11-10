from django.db import migrations


def update_brand_wording(apps, schema_editor):
    Campaign = apps.get_model("fundraising", "Campaign")
    replacements = (
        ("Bethel Eritrean Alliance Church", "Bethel Eritrean Church"),
        ("Bethel Eritrean Church of Atlanta", "Bethel Eritrean Church"),
        ("Eritrean and East African families", "Eritrean families"),
        ("East African families", "Eritrean families"),
        ("East Africa", "Eritrea"),
    )

    for campaign in Campaign.objects.all():
        changed_fields = []
        for field_name in ("name", "story"):
            value = getattr(campaign, field_name, "") or ""
            updated = value
            for old, new in replacements:
                updated = updated.replace(old, new)
            if updated != value:
                setattr(campaign, field_name, updated)
                changed_fields.append(field_name)
        if changed_fields:
            campaign.save(update_fields=changed_fields)


class Migration(migrations.Migration):
    dependencies = [("fundraising", "0002_refresh_building_campaign_story")]

    operations = [migrations.RunPython(update_brand_wording, migrations.RunPython.noop)]
