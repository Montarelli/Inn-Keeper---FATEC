# Sistema Hoteleiro Innkeeper
# Integração: Cadastro, Controle de Acesso (RBAC), Recuperação de Senha (Demo),
# Reservas, Alteração de Dados e Exclusão de Conta

import re
import time
import sqlite3
import secrets
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates" if (BASE_DIR / "templates").exists() else BASE_DIR.parent / "templates"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.secret_key = '82ff3c6887160c891b121814d21d5c38865d1c445eefb27bc0549d66d3a67597'


# --------------------------------------------------
# CONFIGURAÇÕES GERAIS E BANCO DE DADOS
# --------------------------------------------------

BANCO = Path(__file__).resolve().parent / "Innkeeper.db"


def conectar():
    if not BANCO.exists():
        raise FileNotFoundError(f"Banco de dados não encontrado: {BANCO}")

    conn = sqlite3.connect(BANCO, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_senha(senha: str) -> str:
    return sha256(senha.encode("utf-8")).hexdigest()


def obter_colunas_cadclientes(cursor) -> set:
    cursor.execute("PRAGMA table_info(Cadclientes)")
    return {row["name"].lower() for row in cursor.fetchall()}


def inicializar_rbac():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        colunas = obter_colunas_cadclientes(cursor)
        if "perfil" not in colunas:
            cursor.execute("ALTER TABLE Cadclientes ADD COLUMN perfil VARCHAR(20) DEFAULT 'cliente'")
            conn.commit()

        cursor.execute("SELECT idcliente FROM Cadclientes WHERE login = ? OR cpf = ?", ("admin", "00000000000"))
        if cursor.fetchone() is None:
            cursor.execute(
                """
                INSERT INTO Cadclientes (cpf, nome, login, email, senha, perfil)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("00000000000", "Administrador Innkeeper", "admin", "admin@innkeeper.com", hash_senha("admin123"), "admin"),
            )
            conn.commit()
    except (sqlite3.Error, FileNotFoundError) as erro:
        print(f"Aviso RBAC: {erro}")
    finally:
        if conn is not None:
            conn.close()


inicializar_rbac()


# --------------------------------------------------
# VALIDADORES
# --------------------------------------------------

def valida_cpf(cpf: str) -> bool:
    cpf = re.sub(r"\D", "", cpf)

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


def valida_email(email: str) -> bool:
    padrao = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(padrao, email) is not None


def validar_datas(data_entrada: str, data_saida: str) -> bool:
    try:
        entrada = datetime.strptime(data_entrada, "%Y-%m-%d")
        saida = datetime.strptime(data_saida, "%Y-%m-%d")
        return saida > entrada
    except (ValueError, TypeError):
        return False


# --------------------------------------------------
# MÓDULO 1: CADASTRO DE USUÁRIOS
# --------------------------------------------------

def cadastrar_usuario():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        print("\n--- CADASTRO DE NOVO USUÁRIO ---")

        vcpf = input("Informe o CPF somente em números (ou 0 para cancelar): ").strip()
        if vcpf == "0":
            return
        while not valida_cpf(vcpf):
            print("CPF inválido!")
            vcpf = input("Informe o CPF novamente: ").strip()

        vnome = input("Informe o Nome: ").strip()
        while not vnome:
            print("O nome não pode estar vazio!")
            vnome = input("Informe o Nome novamente: ").strip()

        vlogin = input("Informe o Usuário (login): ").strip()
        while not vlogin:
            print("O usuário não pode estar vazio!")
            vlogin = input("Informe o Usuário novamente: ").strip()

        vemail = input("Informe o E-mail: ").strip()
        while not valida_email(vemail):
            print("E-mail inválido!")
            vemail = input("Informe o E-mail novamente: ").strip()

        vsenha = input("Informe a Senha (mínimo 5 caracteres): ")
        while len(vsenha) < 5:
            print("A senha deve ter no mínimo 5 caracteres!")
            vsenha = input("Informe a Senha novamente: ")

        senha_hash = hash_senha(vsenha)

        try:
            cursor.execute(
                """
                INSERT INTO Cadclientes (cpf, nome, login, email, senha)
                VALUES (?, ?, ?, ?, ?)
                """,
                (vcpf, vnome, vlogin, vemail, senha_hash),
            )
            conn.commit()
            print("\nUsuário cadastrado com sucesso! Agora você já pode fazer login.")

        except sqlite3.IntegrityError:
            conn.rollback()
            print("\nErro: CPF, e-mail ou login já cadastrado. Verifique os dados.")

    except (sqlite3.Error, FileNotFoundError) as erro:
        print(f"\nErro no cadastro: {erro}")
    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# MÓDULO 2: CONTROLE DE ACESSO (LOGIN + RBAC)
# --------------------------------------------------

def realizar_login():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        colunas = obter_colunas_cadclientes(cursor)
        tem_coluna_perfil = "perfil" in colunas

        tentativas = 0
        print("\n--- ACESSO AO SISTEMA ---")

        while tentativas < 3:
            if tentativas == 2:
                print("Atenção: Última tentativa antes do bloqueio temporário!")

            identificacao = input("Login ou E-mail: ").strip()
            vsenha = input("Senha: ")
            senha_hash = hash_senha(vsenha)

            if tem_coluna_perfil:
                sql = """
                    SELECT idcliente, nome, login, email, perfil
                    FROM Cadclientes
                    WHERE (login = ? OR email = ?) AND senha = ?
                """
            else:
                sql = """
                    SELECT idcliente, nome, login, email
                    FROM Cadclientes
                    WHERE (login = ? OR email = ?) AND senha = ?
                """

            cursor.execute(sql, (identificacao, identificacao, senha_hash))
            usuario = cursor.fetchone()

            if usuario is not None:
                perfil = usuario["perfil"] if tem_coluna_perfil and usuario["perfil"] else "cliente"
                print(f"\nAcesso permitido! Bem-vindo(a), {usuario['nome']}.")
                return {
                    "idcliente": usuario["idcliente"],
                    "nome": usuario["nome"],
                    "login": usuario["login"],
                    "email": usuario["email"],
                    "perfil": perfil.lower(),
                }

            tentativas += 1
            print(f"Acesso negado. Tentativas restantes: {3 - tentativas}")

        print("\nExcedeu o número máximo de tentativas! Aguarde 30 segundos...")
        time.sleep(30)
        return None

    except (sqlite3.Error, FileNotFoundError) as erro:
        print(f"\nErro na autenticação: {erro}")
        return None
    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# MÓDULO 3: RECUPERAÇÃO DE SENHA (VERSÃO DEMO)
# --------------------------------------------------

def gerar_token():
    # Gera um código numérico de 6 dígitos
    token = f"{secrets.randbelow(1000000):06d}"
    token_hash = hash_senha(token)
    return token, token_hash


def criar_recuperacao(login: str):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT idcliente, nome
            FROM Cadclientes
            WHERE login = ?
            """,
            (login,),
        )
        cliente = cursor.fetchone()

        if cliente is None:
            print("\nUsuário não encontrado.")
            return None

        idcliente = cliente["idcliente"]
        nome = cliente["nome"]

        # Invalida recuperações anteriores do usuário
        cursor.execute(
            """
            UPDATE recuperacao_senha
            SET usado = 1
            WHERE idcliente = ? AND usado = 0
            """,
            (idcliente,),
        )

        # Gera o token
        token, token_hash = gerar_token()

        # Token válido por 15 minutos
        expiracao = int(time.time()) + (15 * 60)

        # Salva somente o hash no banco
        cursor.execute(
            """
            INSERT INTO recuperacao_senha
            (idcliente, token_hash, expiracao, usado, tentativas)
            VALUES (?, ?, ?, 0, 0)
            """,
            (idcliente, token_hash, expiracao),
        )

        idrecuperacao = cursor.lastrowid
        conn.commit()

        print("\nSolicitação de recuperação criada!")
        print(f"Olá, {nome}!")
        print("\nSeu código de recuperação é:")
        print(f"\n{token}\n")
        print("Este código é válido por 15 minutos.")
        print("Utilize-o apenas uma vez.")

        return idrecuperacao, idcliente

    except sqlite3.Error:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


def validar_token(token: str, idrecuperacao: int, idcliente: int):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT token_hash, expiracao, usado, tentativas
            FROM recuperacao_senha
            WHERE idrecuperacao = ? AND idcliente = ?
            """,
            (idrecuperacao, idcliente),
        )
        recuperacao = cursor.fetchone()

        if recuperacao is None:
            print("\nSolicitação de recuperação não encontrada.")
            return None

        token_hash_salvo = recuperacao["token_hash"]
        expiracao = recuperacao["expiracao"]
        usado = recuperacao["usado"]
        tentativas = recuperacao["tentativas"]

        # Verifica se o token já foi utilizado ou invalidado
        if usado == 1:
            print("\nEste código já foi utilizado ou invalidado.")
            return None

        # Verifica se o token expirou
        if time.time() > expiracao:
            cursor.execute(
                """
                UPDATE recuperacao_senha
                SET usado = 1
                WHERE idrecuperacao = ?
                """,
                (idrecuperacao,),
            )
            conn.commit()
            print("\nEste código expirou.")
            return None

        # Gera o hash do código digitado
        token_hash = hash_senha(token)

        # Compara os hashes
        if not secrets.compare_digest(token_hash, token_hash_salvo):
            # Registra uma tentativa incorreta
            cursor.execute(
                """
                UPDATE recuperacao_senha
                SET tentativas = tentativas + 1,
                    usado = CASE
                        WHEN tentativas + 1 >= 5 THEN 1
                        ELSE usado
                    END
                WHERE idrecuperacao = ?
                """,
                (idrecuperacao,),
            )
            conn.commit()

            tentativas += 1

            if tentativas >= 5:
                print("\nLimite de tentativas atingido!")
                print("Solicite um novo código de recuperação.")
            else:
                print("\nCódigo incorreto!")
                print(f"Tentativas restantes: {5 - tentativas}")

            return None

        print("\nToken válido!")
        return idrecuperacao, idcliente

    finally:
        if conn is not None:
            conn.close()


def verificar_status_token(idrecuperacao: int):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT usado
            FROM recuperacao_senha
            WHERE idrecuperacao = ?
            """,
            (idrecuperacao,),
        )
        return cursor.fetchone()
    finally:
        if conn is not None:
            conn.close()


