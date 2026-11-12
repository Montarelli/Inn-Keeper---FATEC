from flask import Flask, render_template
from Back_end.cadastro import cadastro_bp
from Back_end.login import login_bp
app = Flask(__name__)
app.secret_key = '82ff3c6887160c891b121814d21d5c38865d1c445eefb27bc0549d66d3a67597'  # eita chave longa da disgrama

@app.route('/')
def inicial():
    return render_template('inicial.html')

# Registra o blueprint de cadastro
app.register_blueprint(cadastro_bp)

# Registra o blueprint de login
app.register_blueprint(login_bp)

if __name__ == '__main__':
    app.run(debug=True)