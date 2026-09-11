import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenancy", "0002_seed_internal_tenant"),
    ]

    operations = [
        migrations.CreateModel(
            name="Entity",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("COMPANY", "Empresa"),
                            ("ESTABLISHMENT", "Estabelecimento"),
                            ("PERSON", "Pessoa"),
                        ],
                        max_length=24,
                    ),
                ),
                ("natural_key", models.CharField(max_length=160)),
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
                "db_table": "leadstream_entity",
            },
        ),
        migrations.CreateModel(
            name="Company",
            fields=[
                (
                    "entity",
                    models.OneToOneField(
                        limit_choices_to={"kind": "COMPANY"},
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="company",
                        serialize=False,
                        to="entities.entity",
                    ),
                ),
                ("cnpj_root", models.CharField(max_length=8)),
                ("legal_name", models.CharField(max_length=255)),
                ("trade_name", models.CharField(blank=True, max_length=255)),
                ("registration_status", models.CharField(blank=True, max_length=32)),
                ("opened_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "leadstream_company",
            },
        ),
        migrations.CreateModel(
            name="Person",
            fields=[
                (
                    "entity",
                    models.OneToOneField(
                        limit_choices_to={"kind": "PERSON"},
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="person",
                        serialize=False,
                        to="entities.entity",
                    ),
                ),
                ("full_name", models.CharField(max_length=255)),
                ("normalized_name", models.CharField(max_length=255)),
                ("cpf_masked", models.CharField(blank=True, max_length=14)),
                ("cpf_hash", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "leadstream_person",
            },
        ),
        migrations.CreateModel(
            name="ContactPoint",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("EMAIL", "E-mail"),
                            ("PHONE", "Telefone"),
                            ("WHATSAPP", "WhatsApp"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("PERSON", "Pessoa"),
                            ("COMPANY", "Empresa"),
                            ("ESTABLISHMENT", "Estabelecimento"),
                        ],
                        max_length=20,
                    ),
                ),
                ("original_value", models.CharField(max_length=512)),
                ("normalized_value", models.CharField(max_length=512)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OBSERVED", "Observado"),
                            ("INVALID", "Inválido"),
                            ("DOMAIN_VALID", "Domínio validado"),
                            ("CAPABILITY_VALID", "Capacidade técnica validada"),
                            ("CONFIRMED", "Confirmado"),
                            ("STALE", "Desatualizado"),
                            ("EXPIRED", "Expirado"),
                            ("SUPPRESSED", "Suprimido"),
                        ],
                        default="OBSERVED",
                        max_length=32,
                    ),
                ),
                ("capabilities", models.JSONField(blank=True, default=dict)),
                ("last_observed_at", models.DateTimeField(blank=True, null=True)),
                ("stale_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contact_points",
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
                "db_table": "leadstream_contact_point",
            },
        ),
        migrations.CreateModel(
            name="SocialProfile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "network",
                    models.CharField(
                        choices=[
                            ("LINKEDIN", "LinkedIn"),
                            ("INSTAGRAM", "Instagram"),
                            ("FACEBOOK", "Facebook"),
                            ("X", "X"),
                            ("OTHER", "Outra"),
                        ],
                        max_length=20,
                    ),
                ),
                ("profile_url", models.URLField(max_length=1024)),
                ("normalized_url", models.URLField(max_length=1024)),
                ("handle", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OBSERVED", "Observado"),
                            ("INVALID", "Inválido"),
                            ("DOMAIN_VALID", "Domínio validado"),
                            ("CAPABILITY_VALID", "Capacidade técnica validada"),
                            ("CONFIRMED", "Confirmado"),
                            ("STALE", "Desatualizado"),
                            ("EXPIRED", "Expirado"),
                            ("SUPPRESSED", "Suprimido"),
                        ],
                        default="OBSERVED",
                        max_length=32,
                    ),
                ),
                ("last_observed_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="social_profiles",
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
                "db_table": "leadstream_social_profile",
            },
        ),
        migrations.CreateModel(
            name="Establishment",
            fields=[
                (
                    "entity",
                    models.OneToOneField(
                        limit_choices_to={"kind": "ESTABLISHMENT"},
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="establishment",
                        serialize=False,
                        to="entities.entity",
                    ),
                ),
                ("cnpj", models.CharField(max_length=14)),
                ("is_headquarters", models.BooleanField(default=False)),
                ("registration_status", models.CharField(blank=True, max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="establishments",
                        to="entities.company",
                    ),
                ),
            ],
            options={
                "db_table": "leadstream_establishment",
            },
        ),
        migrations.CreateModel(
            name="Relationship",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "qualification",
                    models.CharField(
                        choices=[
                            ("LEGAL_REPRESENTATIVE", "Representante legal"),
                            ("PARTNER", "Sócio"),
                            ("ADMINISTRATOR", "Administrador"),
                            ("EMPLOYEE", "Funcionário"),
                            ("OTHER", "Outro"),
                        ],
                        max_length=32,
                    ),
                ),
                ("observed_title", models.CharField(blank=True, max_length=255)),
                ("normalized_title", models.CharField(blank=True, max_length=255)),
                (
                    "seniority",
                    models.CharField(
                        choices=[
                            ("OWNER", "Proprietário"),
                            ("C_LEVEL", "C-Level"),
                            ("DIRECTOR", "Diretor"),
                            ("MANAGER", "Gerente"),
                            ("COORDINATOR", "Coordenador"),
                            ("OTHER", "Outro"),
                            ("UNKNOWN", "Não informado"),
                        ],
                        default="UNKNOWN",
                        max_length=24,
                    ),
                ),
                ("buying_role", models.CharField(blank=True, max_length=120)),
                ("buying_role_is_inferred", models.BooleanField(default=False)),
                ("started_on", models.DateField(blank=True, null=True)),
                ("ended_on", models.DateField(blank=True, null=True)),
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
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="relationships",
                        to="entities.company",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="relationships",
                        to="entities.person",
                    ),
                ),
            ],
            options={
                "db_table": "leadstream_relationship",
            },
        ),
        migrations.AddIndex(
            model_name="person",
            index=models.Index(fields=["normalized_name"], name="person_name_idx"),
        ),
        migrations.AddIndex(
            model_name="entity",
            index=models.Index(fields=["tenant", "kind", "natural_key"], name="entity_lookup_idx"),
        ),
        migrations.AddConstraint(
            model_name="entity",
            constraint=models.UniqueConstraint(
                fields=("tenant", "kind", "natural_key"), name="entity_tenant_kind_natural_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="contactpoint",
            index=models.Index(fields=["tenant", "kind", "status"], name="contact_status_idx"),
        ),
        migrations.AddIndex(
            model_name="contactpoint",
            index=models.Index(fields=["tenant", "normalized_value"], name="contact_value_idx"),
        ),
        migrations.AddConstraint(
            model_name="contactpoint",
            constraint=models.UniqueConstraint(
                fields=("tenant", "owner", "kind", "normalized_value"), name="contact_identity_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="socialprofile",
            index=models.Index(
                fields=["tenant", "network", "status"], name="social_profile_status_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="socialprofile",
            constraint=models.UniqueConstraint(
                fields=("tenant", "owner", "network", "normalized_url"),
                name="social_profile_identity_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="establishment",
            index=models.Index(fields=["company", "is_headquarters"], name="estab_company_hq_idx"),
        ),
        migrations.AddIndex(
            model_name="relationship",
            index=models.Index(
                fields=["tenant", "company", "ended_on"], name="relationship_company_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="relationship",
            index=models.Index(
                fields=["tenant", "person", "ended_on"], name="relationship_person_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="relationship",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("ended_on__isnull", True),
                    ("started_on__isnull", True),
                    ("ended_on__gte", models.F("started_on")),
                    _connector="OR",
                ),
                name="relationship_dates_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="relationship",
            constraint=models.UniqueConstraint(
                fields=("tenant", "person", "company", "qualification", "started_on"),
                name="relationship_identity_uniq",
                nulls_distinct=False,
            ),
        ),
    ]
