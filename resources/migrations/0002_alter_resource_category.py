from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resource",
            name="category",
            field=models.CharField(
                choices=[
                    ("teaching", "Teaching"),
                    ("faith", "Our faith"),
                    ("archive", "Archive"),
                    ("document", "Document"),
                    ("form", "Form / template"),
                    ("curriculum", "Lesson / curriculum"),
                    ("sermon", "Sermon / teaching"),
                    ("song", "Song / lyrics / sheet music"),
                    ("policy", "Policy / governance"),
                    ("media", "Photos / video"),
                    ("link", "Website / link"),
                    ("other", "Other"),
                ],
                default="document",
                max_length=12,
            ),
        ),
    ]