def alterar_senha_recuperada(idrecuperacao: int, idcliente: int):
    nova_senha = input("\nDigite a nova senha: ")

    while len(nova_senha) < 5:
        print("A senha deve ter no mínimo 5 caracteres!")
        nova_senha = input("Digite a nova senha novamente: ")

    confirmar_senha = input("Confirme a nova senha: ")

    while nova_senha != confirmar_senha:
        print("As senhas não coincidem!")
        nova_senha = input("Digite a nova senha: ")
        confirmar_senha = input("Confirme a nova senha: ")

    nova_senha_hash = hash_senha(nova_senha)
    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE Cadclientes
            SET senha = ?
            WHERE idcliente = ?
            """,
            (nova_senha_hash, idcliente),
        )

        if cursor.rowcount == 0:
            conn.rollback()
            print("\nCliente não encontrado.")
            return

        cursor.execute(
            """
            UPDATE recuperacao_senha
            SET usado = 1
            WHERE idrecuperacao = ?
              AND idcliente = ?
              AND usado = 0
              AND expiracao >= ?
            """,
            (idrecuperacao, idcliente, int(time.time())),
        )

        if cursor.rowcount == 0:
            conn.rollback()
            print("\nCódigo expirado ou já utilizado.")
            print("Solicite uma nova recuperação.")
            return

        conn.commit()
        print("\nSenha alterada com sucesso!")

    except sqlite3.Error:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


def fluxo_recuperacao_senha():
    print("\n===================================")
    print("       RECUPERAÇÃO DE SENHA")
    print("===================================")

    try:
        login = input("Digite seu login cadastrado (ou 0 para voltar): ").strip()
        if login == "0":
            return

        solicitacao = criar_recuperacao(login)
        if solicitacao is None:
            return

        idrecuperacao, idcliente = solicitacao

        print("\n===================================")
        print("          VALIDAR TOKEN")
        print("===================================")

        while True:
            token_digitado = input("Digite o código de recuperação (ou 0 para cancelar): ").strip()
            if token_digitado == "0":
                return

            resultado = validar_token(token_digitado, idrecuperacao, idcliente)
            if resultado is not None:
                print("\nRecuperação autorizada!")
                alterar_senha_recuperada(idrecuperacao, idcliente)
                return

            print("\nNão foi possível validar o código.")
            print("Se ele foi invalidado, solicite outro.\n")

            status = verificar_status_token(idrecuperacao)
            if status is None or status["usado"] == 1:
                print("\nRecuperação encerrada.")
                print("Solicite um novo código para tentar novamente.")
                return

    except (sqlite3.Error, FileNotFoundError) as erro:
        print(f"\nErro na recuperação de senha: {erro}")


# --------------------------------------------------
# MÓDULO 4: RESERVAS E QUARTOS
# --------------------------------------------------

def consultar_quarto_por_numero(numero: int):
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT q.idquarto, q.numero, q.status, t.nome AS tipo, t.preco_atual
            FROM Quartos q
            JOIN TiposQuarto t ON q.idtipo = t.idtipo
            WHERE q.numero = ?
            """,
            (numero,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def listar_quartos():
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT q.numero, t.nome AS tipo, t.preco_atual
            FROM Quartos q
            JOIN TiposQuarto t ON q.idtipo = t.idtipo
            WHERE q.status = 'ativo'
            ORDER BY q.numero
            """
        )
        return [dict(quarto) for quarto in cursor.fetchall()]
    finally:
        conn.close()


def verificar_disponibilidade(idquarto: int, data_entrada: str, data_saida: str) -> bool:
    if not validar_datas(data_entrada, data_saida):
        return False

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM Quartos WHERE idquarto = ?", (idquarto,))
        quarto = cursor.fetchone()

        if quarto is None or quarto["status"] != "ativo":
            return False

        cursor.execute(
            """
            SELECT COUNT(*) AS conflitos
            FROM Reservas
            WHERE idquarto = ?
              AND status IN ('confirmada', 'em_andamento')
              AND date(data_entrada) < date(?)
              AND date(data_saida) > date(?)
            """,
            (idquarto, data_saida, data_entrada),
        )
        return cursor.fetchone()["conflitos"] == 0
    finally:
        conn.close()


def criar_reserva(idcliente: int, idquarto: int, data_entrada: str, data_saida: str):
    if not validar_datas(data_entrada, data_saida):
        return False, "Datas inválidas (a saída deve ser posterior à entrada)."

    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT idcliente FROM Cadclientes WHERE idcliente = ?", (idcliente,))
        if cursor.fetchone() is None:
            conn.rollback()
            return False, "Cliente não encontrado."

        cursor.execute(
            """
            SELECT q.idquarto, q.status, t.preco_atual
            FROM Quartos q
            JOIN TiposQuarto t ON q.idtipo = t.idtipo
            WHERE q.idquarto = ?
            """,
            (idquarto,),
        )
        quarto = cursor.fetchone()

        if quarto is None or quarto["status"] != "ativo":
            conn.rollback()
            return False, "Quarto inexistente ou indisponível."

        preco_diaria = quarto["preco_atual"]
        if preco_diaria is None or preco_diaria <= 0:
            conn.rollback()
            return False, "Preço do quarto ainda não configurado."

        cursor.execute(
            """
            SELECT COUNT(*) AS conflitos
            FROM Reservas
            WHERE idquarto = ?
              AND status IN ('confirmada', 'em_andamento')
              AND date(data_entrada) < date(?)
              AND date(data_saida) > date(?)
            """,
            (idquarto, data_saida, data_entrada),
        )
        if cursor.fetchone()["conflitos"] > 0:
            conn.rollback()
            return False, "Quarto já reservado nesse período."

        entrada = datetime.strptime(data_entrada, "%Y-%m-%d")
        saida = datetime.strptime(data_saida, "%Y-%m-%d")
        quantidade_noites = (saida - entrada).days
        valor_total = preco_diaria * quantidade_noites
        data_reserva = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT INTO Reservas (
                idcliente, idquarto, data_entrada, data_saida,
                preco_diaria, valor_total, status, data_reserva
            )
            VALUES (?, ?, ?, ?, ?, ?, 'confirmada', ?)
            """,
            (
                idcliente,
                idquarto,
                data_entrada,
                data_saida,
                preco_diaria,
                valor_total,
                data_reserva,
            ),
        )
        idreserva = cursor.lastrowid
        conn.commit()

        return True, {
            "idreserva": idreserva,
            "noites": quantidade_noites,
            "preco_diaria": preco_diaria,
            "valor_total": valor_total,
            "data_reserva": data_reserva,
        }

    except sqlite3.Error as erro:
        if conn is not None:
            conn.rollback()
        return False, f"Erro no banco de dados: {erro}"
    finally:
        if conn is not None:
            conn.close()


