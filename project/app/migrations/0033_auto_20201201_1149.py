# Generated by Django 3.1.4 on 2020-12-01 19:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0032_auto_20201201_1135'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='recipient',
            name='namer',
        ),
        migrations.RemoveField(
            model_name='volunteer',
            name='namer',
        ),
    ]