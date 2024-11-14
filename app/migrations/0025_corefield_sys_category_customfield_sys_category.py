# Generated by Django 4.2.7 on 2024-11-14 03:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0024_corefield_term_set'),
    ]

    operations = [
        migrations.AddField(
            model_name='corefield',
            name='sys_category',
            field=models.CharField(default='core', editable=False, max_length=50),
        ),
        migrations.AddField(
            model_name='customfield',
            name='sys_category',
            field=models.CharField(default='custom', editable=False, max_length=50),
        ),
    ]