def alterar_status_reserva(idreserva: int, idcliente: int, status_esperado: str, novo_status: str, msg_sucesso: str, eh_staff: bool = False):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        if eh_staff:
            cursor.execute("SELECT status FROM Reservas WHERE idreserva = ?", (idreserva,))
        else:
            cursor.execute(
                "SELECT status FROM Reservas WHERE idreserva = ? AND idcliente = ?",
                (idreserva, idcliente),
            )

        reserva = cursor.fetchone()
        if reserva is None:
            conn.rollback()
            return False, "Reserva não encontrada."

        if reserva["status"] != status_esperado:
            conn.rollback()
            return False, f"Operação não permitida (status atual: '{reserva['status']}')."

        cursor.execute(
            "UPDATE Reservas SET status = ? WHERE idreserva = ?",
            (novo_status, idreserva),
        )
        conn.commit()
        return True, msg_sucesso

    except sqlite3.Error as erro:
        if conn is not None:
            conn.rollback()
        return False, f"Erro no banco de dados: {erro}"
    finally:
        if conn is not None:
            conn.close()


def listar_reservas(idcliente: int, todas: bool = False):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        if todas:
            cursor.execute(
                """
                SELECT r.idreserva, c.nome AS cliente, q.numero,
                       r.data_entrada, r.data_saida, r.preco_diaria,
                       r.valor_total, r.status, r.data_reserva
                FROM Reservas r
                JOIN Quartos q ON r.idquarto = q.idquarto
                JOIN Cadclientes c ON r.idcliente = c.idcliente
                ORDER BY r.data_entrada DESC
                """
            )
        else:
            cursor.execute(
                """
                SELECT r.idreserva, q.numero,
                       r.data_entrada, r.data_saida, r.preco_diaria,
                       r.valor_total, r.status, r.data_reserva
                FROM Reservas r
                JOIN Quartos q ON r.idquarto = q.idquarto
                WHERE r.idcliente = ?
                ORDER BY r.data_entrada DESC
                """,
                (idcliente,),
            )

        return [dict(row) for row in cursor.fetchall()]

    except sqlite3.Error as erro:
        print(f"Erro ao listar reservas: {erro}")
        return []
    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# MÓDULO 5: ALTERAÇÃO DE DADOS CADASTRAIS
# --------------------------------------------------

