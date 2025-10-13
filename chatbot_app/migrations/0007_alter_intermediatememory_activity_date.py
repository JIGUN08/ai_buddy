from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0006_activityanalytics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="intermediatememory",
            name="activity_date",
            field=models.DateField(blank=True, help_text="활동 날짜", null=True),
        ),
    ]
