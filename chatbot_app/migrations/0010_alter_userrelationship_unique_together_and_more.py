import uuid
from django.conf import settings
from django.db import migrations, models

def populate_serial_codes(apps, schema_editor):
    UserRelationship = apps.get_model('chatbot_app', 'UserRelationship')
    for relationship in UserRelationship.objects.all():
        if relationship.serial_code is None:
            relationship.serial_code = uuid.uuid4()
            relationship.save()


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot_app", "0009_alter_userrelationship_unique_together_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="userrelationship",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="userrelationship",
            name="serial_code",
            field=models.UUIDField(
                editable=False,
                help_text="동일 인물 구분을 위한 고유 시리얼 코드",
                null=True,
            ),
        ),
        migrations.RunPython(populate_serial_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userrelationship',
            name='serial_code',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="동일 인물 구분을 위한 고유 시리얼 코드",
                unique=True,
                null=False,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="userrelationship",
            unique_together={("user", "serial_code")},
        ),
    ]
