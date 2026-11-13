from flask import Flask, render_template, session, redirect, url_for  # ALTERADO: session, redirect, url_for
import sqlite3  # NOVO
from Back_end.cadastro import cadastro_bp
from Back_end.login import login_bp
app = Flask(__name__)
app.secret_key = 'sua-chave-aqui'  # mantenha a chave que você já colocou

@app.route('/')
def inicial():
    return render_template('inicial.html')

# NOVO: página do usuário logado
@app.route('/painel')
def painel():
    # Se não estiver logado, volta para o login
    if 'usuario' not in session:
        return redirect(url_for('login.controle_acesso'))

    nome = session['usuario']
    conn = sqlite3.connect("Cadastroclientes.db")
    try:
        linha = conn.execute(
            "SELECT nome FROM Cadclientes WHERE login = ?", (session['usuario'],)
        ).fetchone()
        if linha:
            nome = linha[0]
    finally:
        conn.close()

    return render_template('painel.html', nome=nome)

# NOVO: sair da conta
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('inicial'))

# Registra o blueprint de cadastro
app.register_blueprint(cadastro_bp)

# Registra o blueprint de login
app.register_blueprint(login_bp)

if __name__ == '__main__':
    app.run(debug=True)