# Generated by Django 2.2 on 2019-08-10 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0015_auto_20190810_1340'),
    ]

    operations = [
        migrations.AlterField(
            model_name='houseownerlead',
            name='zoho_id',
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='tenantlead',
            name='zoho_id',
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
    ]
