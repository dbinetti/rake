# Generated by Django 3.1.4 on 2020-12-01 17:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0024_auto_20201201_0907'),
    ]

    operations = [
        migrations.RenameField(
            model_name='recipient',
            old_name='name',
            new_name='namer',
        ),
    ]