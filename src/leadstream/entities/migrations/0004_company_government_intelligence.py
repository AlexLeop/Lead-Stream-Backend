from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("entities", "0003_lead_search_indexes")]

    operations = [
        migrations.AddField(
            model_name="company",
            name="government_risk",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="company",
            name="government_risk_observed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="company",
            name="public_sector_profile",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="company",
            name="public_sector_observed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
