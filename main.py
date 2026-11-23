#!/usr/bin/env python3
"""
Simulador de Roteador Hierárquico (CLI)

Universidade Federal de Alagoas (UFAL) - Campus Arapiraca
Ciência da Computação (2º Período) - Estrutura de Dados
Autores: José Luiz Ferreira Neto e Luiz Gustavo Dantas Leão

Executar a partir da raiz do projeto: python3 main.py
"""

from core.models import Device, Packet
from core.dhcp import DHCPServer
from structures.hash_table import HashTable
from structures.tree import NetworkNode, RouterTree, Router
from structures.sorting import ordenar_pacotes_por_tamanho


class Simulador:
    """Orquestra Tabela Hash, Árvore N-ária, Filas e Ordenação; guarda o estado da sessão."""

    IP_CORE = "10.0.0.1"

    def __init__(self):
        self.tabela_dispositivos = HashTable(capacity=53)

        self.core = Device("R_Core", Simulador.IP_CORE, tipo="ROUTER")
        self._indexar_dispositivo(self.core)

        self.no_raiz = NetworkNode(self.core)
        self.arvore = RouterTree(self.no_raiz)
        self.roteador = Router(self.arvore, self.tabela_dispositivos)

        self.dhcp = DHCPServer(self.tabela_dispositivos, rede_base="10.0.0", inicio=10, fim=254)

        self.lote_upload: list[Packet] = []  # pacotes aguardando ordenação/despacho

    # ------------------------------------------------------------------ #
    # Dispositivos
    # ------------------------------------------------------------------ #

    def _indexar_dispositivo(self, dispositivo: Device) -> None:
        self.tabela_dispositivos.insert(dispositivo.ip, dispositivo)
        self.tabela_dispositivos.insert(dispositivo.nome, dispositivo)

    def conectar_roteador_setor(self, nome: str) -> str:
        if self.tabela_dispositivos.get(nome) is not None:
            return f"[ERRO] Já existe um dispositivo chamado '{nome}'."

        ip = self.dhcp.alocar_ip()
        if ip is None:
            return "[ERRO] Pool de IPs esgotado."

        novo_router = Device(nome, ip, tipo="ROUTER")
        self.no_raiz.adicionar_filho(NetworkNode(novo_router))
        self._indexar_dispositivo(novo_router)
        return f"[OK] Roteador de setor '{nome}' conectado ao R_Core com IP {ip}."

    def conectar_pc(self, nome: str, nome_setor: str) -> str:
        if self.tabela_dispositivos.get(nome) is not None:
            return f"[ERRO] Já existe um dispositivo chamado '{nome}'."

        ip = self.dhcp.alocar_ip()
        if ip is None:
            return "[ERRO] Pool de IPs esgotado."

        novo_pc = Device(nome, ip, tipo="PC")
        no_pc = NetworkNode(novo_pc)

        sucesso = self.arvore.adicionar_pc(nome_setor, no_pc)
        if not sucesso:
            self.dhcp.liberar_ip(ip)  # devolve o IP reservado, conexão não aconteceu
            return f"[ERRO] Setor '{nome_setor}' não encontrado (ou não é um roteador)."

        self._indexar_dispositivo(novo_pc)
        return f"[OK] PC '{nome}' conectado ao setor '{nome_setor}' com IP {ip}."

    def desconectar_pc(self, identificador: str) -> str:
        dispositivo = self.tabela_dispositivos.get(identificador)
        if dispositivo is None:
            return f"[ERRO] Dispositivo '{identificador}' não encontrado."
        if dispositivo.tipo != "PC":
            return f"[ERRO] '{dispositivo.nome}' é um roteador de setor; apenas PCs podem ser desconectados."

        sucesso = self.arvore.remover_pc(dispositivo.ip)
        if not sucesso:
            return f"[ERRO] Falha ao remover '{dispositivo.nome}' da árvore."

        self.tabela_dispositivos.remove(dispositivo.ip)
        self.tabela_dispositivos.remove(dispositivo.nome)
        self.dhcp.liberar_ip(dispositivo.ip)
        return f"[OK] PC '{dispositivo.nome}' ({dispositivo.ip}) desconectado da rede."

    def listar_dispositivos(self) -> list[Device]:
        """Lista cada Device uma única vez (ele está indexado 2x na tabela: por IP e por Nome)."""
        vistos_ip = set()
        dispositivos = []
        for _chave, valor in self.tabela_dispositivos.to_list():
            if isinstance(valor, Device) and valor.ip not in vistos_ip:
                vistos_ip.add(valor.ip)
                dispositivos.append(valor)
        dispositivos.sort(key=lambda d: d.ip)
        return dispositivos

    # ------------------------------------------------------------------ #
    # Pacotes / Fila de upload
    # ------------------------------------------------------------------ #

    def criar_pacote(self, origem: str, destino: str, arquivo: str, tamanho: int) -> str:
        dispositivo_origem = self.tabela_dispositivos.get(origem)
        dispositivo_destino = self.tabela_dispositivos.get(destino)

        if dispositivo_origem is None:
            return f"[ERRO] Origem '{origem}' não encontrada."
        if dispositivo_destino is None:
            return f"[ERRO] Destino '{destino}' não encontrado."
        if tamanho <= 0:
            return "[ERRO] Tamanho do pacote deve ser maior que zero."

        pacote = Packet(dispositivo_origem.ip, dispositivo_destino.ip, arquivo, tamanho)
        self.lote_upload.append(pacote)
        return (
            f"[OK] Pacote '{arquivo}' ({tamanho}MB) adicionado ao lote de upload "
            f"({len(self.lote_upload)} pacote(s) pendente(s) de ordenação/despacho)."
        )

    def ordenar_lote_upload(self) -> str:
        if not self.lote_upload:
            return "[AVISO] Lote de upload vazio. Nada para ordenar."

        ordenar_pacotes_por_tamanho(self.lote_upload)
        resumo = ", ".join(f"{p.arquivo}({p.tamanho}MB)" for p in self.lote_upload)
        return f"[OK] Lote ordenado por tamanho - SJF (QuickSort Híbrido):\n  {resumo}"

    def despachar_lote_para_fila(self) -> str:
        if not self.lote_upload:
            return "[AVISO] Lote de upload vazio. Nada para despachar."

        quantidade = self.roteador.enfileirar_pacotes(self.lote_upload)
        self.lote_upload = []
        return f"[OK] {quantidade} pacote(s) movido(s) do lote para a Fila FIFO de transmissão."


