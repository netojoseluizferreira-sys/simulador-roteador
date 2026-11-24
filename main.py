"""Interface de terminal do Simulador de Roteador Hierárquico."""

import os
import random
import sys

from core.models import Device, Packet, converter_para_bytes, formatar_tamanho
from core.dhcp import DHCPServer
from core.sockets import (
    PORTA_PADRAO,
    PORTA_SIMULADOR,
    ReceptorSimuladorUDP,
    ler_arquivo_transfer,
    listar_arquivos_transfer,
    obter_ip_local,
)
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

    def conectar_pc(
        self,
        nome: str,
        nome_setor: str,
        modo: str = "SIMULADO",
        host_real: str | None = None,
        porta_real: int | None = None,
    ) -> str:
        """Conecta um PC simulado ou real (via cabo/rede) a um roteador de setor."""
        nome = nome.strip()
        nome_setor = nome_setor.strip()
        if not nome:
            return "[ERRO] Nome do PC não pode ser vazio."
        if not nome_setor:
            return "[ERRO] Nome do setor não pode ser vazio."
        if self.tabela_dispositivos.get(nome) is not None:
            return f"[ERRO] Já existe um dispositivo chamado '{nome}'."
        if modo == "REAL" and (not host_real or not host_real.strip()):
            return "[ERRO] Informe o IP físico do PC real."

        ip = self.dhcp.alocar_ip()
        if ip is None:
            return "[ERRO] Pool de IPs esgotado."

        novo_pc = Device(
            nome,
            ip,
            tipo="PC",
            modo=modo,
            host_real=host_real,
            porta_real=porta_real if modo == "REAL" else None,
        )
        if not self.arvore.adicionar_pc(nome_setor, NetworkNode(novo_pc)):
            self.dhcp.liberar_ip(ip)
            return f"[ERRO] Setor '{nome_setor}' não encontrado."

        self._indexar_dispositivo(novo_pc)
        if modo == "REAL":
            return (
                f"[OK] PC real '{nome}' ({host_real}:{porta_real}) conectado ao setor "
                f"'{nome_setor}' com IP interno {ip}."
            )
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

    def _enfileirar_pacote_inicial(self, pacote_inicial: Packet, descricao: str) -> str:
        tamanho_total = pacote_inicial.tamanho
        partes = pacote_inicial.dividir()
        del pacote_inicial

        if len(partes) > 1:
            random.shuffle(partes)

        for pacote in partes:
            self.roteador.fila_transmissao.enqueue(pacote)

        linhas = [f"[OK] {descricao} ({formatar_tamanho(tamanho_total)}) enviado para a fila:"]
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

    def _validar_origem_destino(self, origem: str, destino: str):
        disp_origem = self.tabela_dispositivos.get(origem.strip())
        disp_destino = self.tabela_dispositivos.get(destino.strip())
        if disp_origem is None:
            return None, None, f"[ERRO] Origem '{origem}' não encontrada."
        if disp_destino is None:
            return None, None, f"[ERRO] Destino '{destino}' não encontrado."
        return disp_origem, disp_destino, None

    def enviar_arquivo(
        self,
        origem: str,
        destino: str,
        arquivo: str,
        valor_tamanho: float,
        unidade: str,
    ) -> str:
        """Envia um arquivo simulado (apenas tamanho)."""
        arquivo = arquivo.strip()
        if not arquivo:
            return "[ERRO] Nome do arquivo não pode ser vazio."

        disp_origem, disp_destino, erro = self._validar_origem_destino(origem, destino)
        if erro:
            return erro

        try:
            tamanho_bytes = converter_para_bytes(valor_tamanho, unidade)
            pacote_inicial = Packet(disp_origem.ip, disp_destino.ip, arquivo, tamanho_bytes)
            return self._enfileirar_pacote_inicial(pacote_inicial, f"Arquivo '{arquivo}'")
        except ValueError as e:
            return f"[ERRO] {e}"

    def enviar_arquivo_real(self, origem: str, destino: str, nome_arquivo: str) -> str:
        """Lê um arquivo real da pasta transfer/ e envia seus bytes pela rede."""
        nome_arquivo = nome_arquivo.strip()
        if not nome_arquivo:
            return "[ERRO] Informe o nome do arquivo em transfer/."

        disp_origem, disp_destino, erro = self._validar_origem_destino(origem, destino)
        if erro:
            return erro

        try:
            dados = ler_arquivo_transfer(nome_arquivo)
            if not dados:
                return f"[ERRO] Arquivo '{nome_arquivo}' está vazio (0 B)."
            pacote_inicial = Packet(
                disp_origem.ip,
                disp_destino.ip,
                nome_arquivo,
                len(dados),
                payload=dados,
            )
            return self._enfileirar_pacote_inicial(pacote_inicial, f"Arquivo real '{nome_arquivo}'")
        except (FileNotFoundError, OSError, ValueError) as e:
            return f"[ERRO] {e}"

    def enviar_mensagem(self, origem: str, destino: str, texto: str) -> str:
        """Envia uma mensagem de texto e gera arquivo .txt no destinatário."""
        texto = texto.strip()
        if not texto:
            return "[ERRO] A mensagem não pode ser vazia."

        disp_origem, disp_destino, erro = self._validar_origem_destino(origem, destino)
        if erro:
            return erro

        dados = texto.encode("utf-8")
        nome_msg = f"msg_{disp_origem.nome}_para_{disp_destino.nome}_{Packet._contador_id + 1}.txt"
        try:
            pacote_inicial = Packet(
                disp_origem.ip,
                disp_destino.ip,
                nome_msg,
                len(dados),
                payload=dados,
                eh_mensagem=True,
            )
            return self._enfileirar_pacote_inicial(pacote_inicial, f"Mensagem '{nome_msg}'")
        except ValueError as e:
            return f"[ERRO] {e}"


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
    "6": "ENVIAR ARQUIVO OU MENSAGEM",
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
 [6]  Enviar arquivo ou mensagem
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


