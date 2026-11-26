from flask import Blueprint, render_template, request, session, redirect, url_for
import sqlite3
from hashlib import sha256
from pathlib import Path

login_bp = Blueprint('login', __name__)


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

@login_bp.route('/login', methods=['GET', 'POST'])
def controle_acesso():
    mensagem = None

    if 'tentativas' not in session:
        session['tentativas'] = 0

    if request.method == 'POST':
        if session['tentativas'] >= 3:
            mensagem = "Excedeu o número máximo de tentativas! Programa encerrado."
            return render_template('login.html', mensagem=mensagem)

        vlogin = request.form.get('login', '').strip()
        vsenha = request.form.get('senha', '')

        conn = None

        try:
            conn = conectar()
            cursor = conn.cursor()

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
                session['tentativas'] = 0
                session['usuario_logado'] = True
                session['usuario_nome'] = vlogin
                return redirect(url_for('inicial'))

            session['tentativas'] += 1
            restantes = 3 - session['tentativas']

            if session['tentativas'] >= 3:
                mensagem = "Excedeu o número máximo de tentativas! Programa encerrado."
            elif restantes == 1:
                mensagem = "Acesso negado. Última tentativa!"
            else:
                mensagem = f"Acesso negado. Tentativas restantes: {restantes}"

        except FileNotFoundError as erro:
            mensagem = str(erro)

        except sqlite3.Error as erro:
            mensagem = f"Erro no banco de dados: {erro}"

        finally:
            if conn is not None:
                conn.close()

    return render_template('login.html', mensagem=mensagem)