def alterar_dados_cadastrais(usuario_logado: dict):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        while True:
            print("\n--- ALTERAÇÃO DE DADOS CADASTRAIS ---")
            print(f"Nome atual  : {usuario_logado['nome']}")
            print(f"Login atual : {usuario_logado['login']}")
            print(f"E-mail atual: {usuario_logado['email']}")
            print("-" * 40)
            print("1 - Alterar Nome")
            print("2 - Alterar Login")
            print("3 - Alterar E-mail")
            print("4 - Alterar Senha")
            print("0 - Voltar ao painel")
            print("-" * 40)

            escolha = input("O que deseja alterar? ").strip()

            if escolha == "0":
                break

            if escolha not in ("1", "2", "3", "4"):
                print("Opção inválida!")
                continue

            # Exige confirmação da senha atual por segurança
            senha_atual = input("\nInforme sua senha atual para confirmar: ")
            cursor.execute(
                "SELECT idcliente FROM Cadclientes WHERE idcliente = ? AND senha = ?",
                (usuario_logado["idcliente"], hash_senha(senha_atual)),
            )
            if cursor.fetchone() is None:
                print("Senha atual incorreta! Alteração cancelada.")
                continue

            try:
                if escolha == "1":
                    novo_nome = input("Novo nome: ").strip()
                    while not novo_nome:
                        print("O nome não pode estar vazio!")
                        novo_nome = input("Novo nome: ").strip()

                    cursor.execute(
                        "UPDATE Cadclientes SET nome = ? WHERE idcliente = ?",
                        (novo_nome, usuario_logado["idcliente"]),
                    )
                    conn.commit()
                    usuario_logado["nome"] = novo_nome
                    print("\nNome atualizado com sucesso!")

                elif escolha == "2":
                    novo_login = input("Novo login: ").strip()
                    while not novo_login:
                        print("O login não pode estar vazio!")
                        novo_login = input("Novo login: ").strip()

                    if novo_login == usuario_logado["login"]:
                        print("\nO novo login é igual ao atual.")
                        continue

                    cursor.execute(
                        "SELECT idcliente FROM Cadclientes WHERE login = ? AND idcliente != ?",
                        (novo_login, usuario_logado["idcliente"]),
                    )
                    if cursor.fetchone() is not None:
                        print("\nErro: Este login já está em uso por outra conta.")
                        continue

                    cursor.execute(
                        "UPDATE Cadclientes SET login = ? WHERE idcliente = ?",
                        (novo_login, usuario_logado["idcliente"]),
                    )
                    conn.commit()
                    usuario_logado["login"] = novo_login
                    print("\nLogin atualizado com sucesso!")

                elif escolha == "3":
                    novo_email = input("Novo e-mail: ").strip()
                    while not valida_email(novo_email):
                        print("E-mail inválido!")
                        novo_email = input("Novo e-mail: ").strip()

                    if novo_email == usuario_logado["email"]:
                        print("\nO novo e-mail é igual ao atual.")
                        continue

                    cursor.execute(
                        "SELECT idcliente FROM Cadclientes WHERE email = ? AND idcliente != ?",
                        (novo_email, usuario_logado["idcliente"]),
                    )
                    if cursor.fetchone() is not None:
                        print("\nErro: Este e-mail já está em uso por outra conta.")
                        continue

                    cursor.execute(
                        "UPDATE Cadclientes SET email = ? WHERE idcliente = ?",
                        (novo_email, usuario_logado["idcliente"]),
                    )
                    conn.commit()
                    usuario_logado["email"] = novo_email
                    print("\nE-mail atualizado com sucesso!")

                elif escolha == "4":
                    nova_senha = input("Nova senha (mínimo 5 caracteres): ")
                    while len(nova_senha) < 5:
                        print("A senha deve ter no mínimo 5 caracteres!")
                        nova_senha = input("Nova senha: ")

                    confirma_senha = input("Confirme a nova senha: ")
                    if nova_senha != confirma_senha:
                        print("\nAs senhas não coincidem! Alteração cancelada.")
                        continue

                    cursor.execute(
                        "UPDATE Cadclientes SET senha = ? WHERE idcliente = ?",
                        (hash_senha(nova_senha), usuario_logado["idcliente"]),
                    )
                    conn.commit()
                    print("\nSenha atualizada com sucesso!")

            except sqlite3.IntegrityError:
                conn.rollback()
                print("\nErro de integridade: login ou e-mail já cadastrado no sistema.")

    except (sqlite3.Error, FileNotFoundError) as erro:
        print(f"\nErro ao alterar dados: {erro}")
    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# MÓDULO 6: EXCLUSÃO DE CONTA
# --------------------------------------------------

def excluir_propria_conta(usuario_logado: dict) -> bool:
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        print("\n--- EXCLUSÃO DA PRÓPRIA CONTA ---")
        print(f"Conta atual: {usuario_logado['nome']} ({usuario_logado['login']})")
        vsenha = input("Confirme sua senha atual para prosseguir: ")
        senha_hash = hash_senha(vsenha)

        cursor.execute(
            "SELECT idcliente FROM Cadclientes WHERE idcliente = ? AND senha = ?",
            (usuario_logado["idcliente"], senha_hash),
        )
        if cursor.fetchone() is None:
            print("\nSenha incorreta! Operação cancelada.")
            return False

        # Verifica se existem reservas ainda ativas antes de permitir a exclusão
        cursor.execute(
            """
            SELECT COUNT(*) AS ativas
            FROM Reservas
            WHERE idcliente = ?
              AND status IN ('confirmada', 'em_andamento')
            """,
            (usuario_logado["idcliente"],),
        )
        if cursor.fetchone()["ativas"] > 0:
            print(
                "\nNão é possível excluir a conta enquanto houver reservas "
                "'confirmada' ou 'em_andamento'. Cancele ou finalize o check-out primeiro."
            )
            return False

        confirma = input(
            "Tem certeza que deseja excluir permanentemente sua conta e seu histórico de reservas? (sim/não): "
        ).strip().lower()
        if confirma != "sim":
            print("\nExclusão cancelada.")
            return False

        try:
            cursor.execute("BEGIN IMMEDIATE")

            # 1. Remove tokens de recuperação de senha vinculados ao usuário
            cursor.execute(
                "DELETE FROM recuperacao_senha WHERE idcliente = ?",
                (usuario_logado["idcliente"],),
            )

            # 2. Remove o histórico de reservas (finalizadas/canceladas) do usuário
            cursor.execute(
                "DELETE FROM Reservas WHERE idcliente = ?",
                (usuario_logado["idcliente"],),
            )

            # 3. Remove o cadastro do cliente
            cursor.execute(
                "DELETE FROM Cadclientes WHERE idcliente = ?",
                (usuario_logado["idcliente"],),
            )

            conn.commit()
            print("\nConta e registros vinculados excluídos com sucesso! Encerrando sessão...")
            return True

        except sqlite3.IntegrityError as erro:
            conn.rollback()
            print(f"\nNão foi possível excluir a conta devido a outro vínculo no banco: {erro}")
            return False

    except (sqlite3.Error, FileNotFoundError) as erro:
        if conn is not None:
            conn.rollback()
        print(f"\nErro ao excluir conta: {erro}")
        return False
    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# MENU INTERNO (LOGADO + CONTROLE RBAC)
# --------------------------------------------------

