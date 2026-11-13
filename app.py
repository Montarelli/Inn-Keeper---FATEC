from flask import Flask, render_template, session, redirect, url_for
from Back_end.cadastro import cadastro_bp
from Back_end.login import login_bp

app = Flask(__name__)
app.secret_key = '82ff3c6887160c891b121814d21d5c38865d1c445eefb27bc0549d66d3a67597'

# Rota da página inicial (verifica se o usuário está logado para exibir o painel correto)
@app.route('/')
def inicial():
    if session.get('usuario_logado'):
        return render_template('inicial_logado.html')
    return render_template('inicial.html')

# Rota da página de acomodações
@app.route('/acomodacoes')
def acomodacoes():
    return render_template('acomodacoes.html')

# Rota para deslogar o usuário
@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('inicial'))

# Registra os blueprints de cadastro e login
app.register_blueprint(cadastro_bp)
app.register_blueprint(login_bp)

if __name__ == '__main__':
    app.run(debug=True)
