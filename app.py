from flask import Flask, render_template, session, redirect, url_for
from Back_end.cadastro import cadastro_bp
from Back_end.login import login_bp
from Back_end.recuperacao_web import recuperacao_bp

app = Flask(__name__)
app.secret_key = '82ff3c6887160c891b121814d21d5c38865d1c445eefb27bc0549d66d3a67597'

@app.route('/')
def inicial():
    if session.get('usuario_logado'):
        return render_template('inicial_logado.html')
    return render_template('inicial.html')

@app.route('/acomodacoes')
def acomodacoes():
    return render_template('acomodacoes.html')

@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('inicial'))

# --- RECUPERANDO AS ROTAS DO SEU ANTIGO AUTH.PY ---
@app.route('/cadastro')
def cadastrar():
    return render_template('cadastro.html')

@app.route('/recuperacao')
def recuperar_senha():
    return render_template('recuperacao.html')
# --------------------------------------------------

app.register_blueprint(cadastro_bp)
app.register_blueprint(login_bp)
app.register_blueprint(recuperacao_bp)

if __name__ == '__main__':
    app.run(debug=True)