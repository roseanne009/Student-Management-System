# Generated by Django 5.2 on 2025-05-29 01:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('SMSapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subject',
            name='course',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='SMSapp.course'),
        ),
    ]