def barra_status(sim: Simulador, receptor: ReceptorSimuladorUDP | None = None, ip_local: str = "") -> str:
    total_disp = len(sim.listar_dispositivos())
    fila_qtd = sim.roteador.fila_transmissao.size()
    em_transito = sim.roteador.total_pacotes_em_transito()
    proximo = sim.roteador.fila_transmissao.peek()
    dhcp_livres = sim.dhcp.ips_disponiveis_restantes()

    linha = (
        f" STATUS | Core: {Simulador.IP_CORE} | Dispositivos: {total_disp} | "
        f"Fila: {fila_qtd} | Em trânsito: {em_transito} | DHCP livres: {dhcp_livres}"
    )
    if receptor is not None and receptor.ativo:
        linha += f"\n REDE   | UDP ativo em {ip_local}:{receptor.porta} | Recebidos via rede: {receptor.total_recebidos}"
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


def pedir_porta(padrao: int = PORTA_PADRAO) -> int:
    while True:
        texto = input(f"Porta do PC real (ENTER para {padrao}): ").strip()
        if texto == "":
            return padrao
        try:
            porta = int(texto)
            if 1 <= porta <= 65535:
                return porta
        except ValueError:
            pass
        print("[ERRO] Informe uma porta válida entre 1 e 65535.")


def executar_cli() -> None:
    configurar_terminal()
    sim = Simulador()
    carregar_estado(sim)

    ip_local = obter_ip_local()
    receptor = ReceptorSimuladorUDP(sim, porta=PORTA_SIMULADOR)
    receptor.iniciar()

    try:
        while True:
            limpar_tela()
            print(BANNER)
            print(barra_status(sim, receptor, ip_local))
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
                print("Tipo de PC:")
                print("  [1] PC simulado")
                print("  [2] PC real (via cabo/rede)")
                tipo_pc = input("Escolha (1-2): ").strip()

                nome = input("Nome do PC (ex: PC1): ").strip()
                setor = input("Nome do roteador de setor: ").strip()

                if tipo_pc == "2":
                    host_real = input("IP físico do PC real (ex: 192.168.50.2 ou 127.0.0.1): ").strip()
                    porta_real = pedir_porta()
                    print("\n" + sim.conectar_pc(nome, setor, modo="REAL", host_real=host_real, porta_real=porta_real))
                elif tipo_pc == "1":
                    print("\n" + sim.conectar_pc(nome, setor, modo="SIMULADO"))
                else:
                    print("\n[ERRO] Tipo de PC inválido.")

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
                        info_real = f"  REAL->{d.host_real}:{d.porta_real}" if d.modo == "REAL" else ""
                        print(f"  - {d.nome:<12} {d.ip:<14} [{d.tipo:<6}]  MAC={d.mac}{info_real}")

            elif opcao == "6":
                print("Tipo de envio:")
                print("  [1] Arquivo simulado")
                print("  [2] Arquivo real (pasta transfer/)")
                print("  [3] Mensagem de texto")
                tipo_envio = input("Escolha (1-3): ").strip()

                if tipo_envio not in ("1", "2", "3"):
                    print("\n[ERRO] Tipo de envio inválido.")
                else:
                    origem = input("Origem (nome ou IP): ").strip()
                    destino = input("Destino (nome ou IP): ").strip()

                    if tipo_envio == "1":
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

                    elif tipo_envio == "2":
                        disponiveis = listar_arquivos_transfer()
                        if not disponiveis:
                            print("\n[AVISO] Nenhum arquivo encontrado na pasta transfer/.")
                            print("Coloque o arquivo desejado em transfer/ e tente novamente.")
                        else:
                            print("\nArquivos disponíveis em transfer/:")
                            for idx, nome_arq in enumerate(disponiveis, start=1):
                                print(f"  [{idx}] {nome_arq}")
                            escolha = input("Número ou nome do arquivo (vazio para cancelar): ").strip()
                            if not escolha:
                                print("\n[AVISO] Envio cancelado.")
                            else:
                                if escolha.isdigit() and 1 <= int(escolha) <= len(disponiveis):
                                    nome_arq = disponiveis[int(escolha) - 1]
                                else:
                                    nome_arq = escolha
                                print("\n" + sim.enviar_arquivo_real(origem, destino, nome_arq))

                    elif tipo_envio == "3":
                        texto = input("Digite a mensagem: ").strip()
                        print("\n" + sim.enviar_mensagem(origem, destino, texto))

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
                    print(f"\nCaixa de entrada de {dispositivo.nome} ({len(dispositivo.caixa_entrada)} item(ns)):\n")
                    for pacote in dispositivo.caixa_entrada:
                        print(f"  - {pacote}")
                        if pacote.eh_mensagem and pacote.payload is not None:
                            texto = pacote.payload.decode("utf-8", errors="replace")
                            print(f"    Mensagem: {texto}")
                        if pacote.caminho_salvo:
                            print(f"    Arquivo:  {pacote.caminho_salvo}")

            pausar()
    finally:
        receptor.parar()


if __name__ == "__main__":
    try:
        executar_cli()
    except (KeyboardInterrupt, EOFError):
        print("\nSimulador interrompido.")