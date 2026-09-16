from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("entities", "0004_company_government_intelligence")]

    operations = [
        migrations.AddField(
            model_name="person",
            name="government_profile",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="person",
            name="government_profile_observed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
