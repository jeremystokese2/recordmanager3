# Generated by Django 4.2.7 on 2024-11-13 04:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0019_corefield_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='customfield',
            name='wizard_position',
            field=models.IntegerField(choices=[(0, 'Record Information'), (1, 'Record Response')], default=0, help_text='Page where this field will appear'),
        ),
    ]
