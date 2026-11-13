from flask import Blueprint, render_template, request, session, redirect, url_for
import sqlite3
import secrets
import hashlib
import time

recuperacao_bp = Blueprint('recuperacao', __name__)

@recuperacao_bp.route('/gerar-codigo', methods=['POST'])
def gerar_codigo():
    email = request.form.get('email')
    
    conn = sqlite3.connect("Cadastroclientes.db")
    cursor = conn.cursor()
    
    try:
        # Corrigido para buscar 'id' e 'login' conforme o seu banco
        cursor.execute("SELECT id, login FROM Cadclientes WHERE email = ?", (email,))
        cliente = cursor.fetchone()
        
        if cliente is None:
            return render_template('recuperacao.html', erro="E-mail não encontrado.")
            
        idcliente = cliente[0]
        
        # Gera o token (código de 6 letras para ficar fácil do usuário copiar/colar)
        token = secrets.token_hex(3)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expiracao = int(time.time()) + (15 * 60)
        
        cursor.execute("""
            INSERT INTO recuperacao_senha (idcliente, token_hash, expiracao, usado)
            VALUES (?, ?, ?, 0)
        """, (idcliente, token_hash, expiracao))
        conn.commit()
        
        session['token_gerado'] = token # Exibe na tela para teste
        
        return redirect(url_for('recuperacao.nova_senha'))
        
    finally:
        conn.close()

@recuperacao_bp.route('/nova-senha', methods=['GET', 'POST'])
def nova_senha():
    if request.method == 'GET':
        token = session.pop('token_gerado', None)
        return render_template('nova_senha.html', token_teste=token)
        
    token_digitado = request.form.get('token')
    senha = request.form.get('senha')
    confirmar_senha = request.form.get('confirmar_senha')
    
    if senha != confirmar_senha:
        return render_template('nova_senha.html', erro="As senhas não coincidem.")
        
    if len(senha) < 5:
        return render_template('nova_senha.html', erro="A senha deve ter no mínimo 5 caracteres.")
        
    token_hash = hashlib.sha256(token_digitado.encode("utf-8")).hexdigest()
    
    conn = sqlite3.connect("Cadastroclientes.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT idrecuperacao, idcliente, expiracao, usado
            FROM recuperacao_senha WHERE token_hash = ?
        """, (token_hash,))
        
        recuperacao = cursor.fetchone()
        
        if recuperacao is None:
            return render_template('nova_senha.html', erro="Código inválido.")
            
        idrecuperacao, idcliente, expiracao, usado = recuperacao
        
        if usado == 1:
            return render_template('nova_senha.html', erro="Este código já foi utilizado.")
            
        if time.time() > expiracao:
            return render_template('nova_senha.html', erro="Este código expirou.")
            
        # Altera a senha
        nova_senha_hash = hashlib.sha256(senha.encode("utf-8")).hexdigest()
        
        cursor.execute("UPDATE Cadclientes SET senha = ? WHERE id = ?", (nova_senha_hash, idcliente))
        cursor.execute("UPDATE recuperacao_senha SET usado = 1 WHERE idrecuperacao = ?", (idrecuperacao,))
        conn.commit()
        
        session['usuario_logado'] = True
        return redirect(url_for('inicial'))
        
    finally:
        conn.close()