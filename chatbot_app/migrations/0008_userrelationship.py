import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0007_alter_intermediatememory_activity_date"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserRelationship",
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
                    "relationship_type",
                    models.CharField(
                        help_text="관계 유형 (예: 가족, 친구, 직장 동료)",
                        max_length=100,
                    ),
                ),
                (
                    "position",
                    models.CharField(
                        blank=True,
                        help_text="관계 내 포지션 (예: 오빠, 친한 친구, 상사)",
                        max_length=100,
                        null=True,
                    ),
                ),
                ("name", models.CharField(help_text="상대방 이름", max_length=100)),
                (
                    "traits",
                    models.TextField(
                        blank=True, help_text="상대방 성격 또는 특징", null=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relationships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("user", "name", "relationship_type")},
            },
        ),
    ]