def menu_usuario_logado(usuario: dict):
    idcliente = usuario["idcliente"]
    perfil = usuario["perfil"]
    eh_staff = perfil in ("admin", "recepcionista", "gerente")

    while True:
        print("\n" + "=" * 50)
        print("           INNKEEPER - PAINEL DO SISTEMA")
        print("=" * 50)
        print(f"Usuário: {usuario['nome']} ({usuario['login']}) | Perfil: {perfil.upper()}")
        print("-" * 50)
        print("1 - Listar quartos ativos")
        print("2 - Verificar disponibilidade de quarto")
        print("3 - Fazer nova reserva")
        print("4 - Cancelar reserva")
        print("5 - Realizar check-in")
        print("6 - Realizar check-out")
        print("7 - Listar minhas reservas")
        if eh_staff:
            print("8 - [STAFF] Listar todas as reservas do hotel")
        print("9 - Alterar meus dados cadastrais")
        print("10 - Excluir minha conta")
        print("0 - Sair da conta (Logout)")
        print("=" * 50)

        opcao = input("Escolha uma opção: ").strip()

        try:
            if opcao == "1":
                quartos = listar_quartos()
                print("\n--- QUARTOS ATIVOS ---")
                if not quartos:
                    print("Nenhum quarto ativo cadastrado.")
                else:
                    for q in quartos:
                        print(f"Quarto {q['numero']} | {q['tipo']} | R$ {q['preco_atual']:.2f}/diária")

            elif opcao == "2":
                numero = int(input("Número do quarto: "))
                data_entrada = input("Data de entrada (AAAA-MM-DD): ").strip()
                data_saida = input("Data de saída (AAAA-MM-DD): ").strip()

                quarto = consultar_quarto_por_numero(numero)
                if quarto is None:
                    print("Quarto não encontrado.")
                elif verificar_disponibilidade(quarto["idquarto"], data_entrada, data_saida):
                    print("Quarto disponível para o período!")
                else:
                    print("Quarto indisponível ou datas inválidas.")

            elif opcao == "3":
                numero = int(input("Número do quarto: "))
                data_entrada = input("Data de entrada (AAAA-MM-DD): ").strip()
                data_saida = input("Data de saída (AAAA-MM-DD): ").strip()

                quarto = consultar_quarto_por_numero(numero)
                if quarto is None:
                    print("Quarto não encontrado.")
                else:
                    sucesso, resultado = criar_reserva(
                        idcliente, quarto["idquarto"], data_entrada, data_saida
                    )
                    if sucesso:
                        print("\nRESERVA REALIZADA COM SUCESSO!")
                        print(f"Código da reserva: {resultado['idreserva']}")
                        print(f"Quarto: {numero} | Noites: {resultado['noites']}")
                        print(f"Diária: R$ {resultado['preco_diaria']:.2f} | Total: R$ {resultado['valor_total']:.2f}")
                    else:
                        print(f"\nNão foi possível realizar a reserva: {resultado}")

            elif opcao == "4":
                idreserva = int(input("Código da reserva para cancelar: "))
                _, msg = alterar_status_reserva(
                    idreserva, idcliente, "confirmada", "cancelada",
                    "Reserva cancelada com sucesso.", eh_staff
                )
                print(msg)

            elif opcao == "5":
                idreserva = int(input("Código da reserva para check-in: "))
                _, msg = alterar_status_reserva(
                    idreserva, idcliente, "confirmada", "em_andamento",
                    "Check-in realizado com sucesso!", eh_staff
                )
                print(msg)

            elif opcao == "6":
                idreserva = int(input("Código da reserva para check-out: "))
                _, msg = alterar_status_reserva(
                    idreserva, idcliente, "em_andamento", "finalizada",
                    "Check-out realizado com sucesso!", eh_staff
                )
                print(msg)

            elif opcao == "7":
                reservas = listar_reservas(idcliente, todas=False)
                if not reservas:
                    print("Você ainda não possui reservas.")
                else:
                    print("\n--- MINHAS RESERVAS ---")
                    for r in reservas:
                        print("-" * 40)
                        print(f"Código: {r['idreserva']} | Quarto: {r['numero']} | Status: {r['status']}")
                        print(f"Período: {r['data_entrada']} até {r['data_saida']}")
                        print(f"Diária: R$ {r['preco_diaria']:.2f} | Total: R$ {r['valor_total']:.2f}")

            elif opcao == "8" and eh_staff:
                reservas = listar_reservas(idcliente, todas=True)
                if not reservas:
                    print("Nenhuma reserva registrada no sistema.")
                else:
                    print("\n--- TODAS AS RESERVAS DO HOTEL ---")
                    for r in reservas:
                        print("-" * 45)
                        print(f"Código: {r['idreserva']} | Cliente: {r['cliente']} | Quarto: {r['numero']}")
                        print(f"Período: {r['data_entrada']} até {r['data_saida']} | Status: {r['status']}")
                        print(f"Total: R$ {r['valor_total']:.2f}")

            elif opcao == "9":
                alterar_dados_cadastrais(usuario)

            elif opcao == "10":
                if excluir_propria_conta(usuario):
                    break

            elif opcao == "0":
                print(f"\nAté logo, {usuario['nome']}!")
                break

            else:
                print("Opção inválida. Tente novamente.")

        except ValueError:
            print("Entrada inválida. Verifique os números e datas digitados.")
        except (sqlite3.Error, FileNotFoundError) as erro:
            print(f"Erro no sistema: {erro}")

        input("\nPressione ENTER para continuar...")


# --------------------------------------------------
# LOOP PRINCIPAL (PORTA DE ENTRADA)
# --------------------------------------------------

def main():
    while True:
        print("\n" + "=" * 50)
        print("       BEM-VINDO AO SISTEMA INNKEEPER")
        print("=" * 50)
        print("1 - Já tenho cadastro (Fazer Login)")
        print("2 - Não tenho cadastro (Criar Conta)")
        print("3 - Esqueci minha senha (Recuperar Senha)")
        print("0 - Encerrar sistema")
        print("=" * 50)

        escolha = input("Escolha uma opção: ").strip()

        if escolha == "1":
            usuario = realizar_login()
            if usuario is not None:
                menu_usuario_logado(usuario)

        elif escolha == "2":
            cadastrar_usuario()

        elif escolha == "3":
            fluxo_recuperacao_senha()

        elif escolha == "0":
            print("\nEncerrando o Sistema Innkeeper. Até mais!")
            break

        else:
            print("\nOpção inválida! Digite 1, 2, 3 ou 0.")


# --------------------------------------------------
# ROTAS FLASK (INTEGRAÇÃO COM O FRONT-END + RBAC)
# --------------------------------------------------

@app.route("/")
@app.route("/inicial")
def inicial():
    usuario = session.get("usuario")
    if usuario:
        if usuario.get("perfil") in ("admin", "recepcionista", "gerente"):
            return redirect(url_for("painel_staff"))
        return redirect(url_for("painel"))
    return render_template("inicial.html")


@app.route("/acomodacoes")
def acomodacoes():
    if session.get("usuario"):
        return redirect(url_for("painel"))
    return redirect(url_for("inicial") + "#quartos")


