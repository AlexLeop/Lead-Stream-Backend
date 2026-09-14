from __future__ import annotations

import json
from typing import Any

from django.db import migrations

import leadstream.common.encrypted_fields
from leadstream.common.encrypted_fields import decrypt_json, encrypt_json


def encrypt_existing_credentials(apps: Any, schema_editor: Any) -> None:
    connection = schema_editor.connection
    table = connection.ops.quote_name("leadstream_crm_connection")
    pk_column = connection.ops.quote_name("id")
    credentials_column = connection.ops.quote_name("credentials")
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {pk_column}, {credentials_column} FROM {table}")
        rows = cursor.fetchall()
        for pk, raw_value in rows:
            if raw_value in (None, ""):
                value: dict[str, Any] = {}
            elif isinstance(raw_value, dict):
                value = raw_value
            else:
                parsed = json.loads(raw_value)
                value = parsed if isinstance(parsed, dict) else {}
            encrypted = encrypt_json(value)
            cursor.execute(
                f"UPDATE {table} SET {credentials_column} = %s WHERE {pk_column} = %s",
                [encrypted, pk],
            )


def decrypt_existing_credentials(apps: Any, schema_editor: Any) -> None:
    connection = schema_editor.connection
    table = connection.ops.quote_name("leadstream_crm_connection")
    pk_column = connection.ops.quote_name("id")
    credentials_column = connection.ops.quote_name("credentials")
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {pk_column}, {credentials_column} FROM {table}")
        rows = cursor.fetchall()
        for pk, raw_value in rows:
            if isinstance(raw_value, str):
                value = decrypt_json(raw_value)
            elif isinstance(raw_value, dict):
                value = raw_value
            else:
                value = {}
            cursor.execute(
                f"UPDATE {table} SET {credentials_column} = %s WHERE {pk_column} = %s",
                [json.dumps(value, ensure_ascii=False), pk],
            )


class Migration(migrations.Migration):
    dependencies = [("integrations", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="crmconnection",
            name="credentials",
            field=leadstream.common.encrypted_fields.EncryptedJSONField(blank=True, default=dict),
        ),
        migrations.RunPython(encrypt_existing_credentials, decrypt_existing_credentials),
    ]
