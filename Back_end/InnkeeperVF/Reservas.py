# Sistema Hoteleiro Innkeeper - Módulo de Reservas

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime


# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------

BANCO = Path(__file__).resolve().parent / "Innkeeper.db"


# --------------------------------------------------
# CONEXÃO COM O BANCO
# --------------------------------------------------

def conectar():

    if not BANCO.exists():
        raise FileNotFoundError(
            f"Banco de dados não encontrado: {BANCO}"
        )

    conn = sqlite3.connect(BANCO, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# --------------------------------------------------
# AUTENTICAÇÃO DO CLIENTE
# --------------------------------------------------

def autenticar_cliente(identificacao, senha):

    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        senha_hash = hashlib.sha256(
            senha.encode("utf-8")
        ).hexdigest()

        cursor.execute("""
            SELECT idcliente, nome
            FROM Cadclientes
            WHERE (login = ? OR email = ?)
              AND senha = ?
        """, (
            identificacao,
            identificacao,
            senha_hash
        ))

        clientes = cursor.fetchall()

        if len(clientes) == 1:
            return True, {
                "idcliente": clientes[0]["idcliente"],
                "nome": clientes[0]["nome"]
            }

        return False, "Login, e-mail ou senha incorretos."

    except sqlite3.Error as erro:
        return False, f"Erro ao autenticar cliente: {erro}"

    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------
# VALIDAR DATAS
# --------------------------------------------------

def validar_datas(data_entrada, data_saida):

    try:
        entrada = datetime.strptime(data_entrada, "%Y-%m-%d")
        saida = datetime.strptime(data_saida, "%Y-%m-%d")

        return saida > entrada

    except (ValueError, TypeError):
        return False


# --------------------------------------------------
# CONSULTAR QUARTO PELO NÚMERO
# --------------------------------------------------

def consultar_quarto_por_numero(numero):

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                q.idquarto,
                q.numero,
                q.status,
                t.nome AS tipo,
                t.preco_atual
            FROM Quartos q
            JOIN TiposQuarto t ON q.idtipo = t.idtipo
            WHERE q.numero = ?
        """, (numero,))

        return cursor.fetchone()

    finally:
        conn.close()


# --------------------------------------------------
# LISTAR QUARTOS
# --------------------------------------------------

def listar_quartos():

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                q.numero,
                t.nome AS tipo,
                t.preco_atual
            FROM Quartos q
            JOIN TiposQuarto t ON q.idtipo = t.idtipo
            WHERE q.status = 'ativo'
            ORDER BY q.numero
        """)

        return [dict(quarto) for quarto in cursor.fetchall()]

    finally:
        conn.close()


# --------------------------------------------------
# VERIFICAR DISPONIBILIDADE
# --------------------------------------------------

