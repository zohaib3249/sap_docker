# Generated by Django 4.1.7 on 2023-05-28 04:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_sapdownloading_error_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sapdownloading',
            name='file_path',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]