from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0004_remove_importantmemory_activity_date_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="importantmemory",
            unique_together={("user", "fact_type", "content")},
        ),
    ]