# ---------------------------------------------------------------------- #
# Camada de interface (CLI)
# ---------------------------------------------------------------------- #

BANNER = """
==========================================================================
  SIMULADOR DE ROTEADOR HIERARQUICO (CLI)
  UFAL - Campus Arapiraca | Ciencia da Computacao | Estrutura de Dados
  Autores: Jose Luiz Ferreira Neto e Luiz Gustavo Dantas Leao
==========================================================================
"""

MENU = """
------------------------------- MENU -------------------------------
 [1] Visualizar topologia da rede (árvore)
 [2] Conectar roteador de setor ao R_Core
 [3] Conectar PC a um setor
 [4] Desconectar PC
 [5] Listar dispositivos conectados (Tabela Hash)
 [6] Criar pacote (adicionar ao lote de upload)
 [7] Ordenar lote de upload por tamanho (QuickSort Híbrido - SJF)
 [8] Despachar lote ordenado para a Fila FIFO de transmissão
 [9] Processar PRÓXIMO pacote da fila (1 passo)
 [10] Processar TODOS os pacotes da fila
 [11] Ping (rota BFS entre dois dispositivos)
 [12] Ver caixa de entrada de um dispositivo
 [0] Sair
----------------------------------------------------------------------
"""


def pedir_inteiro(mensagem: str, minimo: int | None = None) -> int | None:
    """Lê um inteiro do usuário com validação; retorna None se a entrada for vazia (cancelar)."""
    texto = input(mensagem).strip()
    if texto == "":
        return None
    try:
        valor = int(texto)
    except ValueError:
        print("[ERRO] Valor inválido, informe um número inteiro.")
        return pedir_inteiro(mensagem, minimo)

    if minimo is not None and valor < minimo:
        print(f"[ERRO] O valor deve ser >= {minimo}.")
        return pedir_inteiro(mensagem, minimo)
    return valor


def executar_cli() -> None:
    sim = Simulador()
    print(BANNER)
    print(f"Rede inicializada com o roteador raiz R_Core ({Simulador.IP_CORE}).")

    while True:
        print(MENU)
        opcao = input("Escolha uma opção: ").strip()

        if opcao == "0":
            print("Encerrando o simulador. Até logo!")
            break

        elif opcao == "1":
            print("\n" + sim.arvore.imprimir_arvore())

        elif opcao == "2":
            nome = input("Nome do novo roteador de setor (ex: R_Lab1): ").strip()
            print(sim.conectar_roteador_setor(nome))

        elif opcao == "3":
            nome = input("Nome do novo PC (ex: PC1): ").strip()
            setor = input("Nome do roteador de setor ao qual conectar: ").strip()
            print(sim.conectar_pc(nome, setor))

        elif opcao == "4":
            alvo = input("Nome ou IP do PC a desconectar: ").strip()
            print(sim.desconectar_pc(alvo))

        elif opcao == "5":
            dispositivos = sim.listar_dispositivos()
            if not dispositivos:
                print("Nenhum dispositivo conectado.")
            else:
                print(f"\n{len(dispositivos)} dispositivo(s) conectado(s):")
                for d in dispositivos:
                    print(f"  - {d.nome:<12} {d.ip:<14} [{d.tipo}]  MAC={d.mac}")

        elif opcao == "6":
            origem = input("Nome ou IP de origem: ").strip()
            destino = input("Nome ou IP de destino: ").strip()
            arquivo = input("Nome do arquivo: ").strip()
            tamanho = pedir_inteiro("Tamanho do arquivo em MB: ", minimo=1)
            if tamanho is not None:
                print(sim.criar_pacote(origem, destino, arquivo, tamanho))

        elif opcao == "7":
            print(sim.ordenar_lote_upload())

        elif opcao == "8":
            print(sim.despachar_lote_para_fila())

        elif opcao == "9":
            print(sim.roteador.processar_proximo())

        elif opcao == "10":
            for linha in sim.roteador.processar_tudo():
                print(linha)

        elif opcao == "11":
            origem = input("Nome ou IP de origem: ").strip()
            destino = input("Nome ou IP de destino: ").strip()
            print(sim.roteador.ping(origem, destino))

        elif opcao == "12":
            alvo = input("Nome ou IP do dispositivo: ").strip()
            dispositivo = sim.tabela_dispositivos.get(alvo)
            if dispositivo is None:
                print(f"[ERRO] Dispositivo '{alvo}' não encontrado.")
            elif not dispositivo.caixa_entrada:
                print(f"Caixa de entrada de {dispositivo.nome} está vazia.")
            else:
                print(f"\nCaixa de entrada de {dispositivo.nome} ({len(dispositivo.caixa_entrada)} pacote(s)):")
                for pacote in dispositivo.caixa_entrada:
                    print(f"  - {pacote}")

        else:
            print("[ERRO] Opção inválida.")


if __name__ == "__main__":
    try:
        executar_cli()
    except (KeyboardInterrupt, EOFError):
        print("\nSimulador interrompido pelo usuário.")