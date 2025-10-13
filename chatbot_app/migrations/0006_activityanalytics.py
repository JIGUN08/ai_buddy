import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0005_alter_importantmemory_unique_together"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityAnalytics",
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
                    "period_type",
                    models.CharField(
                        choices=[
                            ("weekly", "주간"),
                            ("monthly", "월간"),
                            ("yearly", "연간"),
                        ],
                        max_length=10,
                    ),
                ),
                ("period_start_date", models.DateField(help_text="통계 기간의 시작일")),
                (
                    "place",
                    models.CharField(db_index=True, help_text="장소", max_length=255),
                ),
                (
                    "companion",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="동행인",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "count",
                    models.PositiveIntegerField(
                        default=0, help_text="해당 기간 동안의 방문 횟수"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analytics",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {
                    ("user", "period_type", "period_start_date", "place", "companion")
                },
            },
        ),
    ]
