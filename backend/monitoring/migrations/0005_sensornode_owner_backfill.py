from django.db import migrations, models
import django.db.models.deletion


def assign_to_raphael(apps, schema_editor):
    SensorNode = apps.get_model('monitoring', 'SensorNode')
    User = apps.get_model('monitoring', 'User')
    raphael = (
        User.objects.filter(phone_number='+256762038491').first()
        or User.objects.filter(phone_number='256762038491').first()
    )
    if raphael is None:
        print('\n[0005] WARNING: +256762038491 not found — nodes remain owner=NULL.\n')
        return
    updated = SensorNode.objects.filter(owner__isnull=True).update(owner=raphael)
    print(f'\n[0005] Assigned {updated} node(s) to {raphael.full_name}.\n')


def reverse_assignment(apps, schema_editor):
    SensorNode = apps.get_model('monitoring', 'SensorNode')
    SensorNode.objects.all().update(owner=None)


class Migration(migrations.Migration):
    dependencies = [
        ('monitoring', '0004_reading_moisture_pct_sensornode_api_key_and_more'),
    ]
    operations = [
        migrations.AddField(
            model_name='sensornode',
            name='owner',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='User who registered this node (drives RBAC).',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='owned_nodes',
                to='monitoring.user',
            ),
        ),
        migrations.RunPython(assign_to_raphael, reverse_code=reverse_assignment),
    ]
