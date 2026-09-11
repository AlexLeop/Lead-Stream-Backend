import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("evidence", "0002_observation_append_only"),
        ("tenancy", "0002_seed_internal_tenant"),
    ]

    operations = [
        migrations.CreateModel(
            name="RetentionRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("RUNNING", "Em execução"),
                            ("COMPLETED", "Concluída"),
                            ("FAILED", "Falhou"),
                        ],
                        default="RUNNING",
                        max_length=16,
                    ),
                ),
                ("stale_marked", models.PositiveIntegerField(default=0)),
                ("expired_marked", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "policy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="runs",
                        to="evidence.retentionpolicy",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "leadstream_retention_run",
                "indexes": [
                    models.Index(fields=["tenant", "started_at"], name="retention_run_time_idx")
                ],
            },
        ),
        migrations.CreateModel(
            name="Suppression",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("PERSON", "Pessoa"),
                            ("DOMAIN", "Domínio"),
                            ("EMAIL", "E-mail"),
                            ("PHONE", "Telefone"),
                        ],
                        max_length=16,
                    ),
                ),
                ("value_digest", models.CharField(max_length=64)),
                ("key_version", models.CharField(max_length=32)),
                ("reason", models.CharField(max_length=255)),
                ("effective_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "leadstream_suppression",
                "indexes": [
                    models.Index(
                        fields=["tenant", "scope", "value_digest", "effective_at"],
                        name="suppression_lookup_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "scope", "value_digest", "key_version"),
                        name="suppression_identity_uniq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("expires_at__isnull", True),
                            ("expires_at__gt", models.F("effective_at")),
                            _connector="OR",
                        ),
                        name="suppression_dates_valid",
                    ),
                ],
            },
        ),
    ]
