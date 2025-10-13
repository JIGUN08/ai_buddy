import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0011_userattribute_delete_importantmemory"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserActivity",
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
                    "activity_date",
                    models.DateField(blank=True, help_text="활동 날짜", null=True),
                ),
                (
                    "activity_time",
                    models.TimeField(blank=True, help_text="활동 시간", null=True),
                ),
                (
                    "place",
                    models.CharField(
                        blank=True, help_text="장소", max_length=255, null=True
                    ),
                ),
                (
                    "companion",
                    models.CharField(
                        blank=True, help_text="동행인", max_length=255, null=True
                    ),
                ),
                (
                    "memo",
                    models.TextField(
                        blank=True, help_text="활동 관련 메모 또는 대화 내용", null=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.DeleteModel(
            name="IntermediateMemory",
        ),
    ]
