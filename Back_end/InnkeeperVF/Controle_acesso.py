
# Controle de acesso v07
# Sistema Innkeeper

import sqlite3
from hashlib import sha256
import sys
from pathlib import Path


# --------------------------------------------------
# CONFIGURAÇÃO DO BANCO DE DADOS
# --------------------------------------------------

BANCO = Path(__file__).resolve().parent / "Innkeeper.db"


def conectar():

    if not BANCO.exists():
        raise FileNotFoundError(
            f"Banco de dados não encontrado: {BANCO}"
        )

    conn = sqlite3.connect(BANCO)
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# --------------------------------------------------
# CONTROLE DE ACESSO
# --------------------------------------------------

def controle_acesso():

    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        tentativas = 0

        while tentativas < 3:

            if tentativas == 2:
                print("Última tentativa!")

            vlogin = input("Login: ").strip()
            vsenha = input("Senha: ")

            senha_hash = sha256(
                vsenha.encode("utf-8")
            ).hexdigest()

            sql = """
                SELECT COUNT(*)
                FROM Cadclientes
                WHERE login = ? AND senha = ?
            """

            cursor.execute(sql, (vlogin, senha_hash))
            dados = cursor.fetchone()

            if dados[0] > 0:
                print("Acesso permitido!")
                return True

            tentativas += 1

            print("Acesso negado.")
            print("Tentativas restantes:", 3 - tentativas)

        print("Excedeu o número máximo de tentativas!")
        print("Programa encerrado.")

        return False

    except FileNotFoundError as erro:
        print(erro)
        return False

    except sqlite3.Error as erro:
        print(f"Erro no banco de dados: {erro}")
        return False

    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# EXECUÇÃO PRINCIPAL
# --------------------------------------------------

if __name__ == "__main__":
    controle_acesso()
    sys.exit(0)
