import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("entities", "0001_initial"),
        ("tenancy", "0002_seed_internal_tenant"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conflict",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("field_path", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("OPEN", "Aberto"), ("RESOLVED", "Resolvido")],
                        default="OPEN",
                        max_length=16,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="conflicts",
                        to="entities.entity",
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
                "db_table": "leadstream_conflict",
            },
        ),
        migrations.CreateModel(
            name="Evidence",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("url", models.URLField(blank=True, max_length=2048)),
                ("external_id", models.CharField(blank=True, max_length=255)),
                ("captured_at", models.DateTimeField()),
                ("observed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("API", "API"),
                            ("DATASET", "Base de dados"),
                            ("WEB_PAGE", "Página pública"),
                            ("SEARCH", "Busca pública"),
                            ("TECHNICAL_CHECK", "Validação técnica"),
                            ("INFERENCE", "Inferência"),
                            ("MANUAL", "Registro manual"),
                        ],
                        max_length=32,
                    ),
                ),
                ("excerpt", models.TextField(blank=True)),
                ("excerpt_hash", models.CharField(blank=True, max_length=64)),
                ("content_hash", models.CharField(max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
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
                "db_table": "leadstream_evidence",
            },
        ),
        migrations.CreateModel(
            name="Observation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("field_path", models.CharField(max_length=255)),
                ("value", models.JSONField(blank=True, null=True)),
                ("value_fingerprint", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ABSENT", "Ausente"),
                            ("OBSERVED", "Observado"),
                            ("INFERRED", "Inferido"),
                            ("TECHNICALLY_VALIDATED", "Validado tecnicamente"),
                            ("CONFIRMED", "Confirmado"),
                            ("CONFLICTING", "Conflitante"),
                            ("REJECTED", "Rejeitado"),
                        ],
                        max_length=32,
                    ),
                ),
                ("confidence", models.PositiveSmallIntegerField()),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("API", "API"),
                            ("DATASET", "Base de dados"),
                            ("WEB_PAGE", "Página pública"),
                            ("SEARCH", "Busca pública"),
                            ("TECHNICAL_CHECK", "Validação técnica"),
                            ("INFERENCE", "Inferência"),
                            ("MANUAL", "Registro manual"),
                        ],
                        max_length=32,
                    ),
                ),
                ("observed_at", models.DateTimeField()),
                ("captured_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "supersedes",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="superseded_by",
                        to="evidence.observation",
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="observations",
                        to="entities.entity",
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
                "db_table": "leadstream_observation",
            },
        ),
        migrations.CreateModel(
            name="ConflictParticipant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "conflict",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="evidence.conflict"
                    ),
                ),
                (
                    "observation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="evidence.observation"
                    ),
                ),
            ],
            options={
                "db_table": "leadstream_conflict_participant",
            },
        ),
        migrations.AddField(
            model_name="conflict",
            name="observations",
            field=models.ManyToManyField(
                through="evidence.ConflictParticipant", to="evidence.observation"
            ),
        ),
        migrations.CreateModel(
            name="CanonicalDecision",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("field_path", models.CharField(max_length=255)),
                ("version", models.PositiveIntegerField()),
                ("policy_version", models.CharField(max_length=64)),
                (
                    "decision_status",
                    models.CharField(
                        choices=[
                            ("ABSENT", "Ausente"),
                            ("OBSERVED", "Observado"),
                            ("INFERRED", "Inferido"),
                            ("TECHNICALLY_VALIDATED", "Validado tecnicamente"),
                            ("CONFIRMED", "Confirmado"),
                            ("CONFLICTING", "Conflitante"),
                            ("REJECTED", "Rejeitado"),
                        ],
                        max_length=32,
                    ),
                ),
                ("reason", models.TextField()),
                ("decided_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="canonical_decisions",
                        to="entities.entity",
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
                (
                    "selected_observation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="canonical_selections",
                        to="evidence.observation",
                    ),
                ),
            ],
            options={
                "db_table": "leadstream_canonical_decision",
            },
        ),
        migrations.CreateModel(
            name="ObservationEvidence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "evidence",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="evidence.evidence"
                    ),
                ),
                (
                    "observation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="evidence.observation"
                    ),
                ),
            ],
            options={
                "db_table": "leadstream_observation_evidence",
            },
        ),
        migrations.AddField(
            model_name="observation",
            name="evidence",
            field=models.ManyToManyField(
                through="evidence.ObservationEvidence", to="evidence.evidence"
            ),
        ),
        migrations.CreateModel(
            name="ProcessingPurpose",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField()),
                ("operational_basis", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "leadstream_processing_purpose",
            },
        ),
        migrations.CreateModel(
            name="RetentionPolicy",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("stale_after_days", models.PositiveIntegerField()),
                ("retention_days", models.PositiveIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "leadstream_retention_policy",
            },
        ),
        migrations.CreateModel(
            name="Source",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("slug", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("GOVERNMENT", "Governamental"),
                            ("COMMERCIAL", "Comercial"),
                            ("PUBLIC_WEB", "Web pública"),
                            ("INTERNAL", "Interna"),
                        ],
                        max_length=24,
                    ),
                ),
                ("priority", models.PositiveSmallIntegerField(default=50)),
                ("terms_url", models.URLField(blank=True, max_length=1024)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "leadstream_source",
            },
        ),
        migrations.CreateModel(
            name="SourceRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("external_id", models.CharField(max_length=255)),
                ("source_url", models.URLField(blank=True, max_length=2048)),
                ("captured_at", models.DateTimeField()),
                ("payload_hash", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "purpose",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="source_records",
                        to="evidence.processingpurpose",
                    ),
                ),
                (
                    "retention_policy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="source_records",
                        to="evidence.retentionpolicy",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="records",
                        to="evidence.source",
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
                "db_table": "leadstream_source_record",
            },
        ),
        migrations.AddField(
            model_name="observation",
            name="source_record",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="observations",
                to="evidence.sourcerecord",
            ),
        ),
        migrations.AddField(
            model_name="evidence",
            name="source_record",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="evidence_items",
                to="evidence.sourcerecord",
            ),
        ),
        migrations.AddConstraint(
            model_name="conflictparticipant",
            constraint=models.UniqueConstraint(
                fields=("conflict", "observation"), name="conflict_participant_uniq"
            ),
        ),
        migrations.AddConstraint(
            model_name="conflict",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "OPEN")),
                fields=("tenant", "target", "field_path"),
                name="conflict_one_open_per_field",
            ),
        ),
        migrations.AddIndex(
            model_name="canonicaldecision",
            index=models.Index(
                fields=["tenant", "target", "field_path", "-version"], name="canonical_current_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="canonicaldecision",
            constraint=models.UniqueConstraint(
                fields=("tenant", "target", "field_path", "version"),
                name="canonical_decision_version_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="observationevidence",
            constraint=models.UniqueConstraint(
                fields=("observation", "evidence"), name="observation_evidence_uniq"
            ),
        ),
        migrations.AddConstraint(
            model_name="processingpurpose",
            constraint=models.UniqueConstraint(
                fields=("tenant", "code"), name="purpose_tenant_code_uniq"
            ),
        ),
        migrations.AddConstraint(
            model_name="retentionpolicy",
            constraint=models.UniqueConstraint(
                fields=("tenant", "code"), name="retention_tenant_code_uniq"
            ),
        ),
        migrations.AddConstraint(
            model_name="retentionpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(("retention_days__gte", models.F("stale_after_days"))),
                name="retention_after_stale",
            ),
        ),
        migrations.AddConstraint(
            model_name="source",
            constraint=models.UniqueConstraint(
                fields=("tenant", "slug"), name="source_tenant_slug_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="sourcerecord",
            index=models.Index(
                fields=["tenant", "source", "captured_at"], name="source_record_time_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="sourcerecord",
            constraint=models.UniqueConstraint(
                fields=("tenant", "source", "external_id"), name="source_record_identity_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="observation",
            index=models.Index(
                fields=["tenant", "target", "field_path"], name="observation_field_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="observation",
            index=models.Index(
                fields=["tenant", "status", "expires_at"], name="observation_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="observation",
            index=models.Index(fields=["value_fingerprint"], name="observation_value_hash_idx"),
        ),
        migrations.AddConstraint(
            model_name="observation",
            constraint=models.CheckConstraint(
                condition=models.Q(("confidence__gte", 0), ("confidence__lte", 100)),
                name="observation_confidence_range",
            ),
        ),
        migrations.AddIndex(
            model_name="evidence",
            index=models.Index(fields=["tenant", "captured_at"], name="evidence_captured_idx"),
        ),
    ]
