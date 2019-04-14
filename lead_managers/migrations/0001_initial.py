# Generated by Django 2.2 on 2019-04-12 18:28

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import lead_managers.utils


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LeadManager',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_no', models.CharField(max_length=15)),
                ('address', models.CharField(blank=True, max_length=300, null=True)),
                ('profile_pic', models.ImageField(blank=True, null=True, upload_to=lead_managers.utils.get_lead_manager_profile_pic_upload_path)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
