import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0003_importantmemory"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name="importantmemory",
            name="activity_date",
        ),
        migrations.RemoveField(
            model_name="importantmemory",
            name="activity_time",
        ),
        migrations.RemoveField(
            model_name="importantmemory",
            name="companion",
        ),
        migrations.RemoveField(
            model_name="importantmemory",
            name="memo",
        ),
        migrations.RemoveField(
            model_name="importantmemory",
            name="place",
        ),
        migrations.AddField(
            model_name="importantmemory",
            name="content",
            field=models.CharField(
                blank=True,
                help_text="정보 내용 (예: '털털함', 'INFP', '1995-10-31')",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="importantmemory",
            name="fact_type",
            field=models.CharField(
                blank=True,
                help_text="정보의 종류 (예: '성격', 'MBTI', '생일')",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="importantmemory",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="important_memories",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="IntermediateMemory",
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
                ("activity_date", models.DateField(help_text="활동 날짜")),
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
                        related_name="memories",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
