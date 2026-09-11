from __future__ import annotations

import csv
import hashlib
import logging
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from django.utils import timezone

from leadstream.entities.models import (
    Company,
    ContactPoint,
    Establishment,
    Relationship,
    SocialProfile,
)

from .models import BatchExport, BatchItem
from .storage import StoredExport, save_export_file

logger = logging.getLogger(__name__)

# Colunas padrão em ordem comercial executiva
DEFAULT_EXPORT_COLUMNS = [
    "CNPJ",
    "Razao_Social",
    "Nome_Fantasia",
    "Situacao_Cadastral",
    "CNAE_Principal",
    "Descricao_CNAE",
    "Data_Abertura",
    "UF",
    "Municipio",
    "Bairro",
    "Logradouro",
    "Numero",
    "CEP",
    "Nome_Decisor",
    "Cargo_Observado",
    "Qualificacao_Societaria",
    "Papel_Compra",
    "Senioridade",
    "Email_Direto",
    "Status_Email",
    "Telefone_Direto",
    "Tipo_Linha",
    "WhatsApp_Validado",
    "Status_Telefone",
    "LinkedIn_Decisor",
    "Redes_Sociais_Empresa",
    "Status_Enriquecimento",
    "Qualidade_Geral",
    "Fontes_Utilizadas",
    "Data_Processamento",
]


