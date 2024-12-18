# Generated by Django 4.2.7 on 2024-10-25 03:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0013_alter_role_options_alter_role_unique_together_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='role',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AddField(
            model_name='role',
            name='description',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name='role',
            name='display_name',
            field=models.CharField(default='', max_length=100),
        ),
        migrations.AddField(
            model_name='role',
            name='order',
            field=models.IntegerField(default=0),
        ),
    ]
