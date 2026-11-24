"""Interface de terminal do Simulador de Roteador Hierárquico."""

import os
import random
import sys

from core.models import Device, Packet, converter_para_bytes, formatar_tamanho
from core.dhcp import DHCPServer
from data.storage import carregar_estado, salvar_estado
from structures.hash_table import HashTable
from structures.tree import NetworkNode, RouterTree, Router
from structures.sorting import quicksort_hibrido


class Simulador:
    """Coordena dispositivos, DHCP, fila de pacotes e roteamento."""

    IP_CORE = "10.0.0.1"

    def __init__(self):
        self.tabela_dispositivos = HashTable(capacity=53)

        self.core = Device("R_Core", Simulador.IP_CORE, tipo="ROUTER")
        self._indexar_dispositivo(self.core)

        self.no_raiz = NetworkNode(self.core)
        self.arvore = RouterTree(self.no_raiz)
        self.roteador = Router(self.arvore, self.tabela_dispositivos)
        self.dhcp = DHCPServer(self.tabela_dispositivos, rede_base="10.0.0", inicio=10, fim=254)

    def _indexar_dispositivo(self, dispositivo: Device) -> None:
        self.tabela_dispositivos.insert(dispositivo.ip, dispositivo)
        self.tabela_dispositivos.insert(dispositivo.nome, dispositivo)

    def conectar_roteador_setor(self, nome: str) -> str:
        """Conecta um novo roteador de setor diretamente ao R_Core."""
        nome = nome.strip()
        if not nome:
            return "[ERRO] Nome do roteador de setor não pode ser vazio."
        if self.tabela_dispositivos.get(nome) is not None:
            return f"[ERRO] Já existe um dispositivo chamado '{nome}'."

        ip = self.dhcp.alocar_ip()
        if ip is None:
            return "[ERRO] Pool de IPs esgotado."

        novo_router = Device(nome, ip, tipo="ROUTER")
        self.no_raiz.adicionar_filho(NetworkNode(novo_router))
        self._indexar_dispositivo(novo_router)
        return f"[OK] Roteador '{nome}' conectado ao R_Core com IP {ip}."

    def conectar_pc(self, nome: str, nome_setor: str) -> str:
        """Conecta um novo PC a um roteador de setor existente."""
        nome = nome.strip()
        nome_setor = nome_setor.strip()
        if not nome:
            return "[ERRO] Nome do PC não pode ser vazio."
        if not nome_setor:
            return "[ERRO] Nome do setor não pode ser vazio."
        if self.tabela_dispositivos.get(nome) is not None:
            return f"[ERRO] Já existe um dispositivo chamado '{nome}'."

        ip = self.dhcp.alocar_ip()
        if ip is None:
            return "[ERRO] Pool de IPs esgotado."

        novo_pc = Device(nome, ip, tipo="PC")
        if not self.arvore.adicionar_pc(nome_setor, NetworkNode(novo_pc)):
            self.dhcp.liberar_ip(ip)
            return f"[ERRO] Setor '{nome_setor}' não encontrado."

        self._indexar_dispositivo(novo_pc)
        return f"[OK] PC '{nome}' conectado ao setor '{nome_setor}' com IP {ip}."

    def desconectar_pc(self, identificador: str) -> str:
        """Desconecta um PC da rede e libera seu IP no DHCP."""
        identificador = identificador.strip()
        if not identificador:
            return "[ERRO] Informe o nome ou IP do PC."

        dispositivo = self.tabela_dispositivos.get(identificador)
        if dispositivo is None:
            return f"[ERRO] Dispositivo '{identificador}' não encontrado."
        if dispositivo.tipo != "PC":
            return f"[ERRO] '{dispositivo.nome}' é um roteador; apenas PCs podem ser desconectados."

        if not self.arvore.remover_pc(dispositivo.ip):
            return f"[ERRO] Falha ao remover '{dispositivo.nome}'."

        self.tabela_dispositivos.remove(dispositivo.ip)
        self.tabela_dispositivos.remove(dispositivo.nome)
        self.dhcp.liberar_ip(dispositivo.ip)
        return f"[OK] PC '{dispositivo.nome}' ({dispositivo.ip}) desconectado."

    def listar_dispositivos(self) -> list[Device]:
        """Retorna todos os dispositivos conectados ordenados por IP."""
        vistos = HashTable(capacity=53)
        dispositivos = []
        for _chave, valor in self.tabela_dispositivos.to_list():
            if isinstance(valor, Device) and not vistos.contains(valor.ip):
                vistos.insert(valor.ip, True)
                dispositivos.append(valor)
        quicksort_hibrido(
            dispositivos,
            chave=lambda d: tuple(int(octeto) for octeto in d.ip.split(".")),
        )
        return dispositivos

    def enviar_arquivo(
        self,
        origem: str,
        destino: str,
        arquivo: str,
        valor_tamanho: float,
        unidade: str,
    ) -> str:
        """Instancia o pacote do arquivo, divide em pacotes de até 1500 B e envia para a fila."""
        arquivo = arquivo.strip()
        if not arquivo:
            return "[ERRO] Nome do arquivo não pode ser vazio."

        dispositivo_origem = self.tabela_dispositivos.get(origem.strip())
        dispositivo_destino = self.tabela_dispositivos.get(destino.strip())

        if dispositivo_origem is None:
            return f"[ERRO] Origem '{origem}' não encontrada."
        if dispositivo_destino is None:
            return f"[ERRO] Destino '{destino}' não encontrado."

        try:
            tamanho_bytes = converter_para_bytes(valor_tamanho, unidade)
            pacote_inicial = Packet(
                dispositivo_origem.ip,
                dispositivo_destino.ip,
                arquivo,
                tamanho_bytes,
            )
            partes = pacote_inicial.dividir()
            del pacote_inicial
        except ValueError as erro:
            return f"[ERRO] {erro}"

        if len(partes) > 1:
            random.shuffle(partes)

        for pacote in partes:
            self.roteador.fila_transmissao.enqueue(pacote)

        linhas = [f"[OK] Arquivo '{arquivo}' ({formatar_tamanho(tamanho_bytes)}) enviado para a fila:"]
        if len(partes) <= 20:
            for pacote in partes:
                linhas.append(f"  Pacote {pacote.seq} enfileirado ({formatar_tamanho(pacote.tamanho)})")
        else:
            for pacote in partes[:10]:
                linhas.append(f"  Pacote {pacote.seq} enfileirado ({formatar_tamanho(pacote.tamanho)})")
            linhas.append(f"  ... (+{len(partes) - 15} pacotes enfileirados)")
            for pacote in partes[-5:]:
                linhas.append(f"  Pacote {pacote.seq} enfileirado ({formatar_tamanho(pacote.tamanho)})")

        linhas.append(f"  Total na fila: {self.roteador.fila_transmissao.size()}")
        return "\n".join(linhas)


