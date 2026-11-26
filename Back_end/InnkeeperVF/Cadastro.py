
# Cadastro de usuarios v05 - CPF + E-mail
# Sistema Innkeeper

import sqlite3
import re
from pathlib import Path
from hashlib import sha256


# --------------------------------------------------
# CONFIGURAÇÃO DO BANCO DE DADOS
# --------------------------------------------------

BANCO = Path(__file__).resolve().parent / "Innkeeper.db"

print("Banco utilizado:", BANCO)

if BANCO.exists():
    teste = sqlite3.connect(BANCO)

    tabelas = teste.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    print("Tabelas encontradas:", tabelas)

    teste.close()


def conectar():
    if not BANCO.exists():
        raise FileNotFoundError(
            f"Banco de dados não encontrado: {BANCO}"
        )

    conn = sqlite3.connect(BANCO)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------
# VALIDADOR DE CPF
# --------------------------------------------------

def valida_cpf(cpf):
    cpf = re.sub(r'\D', '', cpf)

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    digito1 = 0 if resto == 10 else resto

    if digito1 != int(cpf[9]):
        return False

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    digito2 = 0 if resto == 10 else resto

    return digito2 == int(cpf[10])


# --------------------------------------------------
# VALIDADOR DE E-MAIL
# --------------------------------------------------

def valida_email(email):
    padrao = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(padrao, email) is not None


# --------------------------------------------------
# CADASTRO DE USUÁRIOS
# --------------------------------------------------

def cadastrar_usuario():

    conn = None

    try:
        conn = conectar()

        while True:
            print("\n--- CADASTRO DE NOVO USUÁRIO ---")

            # CPF
            vcpf = input("Informe o CPF: ").strip()

            while not valida_cpf(vcpf):
                print("CPF inválido!")
                vcpf = input("Informe o CPF novamente: ").strip()

            # Nome
            vnome = input("Informe o Nome: ").strip()

            while not vnome:
                print("O nome não pode estar vazio!")
                vnome = input("Informe o Nome novamente: ").strip()

            # Usuário
            vlogin = input("Informe o Usuário: ").strip()

            while not vlogin:
                print("O usuário não pode estar vazio!")
                vlogin = input("Informe o Usuário novamente: ").strip()

            # E-mail
            vemail = input("Informe o E-mail: ").strip()

            while not valida_email(vemail):
                print("E-mail inválido!")
                vemail = input("Informe o E-mail novamente: ").strip()

            # Senha
            vsenha = input("Informe a Senha: ")

            while len(vsenha) < 5:
                print("A senha deve ter no mínimo 5 caracteres!")
                vsenha = input("Informe a Senha novamente: ")

            # Gerar hash da senha
            senha_hash = sha256(
                vsenha.encode('utf-8')
            ).hexdigest()

            # Inserir usuário
            try:
                conn.execute(
                    """
                    INSERT INTO Cadclientes
                    (cpf, nome, login, email, senha)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (vcpf, vnome, vlogin, vemail, senha_hash)
                )

                conn.commit()

                print("\nUsuário cadastrado com sucesso!")

            except sqlite3.IntegrityError:
                conn.rollback()
                print(
                    "\nErro: CPF ou login já cadastrado. "
                    "Verifique os dados informados."
                )

            continua = input(
                "\nDigite N para encerrar: "
            ).strip()

            if continua.upper() == "N":
                break

    except sqlite3.Error as erro:
        print(f"\nErro no banco de dados: {erro}")

    except FileNotFoundError as erro:
        print(f"\n{erro}")

    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# EXECUÇÃO PRINCIPAL
# --------------------------------------------------

if __name__ == "__main__":
    cadastrar_usuario()
