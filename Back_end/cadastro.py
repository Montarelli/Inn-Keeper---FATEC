from flask import Blueprint, render_template, request, redirect, url_for
import sqlite3
from hashlib import sha256
import re

cadastro_bp = Blueprint('cadastro', __name__)

# Validador de CPF
def valida_cpf(cpf):
    # Remove caracteres não numéricos
    cpf = re.sub(r'\D', '', cpf)

    # Verifica se tem 11 dígitos ou se todos são iguais
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    # Validação do 1º dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    digito1 = 0 if resto == 10 else resto

    if digito1 != int(cpf[9]):
        return False

    # Validação do 2º dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    digito2 = 0 if resto == 10 else resto

    return digito2 == int(cpf[10])


@cadastro_bp.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    mensagem = None  # NOVO

    if request.method == 'POST':
        # Conexão com banco de dados
        conn = sqlite3.connect("Cadastroclientes.db")
        
        # Garante a tabela caso não exista
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Cadclientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpf TEXT,
                nome TEXT,
                login TEXT,
                senha TEXT
            )
        ''')

        vcpf = request.form.get('cpf')
        vnome = request.form.get('nome')
        vlogin = request.form.get('login')
        vsenha = request.form.get('senha')

        if vcpf and vnome and vlogin and vsenha:
            if valida_cpf(vcpf) and len(vsenha) >= 5:
                vcpf = re.sub(r'\D', '', vcpf)  # NOVO: salva só os números
                senha_hash = sha256(vsenha.encode('utf-8')).hexdigest()

                try:  # NOVO
                    conn.execute(
                        "INSERT INTO Cadclientes (cpf, nome, login, senha) values (?,?,?,?)",
                        (vcpf, vnome, vlogin, senha_hash)
                    )
                    conn.commit()
                    conn.close()
                    return redirect(url_for('login.controle_acesso'))  # ALTERADO
                except sqlite3.IntegrityError:  # NOVO: CPF ou email já cadastrado
                    mensagem = "Já existe uma conta com esse CPF ou email."
            elif not valida_cpf(vcpf):  # NOVO
                mensagem = "CPF inválido."
            else:  # NOVO
                mensagem = "A senha deve ter pelo menos 5 caracteres."
        else:  # NOVO
            mensagem = "Preencha todos os campos."

        conn.close()

    return render_template('cadastro.html', mensagem=mensagem) 