def sanitize_csv_cell(value: object) -> str:
    """
    Sanitiza campos de texto para proteção contra CSV Formula Injection (Excel DDE).
    Qualquer valor iniciando com '=', '+', '-', '@' recebe prefixo de apóstrofo.
    Preserva a integridade e legibilidade completa do dado.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


@dataclass
class LeadRow:
    cnpj: str = ""
    razao_social: str = ""
    nome_fantasia: str = ""
    situacao_cadastral: str = ""
    cnae_principal: str = ""
    descricao_cnae: str = ""
    data_abertura: str = ""
    uf: str = ""
    municipio: str = ""
    bairro: str = ""
    logradouro: str = ""
    numero: str = ""
    cep: str = ""
    nome_decisor: str = ""
    cargo_observado: str = ""
    qualificacao_societaria: str = ""
    papel_compra: str = ""
    senioridade: str = ""
    email_direto: str = ""
    status_email: str = ""
    telefone_direto: str = ""
    tipo_linha: str = ""
    whatsapp_validado: str = "NAO"
    status_telefone: str = ""
    linkedin_decisor: str = ""
    redes_sociais_empresa: str = ""
    status_enriquecimento: str = ""
    qualidade_geral: str = "BASICA"
    fontes_utilizadas: str = ""
    data_processamento: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "CNPJ": sanitize_csv_cell(self.cnpj),
            "Razao_Social": sanitize_csv_cell(self.razao_social),
            "Nome_Fantasia": sanitize_csv_cell(self.nome_fantasia),
            "Situacao_Cadastral": sanitize_csv_cell(self.situacao_cadastral),
            "CNAE_Principal": sanitize_csv_cell(self.cnae_principal),
            "Descricao_CNAE": sanitize_csv_cell(self.descricao_cnae),
            "Data_Abertura": sanitize_csv_cell(self.data_abertura),
            "UF": sanitize_csv_cell(self.uf),
            "Municipio": sanitize_csv_cell(self.municipio),
            "Bairro": sanitize_csv_cell(self.bairro),
            "Logradouro": sanitize_csv_cell(self.logradouro),
            "Numero": sanitize_csv_cell(self.numero),
            "CEP": sanitize_csv_cell(self.cep),
            "Nome_Decisor": sanitize_csv_cell(self.nome_decisor),
            "Cargo_Observado": sanitize_csv_cell(self.cargo_observado),
            "Qualificacao_Societaria": sanitize_csv_cell(self.qualificacao_societaria),
            "Papel_Compra": sanitize_csv_cell(self.papel_compra),
            "Senioridade": sanitize_csv_cell(self.senioridade),
            "Email_Direto": sanitize_csv_cell(self.email_direto),
            "Status_Email": sanitize_csv_cell(self.status_email),
            "Telefone_Direto": sanitize_csv_cell(self.telefone_direto),
            "Tipo_Linha": sanitize_csv_cell(self.tipo_linha),
            "WhatsApp_Validado": sanitize_csv_cell(self.whatsapp_validado),
            "Status_Telefone": sanitize_csv_cell(self.status_telefone),
            "LinkedIn_Decisor": sanitize_csv_cell(self.linkedin_decisor),
            "Redes_Sociais_Empresa": sanitize_csv_cell(self.redes_sociais_empresa),
            "Status_Enriquecimento": sanitize_csv_cell(self.status_enriquecimento),
            "Qualidade_Geral": sanitize_csv_cell(self.qualidade_geral),
            "Fontes_Utilizadas": sanitize_csv_cell(self.fontes_utilizadas),
            "Data_Processamento": sanitize_csv_cell(self.data_processamento),
        }


def compute_export_hash(
    batch_id: UUID,
    columns: Sequence[str],
    statuses: Sequence[str],
    lead_level: str,
    updated_at: str,
) -> str:
    cols_str = ",".join(sorted(columns))
    stats_str = ",".join(sorted(statuses))
    key_str = f"{batch_id}:{cols_str}:{stats_str}:{lead_level}:{updated_at}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


class CommercialBatchExporter:
    """
    Gerador de exportação de dados comerciais em altíssima performance.
    - Processa em chunks de 1.000 registros para consumo previsível de memória.
    - Prefetching em lote reduzindo centenas de milhares de queries para poucas operações.
    - Entrega dados 100% visíveis, sem asteriscos ou mascaramento.
    - Saída formatada para pt-BR (UTF-8 com BOM e delimitador ';').
    """

    CHUNK_SIZE = 1_000

    def __init__(self, export: BatchExport) -> None:
        self.export = export
        self.batch = export.batch
        self.tenant = export.tenant
        self.columns = export.selected_columns or DEFAULT_EXPORT_COLUMNS
        self.statuses = export.selected_statuses
        self.lead_level = export.lead_level or "DECISION_MAKER"

    def execute(self) -> BatchExport:
        self.export.status = BatchExport.Status.PROCESSING
        self.export.started_at = timezone.now()
        self.export.save(update_fields=["status", "started_at", "updated_at"])

        try:
            stored = self._generate_file()
            self.export.status = BatchExport.Status.COMPLETED
            self.export.file_backend = stored.backend
            self.export.file_key = stored.key
            self.export.file_name = stored.file_name
            self.export.content_type = stored.content_type
            self.export.size_bytes = stored.size_bytes
            self.export.sha256 = stored.sha256
            self.export.completed_at = timezone.now()

            # Salva o manifesto de auditoria e conformidade
            manifest = {
                "manifest_version": "1.0",
                "export_id": str(self.export.id),
                "batch_id": str(self.batch.id),
                "batch_name": self.batch.name,
                "generated_at": self.export.completed_at.isoformat(),
                "file_name": stored.file_name,
                "file_sha256": stored.sha256,
                "file_size_bytes": stored.size_bytes,
                "total_rows_exported": self.export.total_rows,
                "total_companies": self.export.total_companies,
                "total_decision_makers": self.export.total_decision_makers,
                "total_direct_contacts": self.export.total_direct_contacts,
                "selected_columns": self.columns,
                "selected_statuses": self.statuses,
                "lead_level": self.lead_level,
                "batch_cost_cents": self.batch.cost_cents,
                "batch_revenue_cents": self.batch.revenue_cents,
            }
            self.export.manifest_data = manifest
            self.export.save()
            return self.export
        except Exception as exc:
            logger.exception("Falha na geração do export %s: %s", self.export.id, exc)
            self.export.status = BatchExport.Status.FAILED
            self.export.last_error_code = "EXPORT_GENERATION_FAILED"
            self.export.last_error_message = str(exc)[:500]
            self.export.save(
                update_fields=["status", "last_error_code", "last_error_message", "updated_at"]
            )
            raise

    def _generate_file(self) -> StoredExport:
        ts = timezone.now().strftime("%Y%m%d_%H%M%S")
        batch_slug = self.batch.name[:30].replace(" ", "_")
        file_name = f"leads_{batch_slug}_{ts}.csv"

        # Escreve em arquivo temporário com buffer streaming de 64KB
        with tempfile.NamedTemporaryFile(mode="w+b", delete=False, suffix=".csv") as tmp:
            tmp_path = Path(tmp.name)

        try:
            with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.columns,
                    delimiter=";",
                    quoting=csv.QUOTE_MINIMAL,
                    extrasaction="ignore",
                )
                writer.writeheader()

                total_rows = 0
                total_companies = 0
                total_decision_makers = 0
                total_contacts = 0

                items_qs = BatchItem.objects.filter(batch=self.batch, tenant=self.tenant).order_by(
                    "row_number"
                )
                if self.statuses:
                    items_qs = items_qs.filter(status__in=self.statuses)

                total_items = items_qs.count()

                for start in range(0, total_items, self.CHUNK_SIZE):
                    chunk_items = list(items_qs[start : start + self.CHUNK_SIZE])
                    rows, n_comps, n_decs, n_cnts = self._process_chunk(chunk_items)

                    for row in rows:
                        writer.writerow(row.to_dict())
                        total_rows += 1

                    total_companies += n_comps
                    total_decision_makers += n_decs
                    total_contacts += n_cnts

                self.export.total_rows = total_rows
                self.export.total_companies = total_companies
                self.export.total_decision_makers = total_decision_makers
                self.export.total_direct_contacts = total_contacts

            # Armazena o arquivo (Appwrite Storage com fallback local)
            return save_export_file(
                tenant_id=self.tenant.id,
                file_name=file_name,
                file_path=tmp_path,
                content_type="text/csv; charset=utf-8",
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    def _process_chunk(self, chunk_items: list[BatchItem]) -> tuple[list[LeadRow], int, int, int]:
        """
        Carrega dados em batch prefetch para o chunk de 1.000 itens:
        - 1 query Company
        - 1 query Establishment
        - 1 query Relationship + Person
        - 1 query ContactPoint
        - 1 query SocialProfile
        Total = 5 queries para 1.000 itens!
        """
        entity_ids = [item.entity_id for item in chunk_items if item.entity_id]

        companies_by_entity: dict[UUID, Company] = {}
        estabs_by_company: dict[UUID, Establishment] = {}
        relationships_by_company: dict[UUID, list[Relationship]] = defaultdict(list)
        contacts_by_owner: dict[UUID, list[ContactPoint]] = defaultdict(list)
        socials_by_owner: dict[UUID, list[SocialProfile]] = defaultdict(list)

        if entity_ids:
            companies = Company.objects.filter(entity_id__in=entity_ids, entity__tenant=self.tenant)
            for comp in companies:
                companies_by_entity[comp.entity_id] = comp

            estabs = Establishment.objects.filter(
                company__entity_id__in=entity_ids, entity__tenant=self.tenant
            ).order_by("-is_headquarters")
            for single_estab in estabs:
                company_uuid = cast(UUID, cast(Any, single_estab.company_id))
                if company_uuid not in estabs_by_company:
                    estabs_by_company[company_uuid] = single_estab

            company_rels = (
                Relationship.objects.filter(company__entity_id__in=entity_ids, tenant=self.tenant)
                .select_related("person")
                .order_by("-created_at")
            )
            person_entity_ids: list[UUID] = []
            for rel in company_rels:
                rel_comp_uuid = cast(UUID, cast(Any, rel.company_id))
                relationships_by_company[rel_comp_uuid].append(rel)
                person_entity_ids.append(rel.person.entity_id)

            all_owners = entity_ids + person_entity_ids
            if all_owners:
                contacts = ContactPoint.objects.filter(
                    owner_id__in=all_owners, tenant=self.tenant
                ).exclude(status=ContactPoint.Status.SUPPRESSED)
                for contact in contacts:
                    contacts_by_owner[contact.owner_id].append(contact)

                socials = SocialProfile.objects.filter(owner_id__in=all_owners, tenant=self.tenant)
                for soc in socials:
                    socials_by_owner[soc.owner_id].append(soc)

        rows: list[LeadRow] = []
        companies_count = len(chunk_items)
        decision_makers_count = 0
        contacts_count = 0

        for item in chunk_items:
            norm = item.normalized_data or {}
            orig = item.original_data or {}

            company: Company | None = (
                companies_by_entity.get(item.entity_id) if item.entity_id else None
            )
            estab: Establishment | None = (
                estabs_by_company.get(company.entity_id) if company else None
            )

            cnpj = norm.get("cnpj") or orig.get("cnpj") or (estab.cnpj if estab else "")
            razao_social = (
                company.legal_name
                if company
                else norm.get("razao_social") or orig.get("razao_social") or ""
            )
            nome_fantasia = (
                company.trade_name
                if company
                else norm.get("nome_fantasia") or orig.get("nome_fantasia") or ""
            )
            situacao_cadastral = (
                company.registration_status if company else norm.get("registration_status") or ""
            )
            data_abertura = (
                company.opened_on.isoformat()
                if (company and company.opened_on)
                else norm.get("opened_on") or ""
            )
            cnae_principal = norm.get("primary_cnae") or ""
            descricao_cnae = norm.get("cnae_description") or ""
            uf = norm.get("state") or orig.get("uf") or ""
            municipio = norm.get("city") or orig.get("municipio") or ""
            bairro = norm.get("neighborhood") or orig.get("bairro") or ""
            logradouro = norm.get("street") or orig.get("logradouro") or ""
            numero = norm.get("number") or orig.get("numero") or ""
            cep = norm.get("postal_code") or orig.get("cep") or ""

            status_enriquecimento = item.enrichment_status or item.status
            fontes_utilizadas = (
                ", ".join(item.delivered_blocks) if item.delivered_blocks else "Receita Federal"
            )
            data_proc = item.processed_at.isoformat() if item.processed_at else ""

            # Redes sociais da empresa
            comp_socials = socials_by_owner.get(item.entity_id, []) if item.entity_id else []
            redes_empresa = ", ".join(s.profile_url for s in comp_socials)

            # Contatos da empresa
            comp_contacts = contacts_by_owner.get(item.entity_id, []) if item.entity_id else []

            # Decisores da empresa
            rels: list[Relationship] = (
                list(relationships_by_company.get(company.entity_id, [])) if company else []
            )

            if rels and self.lead_level == "DECISION_MAKER":
                # Emite uma linha por decisor encontrado
                for rel in rels:
                    decision_makers_count += 1
                    person = rel.person
                    person_contacts = contacts_by_owner.get(person.entity_id, [])
                    person_socials = socials_by_owner.get(person.entity_id, [])

                    email_contact = next(
                        (c for c in person_contacts if c.kind == ContactPoint.Kind.EMAIL), None
                    )
                    phone_contact = next(
                        (
                            c
                            for c in person_contacts
                            if c.kind in (ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP)
                        ),
                        None,
                    )
                    linkedin = next(
                        (
                            s.profile_url
                            for s in person_socials
                            if s.network == SocialProfile.Network.LINKEDIN
                        ),
                        "",
                    )

                    # Fallback para contatos da empresa se decisor não tiver direto
                    if not email_contact:
                        email_contact = next(
                            (c for c in comp_contacts if c.kind == ContactPoint.Kind.EMAIL), None
                        )
                    if not phone_contact:
                        phone_contact = next(
                            (
                                c
                                for c in comp_contacts
                                if c.kind in (ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP)
                            ),
                            None,
                        )

                    is_whatsapp = (
                        "SIM"
                        if (
                            phone_contact
                            and (
                                phone_contact.kind == ContactPoint.Kind.WHATSAPP
                                or phone_contact.capabilities.get("whatsapp") is True
                            )
                        )
                        else "NAO"
                    )

                    if email_contact or phone_contact:
                        contacts_count += 1

                    qualidade = "ALTA" if (email_contact and phone_contact) else "MEDIA"

                    rows.append(
                        LeadRow(
                            cnpj=cnpj,
                            razao_social=razao_social,
                            nome_fantasia=nome_fantasia,
                            situacao_cadastral=situacao_cadastral,
                            cnae_principal=cnae_principal,
                            descricao_cnae=descricao_cnae,
                            data_abertura=data_abertura,
                            uf=uf,
                            municipio=municipio,
                            bairro=bairro,
                            logradouro=logradouro,
                            numero=numero,
                            cep=cep,
                            nome_decisor=person.full_name,
                            cargo_observado=rel.observed_title or rel.normalized_title,
                            qualificacao_societaria=rel.qualification,
                            papel_compra=rel.buying_role,
                            senioridade=rel.seniority,
                            email_direto=email_contact.normalized_value if email_contact else "",
                            status_email=email_contact.status if email_contact else "",
                            telefone_direto=phone_contact.normalized_value if phone_contact else "",
                            tipo_linha=phone_contact.kind if phone_contact else "",
                            whatsapp_validado=is_whatsapp,
                            status_telefone=phone_contact.status if phone_contact else "",
                            linkedin_decisor=linkedin,
                            redes_sociais_empresa=redes_empresa,
                            status_enriquecimento=status_enriquecimento,
                            qualidade_geral=qualidade,
                            fontes_utilizadas=fontes_utilizadas,
                            data_processamento=data_proc,
                        )
                    )
            else:
                # Emite uma linha para a empresa
                email_contact = next(
                    (c for c in comp_contacts if c.kind == ContactPoint.Kind.EMAIL), None
                )
                phone_contact = next(
                    (
                        c
                        for c in comp_contacts
                        if c.kind in (ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP)
                    ),
                    None,
                )
                if email_contact or phone_contact:
                    contacts_count += 1

                rows.append(
                    LeadRow(
                        cnpj=cnpj,
                        razao_social=razao_social,
                        nome_fantasia=nome_fantasia,
                        situacao_cadastral=situacao_cadastral,
                        cnae_principal=cnae_principal,
                        descricao_cnae=descricao_cnae,
                        data_abertura=data_abertura,
                        uf=uf,
                        municipio=municipio,
                        bairro=bairro,
                        logradouro=logradouro,
                        numero=numero,
                        cep=cep,
                        email_direto=email_contact.normalized_value if email_contact else "",
                        status_email=email_contact.status if email_contact else "",
                        telefone_direto=phone_contact.normalized_value if phone_contact else "",
                        tipo_linha=phone_contact.kind if phone_contact else "",
                        whatsapp_validado="SIM"
                        if (phone_contact and phone_contact.kind == ContactPoint.Kind.WHATSAPP)
                        else "NAO",
                        status_telefone=phone_contact.status if phone_contact else "",
                        redes_sociais_empresa=redes_empresa,
                        status_enriquecimento=status_enriquecimento,
                        qualidade_geral="BASICA"
                        if not (email_contact or phone_contact)
                        else "MEDIA",
                        fontes_utilizadas=fontes_utilizadas,
                        data_processamento=data_proc,
                    )
                )

        return rows, companies_count, decision_makers_count, contacts_count
