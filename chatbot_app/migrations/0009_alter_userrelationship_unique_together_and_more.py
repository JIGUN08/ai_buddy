from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0008_userrelationship"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="userrelationship",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="userrelationship",
            name="disambiguator",
            field=models.CharField(
                blank=True,
                help_text="동명이인 구분을 위한 식별자 (예: '개발팀', '친구')",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="userrelationship",
            unique_together={("user", "name", "disambiguator")},
        ),
    ]
