# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-20 02:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cabinet', '0002_auto_20170620_0846'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='_overwrite',
            field=models.BooleanField(default=False, help_text='By default, a new and unique filename is generated for each file, which also helps with caching.', verbose_name='Keep filename when uploading new file?'),
        ),
    ]

