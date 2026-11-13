from flask import Blueprint, render_template, request, session, redirect, url_for
import sqlite3
from hashlib import sha256

login_bp = Blueprint('login', __name__)

@login_bp.route('/login', methods=['GET', 'POST'])
def controle_acesso():
    mensagem = None

    if 'tentativas' not in session:
        session['tentativas'] = 0

    if request.method == 'POST':
        if session['tentativas'] >= 3:
            mensagem = "Excedeu o número máximo de tentativas! Programa encerrado."
            return render_template('login.html', mensagem=mensagem)

        vlogin = request.form.get('login')
        vsenha = request.form.get('senha')

        if vlogin and vsenha:
            senha_hash = sha256(vsenha.encode("utf-8")).hexdigest()

            conn = sqlite3.connect("Cadastroclientes.db")
            cursor = conn.cursor()

            try:
                sql = """
                    SELECT COUNT(*)
                    FROM Cadclientes
                    WHERE login = ? AND senha = ?
                """
                cursor.execute(sql, (vlogin, senha_hash))
                dados = cursor.fetchone()

                if dados[0] > 0:
                    session['tentativas'] = 0
                    session['usuario_logado'] = True  # sempre ficar logado
                    session['usuario_nome'] = vlogin #guarda o login pra dps    
                   
                    return redirect(url_for('inicial'))
                else:
                    session['tentativas'] += 1
                    restantes = 3 - session['tentativas']
                    
                    if session['tentativas'] >= 3:
                        mensagem = "Excedeu o número máximo de tentativas! Programa encerrado."
                    elif restantes == 1:
                        mensagem = "Acesso negado. Última tentativa!"
                    else:
                        mensagem = f"Acesso negado. Tentativas restantes: {restantes}"

            finally:
                conn.close()

    return render_template('login.html', mensagem=mensagem)