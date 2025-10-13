import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0010_alter_userrelationship_unique_together_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAttribute",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "fact_type",
                    models.CharField(
                        blank=True,
                        help_text="속성의 종류 (예: '성격', 'MBTI', '생일')",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "content",
                    models.CharField(
                        blank=True,
                        help_text="속성 내용 (예: '털털함', 'INFP', '1995-10-31')",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attributes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("user", "fact_type", "content")},
            },
        ),
        migrations.DeleteModel(
            name="ImportantMemory",
        ),
    ]