BANNER = """==========================================================================
  SIMULADOR DE ROTEADOR HIERÁRQUICO
  UFAL - Campus Arapiraca | Ciência da Computação | Estrutura de Dados
  Autores: José Luiz Ferreira Neto e Luiz Gustavo Dantas Leão
=========================================================================="""

TITULOS_OPCOES = {
    "1": "TOPOLOGIA DA REDE",
    "2": "CONECTAR ROTEADOR DE SETOR",
    "3": "CONECTAR PC A UM SETOR",
    "4": "DESCONECTAR PC",
    "5": "DISPOSITIVOS CONECTADOS",
    "6": "ENVIAR ARQUIVO",
    "7": "PROCESSAR 1 PACOTE",
    "8": "PROCESSAR 10 PACOTES",
    "9": "PROCESSAR TODOS OS PACOTES",
    "10": "PING",
    "11": "CAIXA DE ENTRADA",
}

OPCOES_UNIDADE = {
    "1": "B",
    "2": "KB",
    "3": "MB",
    "4": "GB",
    "5": "TB",
    "B": "B",
    "KB": "KB",
    "MB": "MB",
    "GB": "GB",
    "TB": "TB",
}

MENU = """------------------------------- MENU -------------------------------------
 [1]  Visualizar topologia da rede
 [2]  Conectar roteador de setor
 [3]  Conectar PC a um setor
 [4]  Desconectar PC
 [5]  Listar dispositivos conectados
 [6]  Enviar arquivo
 [7]  Processar 1 pacote da fila
 [8]  Processar 10 pacotes da fila
 [9]  Processar todos os pacotes da fila
 [10] Ping
 [11] Ver caixa de entrada
 [0]  Sair
--------------------------------------------------------------------------"""


def configurar_terminal() -> None:
    """Configura UTF-8 no terminal do Windows."""
    if os.name == "nt":
        for stream in (sys.stdout, sys.stdin):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")


def limpar_tela() -> None:
    """Limpa a tela no Windows ou Linux/macOS."""
    comando = "cls" if os.name == "nt" else "clear"
    if os.system(comando) != 0:
        print("\033[2J\033[H", end="", flush=True)


def pausar() -> None:
    input("\nPressione ENTER para voltar ao menu...")


def cabecalho_operacao(opcao: str) -> None:
    limpar_tela()
    titulo = TITULOS_OPCOES.get(opcao, "OPERAÇÃO")
    print("=" * 74)
    print(f"  [{opcao}] {titulo}")
    print("=" * 74 + "\n")


def barra_status(sim: Simulador) -> str:
    total_disp = len(sim.listar_dispositivos())
    fila_qtd = sim.roteador.fila_transmissao.size()
    em_transito = sim.roteador.total_pacotes_em_transito()
    proximo = sim.roteador.fila_transmissao.peek()
    dhcp_livres = sim.dhcp.ips_disponiveis_restantes()

    linha = (
        f" STATUS | Core: {Simulador.IP_CORE} | Dispositivos: {total_disp} | "
        f"Fila: {fila_qtd} | Em trânsito: {em_transito} | DHCP livres: {dhcp_livres}"
    )
    if proximo is not None:
        linha += f"\n PRÓXIMO NA FILA | {proximo}"
    return linha