def verificar_disponibilidade(idquarto, data_entrada, data_saida):

    if not validar_datas(data_entrada, data_saida):
        return False

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status
            FROM Quartos
            WHERE idquarto = ?
        """, (idquarto,))

        quarto = cursor.fetchone()

        if quarto is None or quarto["status"] != "ativo":
            return False

        cursor.execute("""
            SELECT COUNT(*) AS conflitos
            FROM Reservas
            WHERE idquarto = ?
              AND status IN ('confirmada', 'em_andamento')
              AND date(data_entrada) < date(?)
              AND date(data_saida) > date(?)
        """, (idquarto, data_saida, data_entrada))

        resultado = cursor.fetchone()

        return resultado["conflitos"] == 0

    finally:
        conn.close()


# --------------------------------------------------
# CRIAR RESERVA
# --------------------------------------------------

def criar_reserva(idcliente, idquarto, data_entrada, data_saida):

    if not validar_datas(data_entrada, data_saida):
        return False, "Datas inválidas."

    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        # Verificar se o cliente existe
        cursor.execute("""
            SELECT idcliente
            FROM Cadclientes
            WHERE idcliente = ?
        """, (idcliente,))

        if cursor.fetchone() is None:
            conn.rollback()
            return False, "Cliente não encontrado."

        # Consultar quarto e preço
        cursor.execute("""
            SELECT q.idquarto, q.status, t.preco_atual
            FROM Quartos q
            JOIN TiposQuarto t ON q.idtipo = t.idtipo
            WHERE q.idquarto = ?
        """, (idquarto,))

        quarto = cursor.fetchone()

        if quarto is None or quarto["status"] != "ativo":
            conn.rollback()
            return False, "Quarto inexistente ou indisponível."

        # Verificar preço
        preco_diaria = quarto["preco_atual"]

        if preco_diaria is None or preco_diaria <= 0:
            conn.rollback()
            return False, "Preço do quarto ainda não configurado."

        # Verificar conflitos
        cursor.execute("""
            SELECT COUNT(*) AS conflitos
            FROM Reservas
            WHERE idquarto = ?
              AND status IN ('confirmada', 'em_andamento')
              AND date(data_entrada) < date(?)
              AND date(data_saida) > date(?)
        """, (idquarto, data_saida, data_entrada))

        if cursor.fetchone()["conflitos"] > 0:
            conn.rollback()
            return False, "Quarto já reservado nesse período."

        # Calcular noites e valor
        entrada = datetime.strptime(data_entrada, "%Y-%m-%d")
        saida = datetime.strptime(data_saida, "%Y-%m-%d")

        quantidade_noites = (saida - entrada).days
        valor_total = preco_diaria * quantidade_noites

        data_reserva = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Registrar reserva
        cursor.execute("""
            INSERT INTO Reservas (
                idcliente,
                idquarto,
                data_entrada,
                data_saida,
                preco_diaria,
                valor_total,
                status,
                data_reserva
            )
            VALUES (?, ?, ?, ?, ?, ?, 'confirmada', ?)
        """, (
            idcliente,
            idquarto,
            data_entrada,
            data_saida,
            preco_diaria,
            valor_total,
            data_reserva
        ))

        idreserva = cursor.lastrowid

        conn.commit()

        return True, {
            "idreserva": idreserva,
            "noites": quantidade_noites,
            "preco_diaria": preco_diaria,
            "valor_total": valor_total,
            "data_reserva": data_reserva
        }

    except sqlite3.Error as erro:

        if conn is not None:
            conn.rollback()

        return False, f"Erro no banco de dados: {erro}"

    finally:

        if conn is not None:
            conn.close()


# --------------------------------------------------
# CANCELAR RESERVA
# --------------------------------------------------

def cancelar_reserva(idreserva, idcliente):

    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT status
            FROM Reservas
            WHERE idreserva = ?
              AND idcliente = ?
        """, (idreserva, idcliente))

        reserva = cursor.fetchone()

        if reserva is None:
            conn.rollback()
            return False, "Reserva não encontrada."

        if reserva["status"] != "confirmada":
            conn.rollback()
            return False, "Esta reserva não pode ser cancelada."

        cursor.execute("""
            UPDATE Reservas
            SET status = 'cancelada'
            WHERE idreserva = ?
              AND idcliente = ?
        """, (idreserva, idcliente))

        conn.commit()

        return True, "Reserva cancelada com sucesso."

    except sqlite3.Error as erro:

        if conn is not None:
            conn.rollback()

        return False, f"Erro no banco de dados: {erro}"

    finally:

        if conn is not None:
            conn.close()


# --------------------------------------------------
# REALIZAR CHECK-IN
# --------------------------------------------------

