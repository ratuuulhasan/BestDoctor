"""Start or stop the isolated native PostgreSQL instance for local development."""
import argparse
import secrets
import subprocess
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DATA = LOCAL / "pgdata"
ADMIN_SECRET = LOCAL / "postgres-admin-password"


def run(*args):
    subprocess.run(args, check=True)


def start():
    config = dotenv_values(ROOT / ".env")
    cluster_admin = config["POSTGRES_USER"] + "_local_admin"
    port = int(config["POSTGRES_PORT"])
    LOCAL.mkdir(exist_ok=True)
    if not (DATA / "PG_VERSION").exists():
        if not ADMIN_SECRET.exists():
            with ADMIN_SECRET.open("x", encoding="ascii") as handle:
                handle.write(secrets.token_urlsafe(40))
        run("initdb", "-D", str(DATA), "-U", cluster_admin,
            "-A", "scram-sha-256", "--pwfile", str(ADMIN_SECRET),
            "--encoding=UTF8", "--locale=C")
    status = subprocess.run(["pg_ctl", "-D", str(DATA), "status"],
                            stdout=subprocess.DEVNULL)
    if status.returncode:
        run("pg_ctl", "-D", str(DATA), "-l", str(LOCAL / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {port}", "-w", "start")
    with psycopg.connect(
        host="127.0.0.1", port=port, dbname="postgres", user=cluster_admin,
        password=ADMIN_SECRET.read_text(encoding="ascii"), autocommit=True,
    ) as conn:
        user = config["POSTGRES_USER"]
        db = config["POSTGRES_DB"]
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (user,)).fetchone():
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN CREATEDB PASSWORD {}").format(
                sql.Identifier(user), sql.Literal(config["POSTGRES_PASSWORD"]),
            ))
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db,)).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(db), sql.Identifier(user),
            ))
    print(f"Local PostgreSQL ready on 127.0.0.1:{port}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop"])
    action = parser.parse_args().action
    if action == "start":
        start()
    else:
        run("pg_ctl", "-D", str(DATA), "-m", "fast", "-w", "stop")
