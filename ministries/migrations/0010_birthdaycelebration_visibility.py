from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ministries", "0009_birthdaycelebration_birthdaywish_birthdayreaction")]
    operations = [
        migrations.AddField(
            model_name="birthdaycelebration",
            name="visibility",
            field=models.CharField(
                choices=[("members", "Members only"), ("public", "Public celebration")],
                db_index=True, default="members", max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="birthdaycelebration",
            name="consent_confirmed",
            field=models.BooleanField(
                default=False,
                help_text="Confirm the member, or a parent/guardian for a child, approved the selected visibility and social sharing.",
            ),
        ),
        migrations.AlterField(
            model_name="birthdaycelebration",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True, verbose_name="Published"),
        ),
    ]
