
from flask import Blueprint, render_template, request, redirect, url_for
import sqlite3
import re
from pathlib import Path
from hashlib import sha256

cadastro_bp = Blueprint('cadastro', __name__)

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

@cadastro_bp.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    mensagem = None

    if request.method == 'POST':
        conn = None

        vcpf = request.form.get('cpf', '').strip()
        vnome = request.form.get('nome', '').strip()
        vlogin = request.form.get('login', '').strip()
        vemail = request.form.get('email', '').strip()
        vsenha = request.form.get('senha', '')

        if not valida_cpf(vcpf):
            mensagem = "CPF inválido!"
        elif not vnome:
            mensagem = "O nome não pode estar vazio!"
        elif not vlogin:
            mensagem = "O usuário não pode estar vazio!"
        elif not valida_email(vemail):
            mensagem = "E-mail inválido!"
        elif len(vsenha) < 5:
            mensagem = "A senha deve ter no mínimo 5 caracteres!"
        else:
            senha_hash = sha256(vsenha.encode('utf-8')).hexdigest()

            try:
                conn = conectar()
                conn.execute(
                    """
                    INSERT INTO Cadclientes
                    (cpf, nome, login, email, senha)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (vcpf, vnome, vlogin, vemail, senha_hash)
                )
                conn.commit()
                return redirect(url_for('login.controle_acesso'))

            except sqlite3.IntegrityError:
                if conn:
                    conn.rollback()
                mensagem = "Erro: CPF ou login já cadastrado. Verifique os dados informados."

            except sqlite3.Error as erro:
                mensagem = f"Erro no banco de dados: {erro}"

            except FileNotFoundError as erro:
                mensagem = str(erro)

            finally:
                if conn is not None:
                    conn.close()

    return render_template('cadastro.html', mensagem=mensagem)