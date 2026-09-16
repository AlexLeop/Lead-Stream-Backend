from django.db import migrations, models

import leadstream.common.encrypted_fields


class Migration(migrations.Migration):
    dependencies = [("entities", "0005_person_government_intelligence")]

    operations = [
        migrations.AddField(
            model_name="person",
            name="enrichment_profile",
            field=leadstream.common.encrypted_fields.EncryptedJSONField(
                blank=True, default=dict
            ),
        ),
        migrations.AddField(
            model_name="person",
            name="enrichment_profile_observed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