def realizar_checkin(idreserva, idcliente):

    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT status
            FROM Reservas
            WHERE idreserva = ?
              AND idcliente = ?
        """, (idreserva, idcliente))

        reserva = cursor.fetchone()

        if reserva is None:
            conn.rollback()
            return False, "Reserva não encontrada."

        if reserva["status"] != "confirmada":
            conn.rollback()
            return False, "Reserva não está disponível para check-in."

        cursor.execute("""
            UPDATE Reservas
            SET status = 'em_andamento'
            WHERE idreserva = ?
              AND idcliente = ?
        """, (idreserva, idcliente))

        conn.commit()

        return True, "Check-in realizado com sucesso!"

    except sqlite3.Error as erro:

        if conn is not None:
            conn.rollback()

        return False, f"Erro ao realizar check-in: {erro}"

    finally:

        if conn is not None:
            conn.close()


# --------------------------------------------------
# REALIZAR CHECK-OUT
# --------------------------------------------------

def realizar_checkout(idreserva, idcliente):

    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT status
            FROM Reservas
            WHERE idreserva = ?
              AND idcliente = ?
        """, (idreserva, idcliente))

        reserva = cursor.fetchone()

        if reserva is None:
            conn.rollback()
            return False, "Reserva não encontrada."

        if reserva["status"] != "em_andamento":
            conn.rollback()
            return False, "A reserva não está em andamento."

        cursor.execute("""
            UPDATE Reservas
            SET status = 'finalizada'
            WHERE idreserva = ?
              AND idcliente = ?
        """, (idreserva, idcliente))

        conn.commit()

        return True, "Check-out realizado com sucesso!"

    except sqlite3.Error as erro:

        if conn is not None:
            conn.rollback()

        return False, f"Erro ao realizar check-out: {erro}"

    finally:

        if conn is not None:
            conn.close()


# --------------------------------------------------
# LISTAR RESERVAS DO CLIENTE
# --------------------------------------------------

