
# Recuperação de senha - Parte B
# Geração, validação e alteração da senha

import sqlite3
import secrets
import hashlib
import time


# --------------------------------------------------
# GERAR TOKEN
# --------------------------------------------------

def gerar_token():

    token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    return token, token_hash


# --------------------------------------------------
# CRIAR SOLICITAÇÃO DE RECUPERAÇÃO
# --------------------------------------------------

def criar_recuperacao(email):

    conn = sqlite3.connect("Cadastroclientes.db")
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT idcliente, nome, email
            FROM Cadclientes
            WHERE email = ?
            """,
            (email,)
        )

        cliente = cursor.fetchone()

        if cliente is None:
            print("\nE-mail não encontrado.")
            return None

        idcliente = cliente[0]
        nome = cliente[1]

        # Gera token
        token, token_hash = gerar_token()

        # Token válido por 15 minutos
        expiracao = int(time.time()) + (15 * 60)

        # Salva no banco
        cursor.execute(
            """
            INSERT INTO recuperacao_senha
            (idcliente, token_hash, expiracao, usado)
            VALUES (?, ?, ?, 0)
            """,
            (idcliente, token_hash, expiracao)
        )

        conn.commit()

        print("\nSolicitação de recuperação criada!")
        print("Cliente:", nome)
        print("E-mail:", email)

        # SOMENTE PARA TESTE
        print("\nTOKEN DE TESTE:")
        print(token)

        return token

    finally:
        conn.close()


# --------------------------------------------------
# VALIDAR TOKEN
# --------------------------------------------------

def validar_token(token):

    conn = sqlite3.connect("Cadastroclientes.db")
    cursor = conn.cursor()

    try:

        token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

        cursor.execute(
            """
            SELECT idrecuperacao, idcliente, expiracao, usado
            FROM recuperacao_senha
            WHERE token_hash = ?
            """,
            (token_hash,)
        )

        recuperacao = cursor.fetchone()

        if recuperacao is None:
            print("\nToken não encontrado.")
            return None

        idrecuperacao = recuperacao[0]
        idcliente = recuperacao[1]
        expiracao = recuperacao[2]
        usado = recuperacao[3]

        # Verifica se já foi utilizado
        if usado == 1:
            print("\nEste token já foi utilizado.")
            return None

        # Verifica se expirou
        if time.time() > expiracao:
            print("\nEste token expirou.")
            return None

        print("\nToken válido!")

        return idrecuperacao, idcliente

    finally:
        conn.close()


# --------------------------------------------------
# ALTERAR SENHA
# --------------------------------------------------

def alterar_senha(idrecuperacao, idcliente):

    nova_senha = input("\nDigite a nova senha: ")

    # Verifica tamanho
    while len(nova_senha) < 5:

        print("A senha deve ter no mínimo 5 caracteres!")

        nova_senha = input(
            "Digite a nova senha novamente: "
        )

    # Confirmação
    confirmar_senha = input("Confirme a nova senha: ")

    while nova_senha != confirmar_senha:

        print("As senhas não coincidem!")

        nova_senha = input("Digite a nova senha: ")
        confirmar_senha = input("Confirme a nova senha: ")

    # Gera o hash da nova senha
    nova_senha_hash = hashlib.sha256(
        nova_senha.encode("utf-8")
    ).hexdigest()

    conn = sqlite3.connect("Cadastroclientes.db")
    cursor = conn.cursor()

    try:

        # Atualiza a senha do cliente
        cursor.execute(
            """
            UPDATE Cadclientes
            SET senha = ?
            WHERE idcliente = ?
            """,
            (nova_senha_hash, idcliente)
        )

        # Marca o token como utilizado
        cursor.execute(
            """
            UPDATE recuperacao_senha
            SET usado = 1
            WHERE idrecuperacao = ?
            """,
            (idrecuperacao,)
        )

        conn.commit()

        print("\nSenha alterada com sucesso!")

    finally:
        conn.close()


# --------------------------------------------------
# TESTE
# --------------------------------------------------

if __name__ == "__main__":

    print("===================================")
    print("       RECUPERAÇÃO DE SENHA")
    print("===================================")

    # Solicita o e-mail até encontrar um cadastro
    while True:

        email = input(
            "Digite o e-mail cadastrado: "
        ).strip()

        token = criar_recuperacao(email)

        if token is not None:
            break

        print("\nTente novamente.\n")

    # Teste do token
    print("\n===================================")
    print("          TESTE DO TOKEN")
    print("===================================")

    # Permite tentar novamente até validar o token
    while True:

        token_digitado = input(
            "Digite o token exibido acima: "
        ).strip()

        resultado = validar_token(token_digitado)

        if resultado is not None:
            break

        print("\nNão foi possível validar o token.")
        print("Tente novamente.\n")

    idrecuperacao, idcliente = resultado

    print("\nRecuperação autorizada!")
    print("ID do cliente:", idcliente)

    # Altera a senha
    alterar_senha(
        idrecuperacao,
        idcliente
    )
