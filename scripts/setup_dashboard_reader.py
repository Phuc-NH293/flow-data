#!/usr/bin/env python3
"""Create a least-privilege BI dashboard role that can only read mart models."""

import os

import psycopg2
from psycopg2 import sql


def main() -> None:
    dashboard_user = os.environ["DASHBOARD_DB_USER"]
    dashboard_password = os.environ["DASHBOARD_DB_PASSWORD"]

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "resident_analytics"),
        user=os.getenv("POSTGRES_USER", "pipeline_user"),
        password=os.environ["POSTGRES_PASSWORD"],
    )
    conn.autocommit = True
    with conn, conn.cursor() as cursor:
        cursor.execute("select 1 from pg_roles where rolname = %s", (dashboard_user,))
        if cursor.fetchone() is None:
            cursor.execute(
                sql.SQL("create role {} login password %s").format(
                    sql.Identifier(dashboard_user)
                ),
                (dashboard_password,),
            )
        else:
            cursor.execute(
                sql.SQL("alter role {} password %s").format(
                    sql.Identifier(dashboard_user)
                ),
                (dashboard_password,),
            )

        # Remove implicit access, then grant only what the dashboard requires.
        cursor.execute("revoke all on schema raw from public")
        cursor.execute("revoke all on schema staging from public")
        cursor.execute(
            sql.SQL("revoke all on schema raw from {}").format(
                sql.Identifier(dashboard_user)
            )
        )
        cursor.execute(
            sql.SQL("revoke all on schema staging from {}").format(
                sql.Identifier(dashboard_user)
            )
        )
        cursor.execute(
            sql.SQL("grant usage on schema mart to {}").format(
                sql.Identifier(dashboard_user)
            )
        )
        cursor.execute(
            sql.SQL("grant select on all tables in schema mart to {}").format(
                sql.Identifier(dashboard_user)
            )
        )
        cursor.execute(
            sql.SQL(
                "alter default privileges in schema mart "
                "grant select on tables to {}"
            ).format(sql.Identifier(dashboard_user))
        )

    print(f"role {dashboard_user!r} can SELECT from mart only")


if __name__ == "__main__":
    main()
