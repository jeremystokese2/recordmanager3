# Generated by Django 4.2.7 on 2024-10-25 03:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0014_alter_role_options_role_description_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Field',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('stage', models.CharField(max_length=100)),
                ('term_set_name', models.CharField(max_length=100)),
            ],
        ),
    ]
