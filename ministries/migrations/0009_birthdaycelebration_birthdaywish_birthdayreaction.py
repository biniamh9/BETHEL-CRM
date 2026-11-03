from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ministries", "0008_ministrymemberspotlight"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="BirthdayCelebration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("member_name", models.CharField(max_length=120)),
                ("celebration_date", models.DateField(help_text="The celebration date for this post. The year is not shown to members as an age.")),
                ("message", models.TextField(blank=True, max_length=800)),
                ("image_blob", models.BinaryField(blank=True, default=b"", editable=False)),
                ("image_content_type", models.CharField(blank=True, editable=False, max_length=30)),
                ("image_filename", models.CharField(blank=True, editable=False, max_length=180)),
                ("consent_confirmed", models.BooleanField(default=False, help_text="Confirm the member, or a parent/guardian for a child, approved the members-only post and social sharing reminder.")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Published to members")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_birthday_celebrations", to=settings.AUTH_USER_MODEL)),
                ("ministry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="birthday_celebrations", to="ministries.ministry")),
            ],
            options={"ordering": ["-celebration_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BirthdayWish",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(max_length=600)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="birthday_wishes", to=settings.AUTH_USER_MODEL)),
                ("celebration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wishes", to="ministries.birthdaycelebration")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="BirthdayReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("love", "Love"), ("celebrate", "Celebrate"), ("blessing", "Blessing")], max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("celebration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="ministries.birthdaycelebration")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="birthday_reactions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="birthdayreaction",
            constraint=models.UniqueConstraint(fields=("celebration", "user"), name="one_birthday_reaction_per_member"),
        ),
    ]