def pedir_unidade_tamanho() -> str | None:
    print("\nUnidade de tamanho:")
    print("  [1] Bytes (B)")
    print("  [2] Kilobytes (KB)")
    print("  [3] Megabytes (MB)")
    print("  [4] Gigabytes (GB)")
    print("  [5] Terabytes (TB)")

    while True:
        escolha = input("Unidade (1-5 ou B/KB/MB/GB/TB, vazio para cancelar): ").strip().upper()
        if escolha == "":
            return None
        if escolha in OPCOES_UNIDADE:
            return OPCOES_UNIDADE[escolha]
        print("[ERRO] Unidade inválida.")


def pedir_numero_positivo(mensagem: str) -> float | None:
    while True:
        texto = input(mensagem).strip().replace(",", ".")
        if texto == "":
            return None
        try:
            valor = float(texto)
        except ValueError:
            print("[ERRO] Valor inválido.")
            continue

        if valor <= 0:
            print("[ERRO] O valor deve ser maior que zero.")
            continue
        return valor


def executar_cli() -> None:
    configurar_terminal()
    sim = Simulador()
    carregar_estado(sim)

    while True:
        limpar_tela()
        print(BANNER)
        print(barra_status(sim))
        print(MENU)
        opcao = input("simulador@R_Core:~$ ").strip()

        if opcao == "0":
            salvar_estado(sim)
            limpar_tela()
            print("Estado salvo em data/estado_rede.json. Encerrando o simulador.")
            break

        if opcao not in TITULOS_OPCOES:
            limpar_tela()
            print(f"[ERRO] Opção '{opcao}' inválida.")
            pausar()
            continue

        cabecalho_operacao(opcao)

        if opcao == "1":
            print(sim.arvore.imprimir_arvore())

        elif opcao == "2":
            nome = input("Nome do roteador de setor (ex: R_Lab1): ").strip()
            print("\n" + sim.conectar_roteador_setor(nome))

        elif opcao == "3":
            nome = input("Nome do PC (ex: PC1): ").strip()
            setor = input("Nome do roteador de setor: ").strip()
            print("\n" + sim.conectar_pc(nome, setor))

        elif opcao == "4":
            alvo = input("Nome ou IP do PC: ").strip()
            print("\n" + sim.desconectar_pc(alvo))

        elif opcao == "5":
            dispositivos = sim.listar_dispositivos()
            if not dispositivos:
                print("Nenhum dispositivo conectado.")
            else:
                print(f"{len(dispositivos)} dispositivo(s) conectado(s):\n")
                for d in dispositivos:
                    print(f"  - {d.nome:<12} {d.ip:<14} [{d.tipo:<6}]  MAC={d.mac}")

        elif opcao == "6":
            origem = input("Origem (nome ou IP): ").strip()
            destino = input("Destino (nome ou IP): ").strip()
            arquivo = input("Nome do arquivo: ").strip()
            unidade = pedir_unidade_tamanho()
            if unidade is None:
                print("\n[AVISO] Envio cancelado.")
            else:
                valor = pedir_numero_positivo(f"Tamanho em {unidade} (vazio para cancelar): ")
                if valor is None:
                    print("\n[AVISO] Envio cancelado.")
                else:
                    print("\n" + sim.enviar_arquivo(origem, destino, arquivo, valor, unidade))

        elif opcao == "7":
            print(sim.roteador.processar_proximo())

        elif opcao == "8":
            for linha in sim.roteador.processar_lote(10):
                print(linha)

        elif opcao == "9":
            logs = sim.roteador.processar_tudo()
            if len(logs) <= 25:
                for linha in logs:
                    print(linha)
            else:
                relevantes = [l for l in logs if not l.startswith("[EM TRÂNSITO]")]
                print(f"Processados {len(logs)} pacotes da fila:\n")
                for linha in relevantes:
                    print(linha)

        elif opcao == "10":
            origem = input("Origem (nome ou IP): ").strip()
            destino = input("Destino (nome ou IP): ").strip()
            print("\n" + sim.roteador.ping(origem, destino))

        elif opcao == "11":
            alvo = input("Dispositivo (nome ou IP): ").strip()
            dispositivo = sim.tabela_dispositivos.get(alvo)
            if dispositivo is None:
                print(f"\n[ERRO] Dispositivo '{alvo}' não encontrado.")
            elif not dispositivo.caixa_entrada:
                print(f"\nCaixa de entrada de {dispositivo.nome} está vazia.")
            else:
                print(f"\nCaixa de entrada de {dispositivo.nome} ({len(dispositivo.caixa_entrada)} arquivo(s)):\n")
                for pacote in dispositivo.caixa_entrada:
                    print(f"  - {pacote}")

        pausar()


if __name__ == "__main__":
    try:
        executar_cli()
    except (KeyboardInterrupt, EOFError):
        print("\nSimulador interrompido.")