@app.route("/cadastro", methods=["GET", "POST"])
@app.route("/cadastrar", methods=["GET", "POST"])
def web_cadastrar():
    mensagem = None
    if request.method == "POST":
        conn = None
        try:
            conn = conectar()
            cursor = conn.cursor()

            vcpf = request.form.get("cpf", "").strip()
            vnome = request.form.get("nome", "").strip()
            vlogin = request.form.get("login", "").strip()
            vemail = (request.form.get("email") or request.form.get("e-mail") or "").strip()
            vsenha = request.form.get("senha", "")

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
                senha_hash = hash_senha(vsenha)
                try:
                    cursor.execute(
                        """
                        INSERT INTO Cadclientes (cpf, nome, login, email, senha)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (vcpf, vnome, vlogin, vemail, senha_hash),
                    )
                    conn.commit()
                    flash("Usuário cadastrado com sucesso! Agora você já pode fazer login.", "success")
                    return redirect(url_for("web_login"))
                except sqlite3.IntegrityError:
                    conn.rollback()
                    mensagem = "Erro: CPF, e-mail ou login já cadastrado. Verifique os dados."

        except (sqlite3.Error, FileNotFoundError) as erro:
            mensagem = f"Erro no cadastro: {erro}"
        finally:
            if conn is not None:
                conn.close()

    return render_template("cadastro.html", mensagem=mensagem)


@app.route("/login", methods=["GET", "POST"])
def web_login():
    mensagem = None

    bloqueado_ate = session.get("bloqueado_ate", 0)
    if time.time() < bloqueado_ate:
        mensagem = "Excedeu o número máximo de tentativas! Aguarde 30 segundos..."
        return render_template("login.html", mensagem=mensagem)

    if "tentativas" not in session:
        session["tentativas"] = 0

    if request.method == "POST":
        conn = None
        try:
            conn = conectar()
            cursor = conn.cursor()

            colunas = obter_colunas_cadclientes(cursor)
            tem_coluna_perfil = "perfil" in colunas

            identificacao = request.form.get("login", "").strip()
            vsenha = request.form.get("senha", "")
            senha_hash = hash_senha(vsenha)

            if tem_coluna_perfil:
                sql = """
                    SELECT idcliente, nome, login, email, perfil
                    FROM Cadclientes
                    WHERE (login = ? OR email = ?) AND senha = ?
                """
            else:
                sql = """
                    SELECT idcliente, nome, login, email
                    FROM Cadclientes
                    WHERE (login = ? OR email = ?) AND senha = ?
                """

            cursor.execute(sql, (identificacao, identificacao, senha_hash))
            usuario = cursor.fetchone()

            if usuario is not None:
                perfil = usuario["perfil"] if tem_coluna_perfil and usuario["perfil"] else "cliente"
                perfil = perfil.lower()
                session["tentativas"] = 0
                session.pop("bloqueado_ate", None)
                session["usuario"] = {
                    "idcliente": usuario["idcliente"],
                    "nome": usuario["nome"],
                    "login": usuario["login"],
                    "email": usuario["email"],
                    "perfil": perfil,
                }
                if perfil in ("admin", "recepcionista", "gerente"):
                    return redirect(url_for("painel_staff"))
                return redirect(url_for("painel"))

            session["tentativas"] += 1
            if session["tentativas"] >= 3:
                session["tentativas"] = 0
                session["bloqueado_ate"] = time.time() + 30
                mensagem = "Excedeu o número máximo de tentativas! Aguarde 30 segundos..."
            elif session["tentativas"] == 2:
                mensagem = "Acesso negado. Tentativas restantes: 1 — Atenção: Última tentativa antes do bloqueio temporário!"
            else:
                mensagem = f"Acesso negado. Tentativas restantes: {3 - session['tentativas']}"

        except (sqlite3.Error, FileNotFoundError) as erro:
            mensagem = f"Erro na autenticação: {erro}"
        finally:
            if conn is not None:
                conn.close()

    return render_template("login.html", mensagem=mensagem)


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("inicial"))


@app.route("/recuperacao", methods=["GET", "POST"])
def web_recuperacao():
    erro = None
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        try:
            solicitacao = criar_recuperacao(login)
            if solicitacao is None:
                erro = "Usuário não encontrado."
            else:
                idrecuperacao, idcliente = solicitacao
                session["rec_idrecuperacao"] = idrecuperacao
                session["rec_idcliente"] = idcliente
                return redirect(url_for("web_nova_senha"))
        except (sqlite3.Error, FileNotFoundError) as e:
            erro = f"Erro na recuperação de senha: {e}"

    return render_template("recuperacao.html", erro=erro)


@app.route("/nova-senha", methods=["GET", "POST"])
def web_nova_senha():
    idrecuperacao = session.get("rec_idrecuperacao")
    idcliente = session.get("rec_idcliente")

    if not idrecuperacao or not idcliente:
        return redirect(url_for("web_recuperacao"))

    erro = None
    if request.method == "POST":
        token_digitado = request.form.get("token", "").strip()
        nova_senha = request.form.get("senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")

        try:
            resultado = validar_token(token_digitado, idrecuperacao, idcliente)
            if resultado is None:
                status = verificar_status_token(idrecuperacao)
                if status is None or status["usado"] == 1:
                    session.pop("rec_idrecuperacao", None)
                    session.pop("rec_idcliente", None)
                    flash("Recuperação encerrada. Solicite um novo código para tentar novamente.", "danger")
                    return redirect(url_for("web_recuperacao"))
                erro = "Não foi possível validar o código. Se ele foi invalidado, solicite outro."
            elif len(nova_senha) < 5:
                erro = "A senha deve ter no mínimo 5 caracteres!"
            elif nova_senha != confirmar_senha:
                erro = "As senhas não coincidem!"
            else:
                nova_senha_hash = hash_senha(nova_senha)
                conn = None
                try:
                    conn = conectar()
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        UPDATE Cadclientes
                        SET senha = ?
                        WHERE idcliente = ?
                        """,
                        (nova_senha_hash, idcliente),
                    )
                    if cursor.rowcount == 0:
                        conn.rollback()
                        erro = "Cliente não encontrado."
                    else:
                        cursor.execute(
                            """
                            UPDATE recuperacao_senha
                            SET usado = 1
                            WHERE idrecuperacao = ?
                              AND idcliente = ?
                              AND usado = 0
                              AND expiracao >= ?
                            """,
                            (idrecuperacao, idcliente, int(time.time())),
                        )
                        if cursor.rowcount == 0:
                            conn.rollback()
                            erro = "Código expirado ou já utilizado. Solicite uma nova recuperação."
                        else:
                            conn.commit()
                            session.pop("rec_idrecuperacao", None)
                            session.pop("rec_idcliente", None)
                            flash("Senha alterada com sucesso!", "success")
                            return redirect(url_for("web_login"))
                except sqlite3.Error:
                    if conn is not None:
                        conn.rollback()
                    raise
                finally:
                    if conn is not None:
                        conn.close()
        except (sqlite3.Error, FileNotFoundError) as e:
            erro = f"Erro na recuperação de senha: {e}"

    return render_template("nova_senha.html", erro=erro)


