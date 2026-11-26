
# Exclusão de usuários v03
# Sistema Innkeeper

import sqlite3
from hashlib import sha256
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
# EXCLUSÃO DE USUÁRIOS
# --------------------------------------------------

def excluir_usuarios():

    conn = None

    try:
        conn = conectar()

        while True:
            print("\n--- EXCLUSÃO DE USUÁRIO ---")

            vlogin = input("Informe seu login: ")
            vsenha = input("Informe sua senha: ")

            # Gerar o hash da senha digitada
            senha_hash = sha256(
                vsenha.encode("utf-8")
            ).hexdigest()

            cursor = conn.cursor()

            # Verificar login e senha
            cursor.execute(
                """
                SELECT idcliente, nome
                FROM Cadclientes
                WHERE login = ? AND senha = ?
                """,
                (vlogin, senha_hash)
            )

            usuario = cursor.fetchone()

            if usuario is None:
                print("\nLogin ou senha incorretos!")

            else:
                print("\nUsuário encontrado:", usuario[1])

                confirma = input(
                    "Deseja realmente excluir sua conta? (sim/não): "
                )

                if confirma.strip().lower() == "sim":

                    try:
                        cursor.execute(
                            """
                            DELETE FROM Cadclientes
                            WHERE idcliente = ?
                            """,
                            (usuario[0],)
                        )

                        conn.commit()
                        print("\nConta excluída com sucesso!")

                    except sqlite3.IntegrityError:
                        conn.rollback()

                        print(
                            "\nNão foi possível excluir a conta."
                        )
                        print(
                            "Existem registros vinculados a este usuário."
                        )

                else:
                    print("\nExclusão cancelada.")

            cont = input(
                "\nDeseja excluir outra conta? (sim/não): "
            )

            if cont.strip().lower() != "sim":
                break

    except FileNotFoundError as erro:
        print(f"\nErro: {erro}")

    except sqlite3.Error as erro:
        print(f"\nErro no banco de dados: {erro}")

    finally:
        if conn is not None:
            conn.close()

        print("\nPrograma encerrado.")


# --------------------------------------------------
# EXECUÇÃO PRINCIPAL
# --------------------------------------------------

if __name__ == "__main__":
    excluir_usuarios()
