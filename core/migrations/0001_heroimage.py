from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="HeroImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("placement", models.CharField(max_length=120, unique=True)),
                ("image_blob", models.BinaryField()),
                ("content_type", models.CharField(default="image/jpeg", max_length=50)),
                ("filename", models.CharField(max_length=190)),
                ("alt_text", models.CharField(blank=True, max_length=220)),
                ("position", models.CharField(default="center center", max_length=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_hero_images", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("placement",)},
        ),
    ]