@app.route("/painel")
def painel():
    usuario = session.get("usuario")
    if not usuario:
        return redirect(url_for("web_login"))

    idcliente = usuario["idcliente"]
    perfil = usuario["perfil"]
    eh_staff = perfil in ("admin", "recepcionista", "gerente")
    aba = request.args.get("aba", "quartos")

    quartos = []
    minhas_reservas = []
    todas_reservas = []

    try:
        quartos = listar_quartos()
        minhas_reservas = listar_reservas(idcliente, todas=False)
        if eh_staff:
            todas_reservas = listar_reservas(idcliente, todas=True)
    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro no sistema: {erro}", "danger")

    return render_template(
        "painel.html",
        usuario=usuario,
        eh_staff=eh_staff,
        quartos=quartos,
        minhas_reservas=minhas_reservas,
        todas_reservas=todas_reservas,
        aba=aba,
    )


@app.route("/painel-staff")
def painel_staff():
    usuario = session.get("usuario")
    if not usuario:
        return redirect(url_for("web_login"))

    perfil = usuario["perfil"]
    eh_staff = perfil in ("admin", "recepcionista", "gerente")
    if not eh_staff:
        flash("Acesso negado! Esta área é restrita ao perfil Staff/Admin (RBAC).", "danger")
        return redirect(url_for("painel"))

    todas_reservas = []
    clientes = []
    quartos = []

    conn = None
    try:
        todas_reservas = listar_reservas(usuario["idcliente"], todas=True)
        quartos = listar_quartos()

        conn = conectar()
        cursor = conn.cursor()
        colunas = obter_colunas_cadclientes(cursor)
        if "perfil" in colunas:
            cursor.execute("SELECT idcliente, cpf, nome, login, email, COALESCE(perfil, 'cliente') AS perfil FROM Cadclientes ORDER BY idcliente")
        else:
            cursor.execute("SELECT idcliente, cpf, nome, login, email, 'cliente' AS perfil FROM Cadclientes ORDER BY idcliente")
        clientes = [dict(row) for row in cursor.fetchall()]
    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro no sistema: {erro}", "danger")
    finally:
        if conn is not None:
            conn.close()

    return render_template(
        "painel_staff.html",
        usuario=usuario,
        todas_reservas=todas_reservas,
        clientes=clientes,
        quartos=quartos,
    )


@app.route("/disponibilidade", methods=["POST"])
def web_disponibilidade():
    usuario = session.get("usuario")
    if not usuario:
        return redirect(url_for("web_login"))

    try:
        numero = int(request.form.get("numero", ""))
        data_entrada = request.form.get("data_entrada", "").strip()
        data_saida = request.form.get("data_saida", "").strip()

        quarto = consultar_quarto_por_numero(numero)
        if quarto is None:
            flash("Quarto não encontrado.", "danger")
        elif verificar_disponibilidade(quarto["idquarto"], data_entrada, data_saida):
            flash("Quarto disponível para o período!", "success")
        else:
            flash("Quarto indisponível ou datas inválidas.", "danger")
    except ValueError:
        flash("Entrada inválida. Verifique os números e datas digitados.", "danger")
    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro no sistema: {erro}", "danger")

    return redirect(url_for("painel", aba="quartos"))


@app.route("/reservar", methods=["POST"])
def web_reservar():
    usuario = session.get("usuario")
    if not usuario:
        return redirect(url_for("web_login"))

    try:
        numero = int(request.form.get("numero", ""))
        data_entrada = request.form.get("data_entrada", "").strip()
        data_saida = request.form.get("data_saida", "").strip()

        quarto = consultar_quarto_por_numero(numero)
        if quarto is None:
            flash("Quarto não encontrado.", "danger")
            return redirect(url_for("painel", aba="quartos"))

        sucesso, resultado = criar_reserva(
            usuario["idcliente"], quarto["idquarto"], data_entrada, data_saida
        )
        if sucesso:
            flash(
                f"RESERVA REALIZADA COM SUCESSO! Código: {resultado['idreserva']} | "
                f"Quarto: {numero} | Noites: {resultado['noites']} | "
                f"Diária: R$ {resultado['preco_diaria']:.2f} | Total: R$ {resultado['valor_total']:.2f}",
                "success",
            )
            return redirect(url_for("painel", aba="reservas"))
        else:
            flash(f"Não foi possível realizar a reserva: {resultado}", "danger")
    except ValueError:
        flash("Entrada inválida. Verifique os números e datas digitados.", "danger")
    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro no sistema: {erro}", "danger")

    return redirect(url_for("painel", aba="quartos"))


@app.route("/reserva/cancelar", methods=["POST"])
def web_cancelar_reserva():
    usuario = session.get("usuario")
    if not usuario:
        return redirect(url_for("web_login"))

    eh_staff = usuario["perfil"] in ("admin", "recepcionista", "gerente")
    aba = request.form.get("aba", "reservas")
    origem = request.form.get("origem", "")
    try:
        idreserva = int(request.form.get("idreserva", ""))
        ok, msg = alterar_status_reserva(
            idreserva, usuario["idcliente"], "confirmada", "cancelada",
            "Reserva cancelada com sucesso.", eh_staff
        )
        flash(msg, "success" if ok else "danger")
    except ValueError:
        flash("Entrada inválida. Verifique os números e datas digitados.", "danger")
    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro no sistema: {erro}", "danger")

    if origem == "staff":
        return redirect(url_for("painel_staff"))
    return redirect(url_for("painel", aba=aba))


@app.route("/reserva/checkin", methods=["POST"])
def web_checkin():
    usuario = session.get("usuario")
    if not usuario:
        return redirect(url_for("web_login"))

    eh_staff = usuario["perfil"] in ("admin", "recepcionista", "gerente")
    aba = request.form.get("aba", "reservas")
    origem = request.form.get("origem", "")
    try:
        idreserva = int(request.form.get("idreserva", ""))
        ok, msg = alterar_status_reserva(
            idreserva, usuario["idcliente"], "confirmada", "em_andamento",
            "Check-in realizado com sucesso!", eh_staff
        )
        flash(msg, "success" if ok else "danger")
    except ValueError:
        flash("Entrada inválida. Verifique os números e datas digitados.", "danger")
    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro no sistema: {erro}", "danger")

    if origem == "staff":
        return redirect(url_for("painel_staff"))
    return redirect(url_for("painel", aba=aba))


@app.route("/reserva/checkout", methods=["POST"])
def web_checkout():
    usuario = session.get("usuario")
    if not usuario:
        return redirect(url_for("web_login"))

    eh_staff = usuario["perfil"] in ("admin", "recepcionista", "gerente")
    aba = request.form.get("aba", "reservas")
    origem = request.form.get("origem", "")
    try:
        idreserva = int(request.form.get("idreserva", ""))
        ok, msg = alterar_status_reserva(
            idreserva, usuario["idcliente"], "em_andamento", "finalizada",
            "Check-out realizado com sucesso!", eh_staff
        )
        flash(msg, "success" if ok else "danger")
    except ValueError:
        flash("Entrada inválida. Verifique os números e datas digitados.", "danger")
    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro no sistema: {erro}", "danger")

    if origem == "staff":
        return redirect(url_for("painel_staff"))
    return redirect(url_for("painel", aba=aba))