def listar_reservas_cliente(idcliente):

    conn = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                r.idreserva,
                r.idquarto,
                q.numero,
                r.data_entrada,
                r.data_saida,
                r.preco_diaria,
                r.valor_total,
                r.status,
                r.data_reserva
            FROM Reservas r
            JOIN Quartos q ON r.idquarto = q.idquarto
            WHERE r.idcliente = ?
            ORDER BY r.data_entrada DESC
        """, (idcliente,))

        reservas = cursor.fetchall()

        return [dict(reserva) for reserva in reservas]

    except sqlite3.Error as erro:

        print(f"Erro ao listar reservas: {erro}")
        return []

    finally:

        if conn is not None:
            conn.close()


# --------------------------------------------------
# MENU INTERATIVO
# --------------------------------------------------

def menu_reservas(idcliente, nome_cliente):

    while True:

        print("\n" + "=" * 45)
        print("       INNKEEPER - SISTEMA DE RESERVAS")
        print("=" * 45)
        print(f"Cliente conectado: {nome_cliente}")
        print("-" * 45)

        print("1 - Listar quartos")
        print("2 - Verificar disponibilidade")
        print("3 - Criar reserva")
        print("4 - Cancelar reserva")
        print("5 - Realizar check-in")
        print("6 - Realizar check-out")
        print("7 - Listar minhas reservas")
        print("0 - Sair")

        print("=" * 45)

        opcao = input("Escolha uma opção: ").strip()

        try:

            # LISTAR QUARTOS
            if opcao == "1":

                quartos = listar_quartos()

                print("\n--- QUARTOS DISPONÍVEIS PARA CONSULTA ---")

                if not quartos:
                    print("Nenhum quarto ativo cadastrado.")

                else:
                    for quarto in quartos:

                        print(
                            f"Quarto {quarto['numero']} | "
                            f"{quarto['tipo']} | "
                            f"R$ {quarto['preco_atual']:.2f} por diária"
                        )

            # VERIFICAR DISPONIBILIDADE
            elif opcao == "2":

                numero = int(input("Número do quarto: "))

                data_entrada = input(
                    "Data de entrada (AAAA-MM-DD): "
                ).strip()

                data_saida = input(
                    "Data de saída (AAAA-MM-DD): "
                ).strip()

                quarto = consultar_quarto_por_numero(numero)

                if quarto is None:

                    print("Quarto não encontrado.")

                else:

                    disponivel = verificar_disponibilidade(
                        quarto["idquarto"],
                        data_entrada,
                        data_saida
                    )

                    if disponivel:
                        print("Quarto disponível para o período!")

                    else:
                        print("Quarto indisponível ou datas inválidas.")

            # CRIAR RESERVA
            elif opcao == "3":

                numero = int(input("Número do quarto: "))

                data_entrada = input(
                    "Data de entrada (AAAA-MM-DD): "
                ).strip()

                data_saida = input(
                    "Data de saída (AAAA-MM-DD): "
                ).strip()

                quarto = consultar_quarto_por_numero(numero)

                if quarto is None:

                    print("Quarto não encontrado.")

                else:

                    sucesso, resultado = criar_reserva(
                        idcliente,
                        quarto["idquarto"],
                        data_entrada,
                        data_saida
                    )

                    if sucesso:

                        print("\nRESERVA REALIZADA COM SUCESSO!")
                        print(f"Cliente: {nome_cliente}")
                        print(f"Quarto: {numero}")
                        print(f"Código da reserva: {resultado['idreserva']}")
                        print(f"Quantidade de noites: {resultado['noites']}")
                        print(
                            f"Valor da diária: "
                            f"R$ {resultado['preco_diaria']:.2f}"
                        )
                        print(
                            f"Valor total: "
                            f"R$ {resultado['valor_total']:.2f}"
                        )

                    else:

                        print(
                            f"\nNão foi possível realizar a reserva: "
                            f"{resultado}"
                        )

            # CANCELAR RESERVA
            elif opcao == "4":

                idreserva = int(input("Código da reserva: "))

                sucesso, mensagem = cancelar_reserva(
                    idreserva,
                    idcliente
                )

                print(mensagem)

            # CHECK-IN
            elif opcao == "5":

                idreserva = int(input("Código da reserva: "))

                sucesso, mensagem = realizar_checkin(
                    idreserva,
                    idcliente
                )

                print(mensagem)

            # CHECK-OUT
            elif opcao == "6":

                idreserva = int(input("Código da reserva: "))

                sucesso, mensagem = realizar_checkout(
                    idreserva,
                    idcliente
                )

                print(mensagem)

            # LISTAR RESERVAS
            elif opcao == "7":

                reservas = listar_reservas_cliente(idcliente)

                if not reservas:

                    print("Você ainda não possui reservas.")

                else:

                    print("\n--- MINHAS RESERVAS ---")

                    for reserva in reservas:

                        print("-" * 40)
                        print(f"Código: {reserva['idreserva']}")
                        print(f"Quarto: {reserva['numero']}")
                        print(f"Entrada: {reserva['data_entrada']}")
                        print(f"Saída: {reserva['data_saida']}")
                        print(
                            f"Diária: "
                            f"R$ {reserva['preco_diaria']:.2f}"
                        )
                        print(
                            f"Total: "
                            f"R$ {reserva['valor_total']:.2f}"
                        )
                        print(f"Status: {reserva['status']}")
                        print(f"Data da reserva: {reserva['data_reserva']}")

            # SAIR
            elif opcao == "0":

                print("\nEncerrando o módulo de reservas...")
                break

            else:

                print("Opção inválida. Tente novamente.")

        except ValueError:

            print(
                "Entrada inválida. Verifique os números "
                "e as datas informadas."
            )

        except sqlite3.Error as erro:

            print(f"Erro no banco de dados: {erro}")

        except FileNotFoundError as erro:

            print(erro)

        input("\nPressione ENTER para continuar...")


# --------------------------------------------------
# EXECUÇÃO DO MÓDULO
# --------------------------------------------------

if __name__ == "__main__":

    print("=" * 45)
    print("       INNKEEPER - SISTEMA DE RESERVAS")
    print("=" * 45)

    print(f"Banco de dados: {BANCO}")

    try:

        print("\n--- IDENTIFICAÇÃO DO CLIENTE ---")

        identificacao = input(
            "Informe seu login ou e-mail: "
        ).strip()

        senha = input("Informe sua senha: ")

        sucesso, resultado = autenticar_cliente(
            identificacao,
            senha
        )

        if sucesso:

            print(
                f"\nBem-vindo(a), {resultado['nome']}!"
            )

            menu_reservas(
                resultado["idcliente"],
                resultado["nome"]
            )

        else:

            print(f"\nAcesso negado: {resultado}")

    except FileNotFoundError as erro:

        print(erro)

    except sqlite3.Error as erro:

        print(f"Erro ao acessar o banco de dados: {erro}")

    except KeyboardInterrupt:

        print("\nSistema encerrado pelo usuário.")
