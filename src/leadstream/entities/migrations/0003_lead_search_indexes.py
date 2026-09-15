from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("entities", "0002_company_registry_projection")]

    operations = [
        migrations.AddIndex(
            model_name="entity",
            index=models.Index(
                fields=["tenant", "kind", "updated_at"],
                name="entity_tenant_recent_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="company",
            index=models.Index(fields=["primary_cnae"], name="company_cnae_idx"),
        ),
        migrations.AddIndex(
            model_name="company",
            index=models.Index(fields=["company_size"], name="company_size_idx"),
        ),
        migrations.AddIndex(
            model_name="company",
            index=models.Index(fields=["registration_status"], name="company_status_idx"),
        ),
        migrations.AddIndex(
            model_name="establishment",
            index=models.Index(fields=["state", "city"], name="estab_location_idx"),
        ),
    ]