@app.route("/alterar-dados", methods=["POST"])
def web_alterar_dados():
    usuario_logado = session.get("usuario")
    if not usuario_logado:
        return redirect(url_for("web_login"))

    escolha = request.form.get("escolha", "").strip()
    senha_atual = request.form.get("senha_atual", "")

    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT idcliente FROM Cadclientes WHERE idcliente = ? AND senha = ?",
            (usuario_logado["idcliente"], hash_senha(senha_atual)),
        )
        if cursor.fetchone() is None:
            flash("Senha atual incorreta! Alteração cancelada.", "danger")
            return redirect(url_for("painel", aba="conta"))

        try:
            if escolha == "1":
                novo_nome = request.form.get("novo_nome", "").strip()
                if not novo_nome:
                    flash("O nome não pode estar vazio!", "danger")
                else:
                    cursor.execute(
                        "UPDATE Cadclientes SET nome = ? WHERE idcliente = ?",
                        (novo_nome, usuario_logado["idcliente"]),
                    )
                    conn.commit()
                    usuario_logado["nome"] = novo_nome
                    session["usuario"] = usuario_logado
                    flash("Nome atualizado com sucesso!", "success")

            elif escolha == "2":
                novo_login = request.form.get("novo_login", "").strip()
                if not novo_login:
                    flash("O login não pode estar vazio!", "danger")
                elif novo_login == usuario_logado["login"]:
                    flash("O novo login é igual ao atual.", "danger")
                else:
                    cursor.execute(
                        "SELECT idcliente FROM Cadclientes WHERE login = ? AND idcliente != ?",
                        (novo_login, usuario_logado["idcliente"]),
                    )
                    if cursor.fetchone() is not None:
                        flash("Erro: Este login já está em uso por outra conta.", "danger")
                    else:
                        cursor.execute(
                            "UPDATE Cadclientes SET login = ? WHERE idcliente = ?",
                            (novo_login, usuario_logado["idcliente"]),
                        )
                        conn.commit()
                        usuario_logado["login"] = novo_login
                        session["usuario"] = usuario_logado
                        flash("Login atualizado com sucesso!", "success")

            elif escolha == "3":
                novo_email = request.form.get("novo_email", "").strip()
                if not valida_email(novo_email):
                    flash("E-mail inválido!", "danger")
                elif novo_email == usuario_logado["email"]:
                    flash("O novo e-mail é igual ao atual.", "danger")
                else:
                    cursor.execute(
                        "SELECT idcliente FROM Cadclientes WHERE email = ? AND idcliente != ?",
                        (novo_email, usuario_logado["idcliente"]),
                    )
                    if cursor.fetchone() is not None:
                        flash("Erro: Este e-mail já está em uso por outra conta.", "danger")
                    else:
                        cursor.execute(
                            "UPDATE Cadclientes SET email = ? WHERE idcliente = ?",
                            (novo_email, usuario_logado["idcliente"]),
                        )
                        conn.commit()
                        usuario_logado["email"] = novo_email
                        session["usuario"] = usuario_logado
                        flash("E-mail atualizado com sucesso!", "success")

            elif escolha == "4":
                nova_senha = request.form.get("nova_senha", "")
                confirma_senha = request.form.get("confirma_senha", "")
                if len(nova_senha) < 5:
                    flash("A senha deve ter no mínimo 5 caracteres!", "danger")
                elif nova_senha != confirma_senha:
                    flash("As senhas não coincidem! Alteração cancelada.", "danger")
                else:
                    cursor.execute(
                        "UPDATE Cadclientes SET senha = ? WHERE idcliente = ?",
                        (hash_senha(nova_senha), usuario_logado["idcliente"]),
                    )
                    conn.commit()
                    flash("Senha atualizada com sucesso!", "success")

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Erro de integridade: login ou e-mail já cadastrado no sistema.", "danger")

    except (sqlite3.Error, FileNotFoundError) as erro:
        flash(f"Erro ao alterar dados: {erro}", "danger")
    finally:
        if conn is not None:
            conn.close()

    return redirect(url_for("painel", aba="conta"))


@app.route("/excluir-conta", methods=["POST"])
def web_excluir_conta():
    usuario_logado = session.get("usuario")
    if not usuario_logado:
        return redirect(url_for("web_login"))

    vsenha = request.form.get("senha_atual", "")
    confirma = request.form.get("confirma", "").strip().lower()
    senha_hash = hash_senha(vsenha)

    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT idcliente FROM Cadclientes WHERE idcliente = ? AND senha = ?",
            (usuario_logado["idcliente"], senha_hash),
        )
        if cursor.fetchone() is None:
            flash("Senha incorreta! Operação cancelada.", "danger")
            return redirect(url_for("painel", aba="conta"))

        # Verifica se existem reservas ainda ativas antes de permitir a exclusão
        cursor.execute(
            """
            SELECT COUNT(*) AS ativas
            FROM Reservas
            WHERE idcliente = ?
              AND status IN ('confirmada', 'em_andamento')
            """,
            (usuario_logado["idcliente"],),
        )
        if cursor.fetchone()["ativas"] > 0:
            flash(
                "Não é possível excluir a conta enquanto houver reservas "
                "'confirmada' ou 'em_andamento'. Cancele ou finalize o check-out primeiro.",
                "danger",
            )
            return redirect(url_for("painel", aba="conta"))

        if confirma != "sim":
            flash("Exclusão cancelada.", "danger")
            return redirect(url_for("painel", aba="conta"))

        try:
            cursor.execute("BEGIN IMMEDIATE")

            # 1. Remove tokens de recuperação de senha vinculados ao usuário
            cursor.execute(
                "DELETE FROM recuperacao_senha WHERE idcliente = ?",
                (usuario_logado["idcliente"],),
            )

            # 2. Remove o histórico de reservas (finalizadas/canceladas) do usuário
            cursor.execute(
                "DELETE FROM Reservas WHERE idcliente = ?",
                (usuario_logado["idcliente"],),
            )

            # 3. Remove o cadastro do cliente
            cursor.execute(
                "DELETE FROM Cadclientes WHERE idcliente = ?",
                (usuario_logado["idcliente"],),
            )

            conn.commit()
            session.clear()
            flash("Conta e registros vinculados excluídos com sucesso! Encerrando sessão...", "success")
            return redirect(url_for("inicial"))

        except sqlite3.IntegrityError as erro:
            conn.rollback()
            flash(f"Não foi possível excluir a conta devido a outro vínculo no banco: {erro}", "danger")
            return redirect(url_for("painel", aba="conta"))

    except (sqlite3.Error, FileNotFoundError) as erro:
        if conn is not None:
            conn.rollback()
        flash(f"Erro ao excluir conta: {erro}", "danger")
        return redirect(url_for("painel", aba="conta"))
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    app.run(debug=True)