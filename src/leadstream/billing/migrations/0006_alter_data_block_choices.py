from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_creditreservation_creditwallet_credittransaction_and_more")
    ]

    operations = [
        migrations.AlterField(
            model_name="billableevent",
            name="block",
            field=models.CharField(
                choices=[
                    ("COMPANY_REGISTRY", "Dados cadastrais"),
                    ("HYGIENE", "Higienização"),
                    ("DECISION_MAKER", "Decisor"),
                    ("DIRECT_EMAIL", "E-mail direto"),
                    ("DIRECT_PHONE", "Telefone direto"),
                    ("WHATSAPP", "WhatsApp validado"),
                    ("SOCIAL_PROFILES", "Redes sociais"),
                    ("BANKING", "Instituição bancária"),
                    ("GOVERNMENT_RISK", "Risco governamental"),
                    ("PUBLIC_SECTOR", "Atuação no setor público"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="pricerule",
            name="block",
            field=models.CharField(
                choices=[
                    ("COMPANY_REGISTRY", "Dados cadastrais"),
                    ("HYGIENE", "Higienização"),
                    ("DECISION_MAKER", "Decisor"),
                    ("DIRECT_EMAIL", "E-mail direto"),
                    ("DIRECT_PHONE", "Telefone direto"),
                    ("WHATSAPP", "WhatsApp validado"),
                    ("SOCIAL_PROFILES", "Redes sociais"),
                    ("BANKING", "Instituição bancária"),
                    ("GOVERNMENT_RISK", "Risco governamental"),
                    ("PUBLIC_SECTOR", "Atuação no setor público"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="providercall",
            name="block",
            field=models.CharField(
                choices=[
                    ("COMPANY_REGISTRY", "Dados cadastrais"),
                    ("HYGIENE", "Higienização"),
                    ("DECISION_MAKER", "Decisor"),
                    ("DIRECT_EMAIL", "E-mail direto"),
                    ("DIRECT_PHONE", "Telefone direto"),
                    ("WHATSAPP", "WhatsApp validado"),
                    ("SOCIAL_PROFILES", "Redes sociais"),
                    ("BANKING", "Instituição bancária"),
                    ("GOVERNMENT_RISK", "Risco governamental"),
                    ("PUBLIC_SECTOR", "Atuação no setor público"),
                ],
                max_length=32,
            ),
        ),
    ]
