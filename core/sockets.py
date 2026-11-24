"""Camada de sockets UDP bidirecional e transferência real de arquivos e mensagens."""

import json
import os
import random
import socket
import struct
import threading
import time

from core.models import Packet, formatar_tamanho
from structures.hash_table import HashTable
from structures.sorting import quicksort_hibrido

PORTA_PADRAO = 5000
PORTA_SIMULADOR = 5001
TIMEOUT_UDP = 2.0
TENTATIVAS_UDP = 3
BUFFER_UDP = 65535

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_TRANSFER = os.path.join(RAIZ_PROJETO, "transfer")
PASTA_PCS_SIMULADOS = os.path.join(RAIZ_PROJETO, "data", "pcs")
PASTA_RECEBIDOS_REAL = os.path.join(RAIZ_PROJETO, "data", "recebidos")


def _nome_seguro(nome: str) -> str:
    """Remove separadores de caminho para evitar escrita fora da pasta destino."""
    return os.path.basename(nome.strip()).replace("..", "_")


def listar_arquivos_transfer() -> list[str]:
    """Lista os arquivos disponíveis na pasta transfer/ (ignorando .gitkeep)."""
    os.makedirs(PASTA_TRANSFER, exist_ok=True)
    arquivos = []
    for item in sorted(os.listdir(PASTA_TRANSFER)):
        caminho = os.path.join(PASTA_TRANSFER, item)
        if item != ".gitkeep" and os.path.isfile(caminho):
            arquivos.append(item)
    return arquivos


def ler_arquivo_transfer(nome_arquivo: str) -> bytes:
    """Lê os bytes de um arquivo real localizado na pasta transfer/."""
    nome_limpo = _nome_seguro(nome_arquivo)
    caminho = os.path.join(PASTA_TRANSFER, nome_limpo)
    if not os.path.isfile(caminho):
        raise FileNotFoundError(f"Arquivo '{nome_limpo}' não encontrado na pasta transfer/.")
    with open(caminho, "rb") as arquivo:
        return arquivo.read()


def garantir_pasta_pc(nome_pc: str) -> str:
    """Garante a existência da pasta dedicada de um PC simulado em data/pcs/."""
    pasta = os.path.join(PASTA_PCS_SIMULADOS, _nome_seguro(nome_pc))
    os.makedirs(pasta, exist_ok=True)
    return pasta


def salvar_arquivo_pc_simulado(nome_pc: str, nome_arquivo: str, dados: bytes) -> str:
    """Salva um arquivo real na pasta do PC simulado em data/pcs/<nome_pc>/."""
    pasta = garantir_pasta_pc(nome_pc)
    caminho = os.path.join(pasta, _nome_seguro(nome_arquivo))
    with open(caminho, "wb") as arquivo:
        arquivo.write(dados)
    return caminho


def salvar_mensagem_pc_simulado(
    nome_pc: str,
    origem: str,
    nome_arquivo: str,
    texto: str,
) -> str:
    """Salva uma mensagem como arquivo .txt na pasta do PC simulado."""
    pasta = garantir_pasta_pc(nome_pc)
    nome_limpo = _nome_seguro(nome_arquivo)
    if not nome_limpo.lower().endswith(".txt"):
        nome_limpo += ".txt"
    caminho = os.path.join(pasta, nome_limpo)
    conteudo = f"De: {origem}\nPara: {nome_pc}\n\n{texto}\n"
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    return caminho


def _empacotar_datagrama(cabecalho: dict, payload: bytes = b"") -> bytes:
    meta = json.dumps(cabecalho, ensure_ascii=False).encode("utf-8")
    return struct.pack("!I", len(meta)) + meta + payload


def _desempacotar_datagrama(bruto: bytes) -> tuple[dict, bytes]:
    if len(bruto) < 4:
        raise ValueError("Datagrama UDP inválido.")
    (tam_meta,) = struct.unpack("!I", bruto[:4])
    meta = json.loads(bruto[4:4 + tam_meta].decode("utf-8"))
    payload = bruto[4 + tam_meta:]
    return meta, payload


def obter_ip_local() -> str:
    """Retorna o IP local ativo da máquina na rede/cabo."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def enviar_ping_real(host: str, porta: int = PORTA_PADRAO, timeout: float = TIMEOUT_UDP) -> tuple[bool, float, str]:
    """Envia um PING via UDP e mede o tempo de resposta em ms."""
    datagrama = _empacotar_datagrama({"tipo": "PING"})
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            inicio = time.perf_counter()
            sock.sendto(datagrama, (host, porta))
            bruto, _ = sock.recvfrom(BUFFER_UDP)
            ms = (time.perf_counter() - inicio) * 1000
            resposta, _ = _desempacotar_datagrama(bruto)
            if resposta.get("status") == "PONG":
                return True, ms, "OK"
            return False, ms, "Resposta inesperada."
    except OSError as erro:
        return False, 0.0, str(erro)


def enviar_pacote_real(
    host: str,
    porta: int,
    pacote,
    nome_origem: str,
    nome_destino: str,
    timeout: float = TIMEOUT_UDP,
) -> tuple[bool, str]:
    """Envia um pacote individual via datagrama UDP (com confirmação ACK)."""
    payload = pacote.payload if pacote.payload is not None else b""
    cabecalho = {
        "tipo": "PACOTE",
        "origem": nome_origem,
        "destino": nome_destino,
        "arquivo": pacote.arquivo,
        "tamanho": pacote.tamanho,
        "transmissao_id": pacote.transmissao_id or pacote.id,
        "seq": pacote.seq,
        "total_partes": pacote.total_partes,
        "eh_mensagem": getattr(pacote, "eh_mensagem", False),
        "simulado": pacote.payload is None,
    }
    datagrama = _empacotar_datagrama(cabecalho, payload)

    ultimo_erro = ""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        for _ in range(TENTATIVAS_UDP):
            try:
                sock.sendto(datagrama, (host, porta))
                bruto, _ = sock.recvfrom(BUFFER_UDP)
                resposta, _ = _desempacotar_datagrama(bruto)
                if resposta.get("status") == "OK":
                    return True, resposta.get("detalhe", "ACK UDP recebido.")
                return False, resposta.get("detalhe", "Erro no receptor UDP.")
            except OSError as erro:
                ultimo_erro = str(erro)

    return False, f"Sem resposta UDP de {host}:{porta} ({ultimo_erro})."


class ReceptorSimuladorUDP:
    """Receptor UDP em segundo plano dentro do simulador para receber dados de PCs reais."""

    def __init__(self, simulador, host: str = "0.0.0.0", porta: int = PORTA_SIMULADOR):
        self.simulador = simulador
        self.host = host
        self.porta = porta
        self.ativo = False
        self.total_recebidos = 0
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def iniciar(self) -> bool:
        """Inicia a escuta UDP em thread daemon; retorna False se a porta estiver ocupada."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.porta))
            sock.settimeout(0.5)
        except OSError:
            return False

        self._sock = sock
        self.ativo = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def parar(self) -> None:
        self.ativo = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _loop(self) -> None:
        buffers = HashTable(capacity=53)
        while self.ativo and self._sock is not None:
            try:
                bruto, addr = self._sock.recvfrom(BUFFER_UDP)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                meta, payload = _desempacotar_datagrama(bruto)
                tipo = meta.get("tipo")

                if tipo == "PING":
                    self._sock.sendto(_empacotar_datagrama({"status": "PONG"}), addr)
                    continue

                if tipo != "PACOTE":
                    continue

                origem = meta.get("origem", addr[0])
                destino_id = meta.get("destino", "R_Core")
                nome_arq = _nome_seguro(meta.get("arquivo", "recebido.bin"))
                tx_id = meta.get("transmissao_id", 0)
                seq = meta.get("seq", 1)
                total_partes = meta.get("total_partes", 1)
                eh_msg = meta.get("eh_mensagem", False)
                tam = meta.get("tamanho", len(payload))

                chave_tx = f"{addr[0]}:{tx_id}"
                recebidos = buffers.get(chave_tx)
                if recebidos is None:
                    recebidos = []
                    buffers.insert(chave_tx, recebidos)

                if not any(item[0] == seq for item in recebidos):
                    recebidos.append((seq, payload, tam))

                if len(recebidos) < total_partes:
                    detalhe = f"Pacote {seq}/{total_partes} recebido ({len(recebidos)}/{total_partes})"
                    self._sock.sendto(_empacotar_datagrama({"status": "OK", "detalhe": detalhe}), addr)
                    continue

                buffers.remove(chave_tx)
                quicksort_hibrido(recebidos, chave=lambda item: item[0])
                dados = b"".join(item[1] for item in recebidos)

                with self._lock:
                    disp_destino = self.simulador.tabela_dispositivos.get(destino_id)
                    if disp_destino is None:
                        disp_destino = self.simulador.core

                    caminho = None
                    if eh_msg:
                        texto = dados.decode("utf-8", errors="replace")
                        caminho = salvar_mensagem_pc_simulado(disp_destino.nome, origem, nome_arq, texto)
                    elif dados:
                        caminho = salvar_arquivo_pc_simulado(disp_destino.nome, nome_arq, dados)

                    pacote_final = Packet(
                        origem_ip=addr[0],
                        destino_ip=disp_destino.ip,
                        arquivo=nome_arq,
                        tamanho=max(1, len(dados) if dados else sum(i[2] for i in recebidos)),
                        payload=dados if dados else None,
                        eh_mensagem=eh_msg,
                        caminho_salvo=caminho,
                    )
                    disp_destino.caixa_entrada.append(pacote_final)
                    self.total_recebidos += 1

                detalhe = f"Entregue em {disp_destino.nome}" + (f" ({caminho})" if caminho else "")
                self._sock.sendto(_empacotar_datagrama({"status": "OK", "detalhe": detalhe}), addr)
            except Exception as erro:
                try:
                    self._sock.sendto(_empacotar_datagrama({"status": "ERRO", "detalhe": str(erro)}), addr)
                except OSError:
                    pass


def iniciar_servidor_pc_real(
    host: str = "0.0.0.0",
    porta: int = PORTA_PADRAO,
    pasta_destino: str = PASTA_RECEBIDOS_REAL,
    silencioso_banner: bool = False,
) -> None:
    """Escuta datagramas UDP para receber arquivos e mensagens neste PC real."""
    os.makedirs(pasta_destino, exist_ok=True)
    ip_local = obter_ip_local()
    buffers = HashTable(capacity=53)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as servidor:
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind((host, porta))

        if not silencioso_banner:
            print("=" * 66)
            print(f"  RECEPTOR UDP ATIVO | IP: {ip_local} | Porta: {porta}")
            print(f"  Salvando arquivos recebidos em: {pasta_destino}")
            print("  Pressione Ctrl+C para encerrar.")
            print("=" * 66)

        while True:
            try:
                bruto, addr = servidor.recvfrom(BUFFER_UDP)
                meta, payload = _desempacotar_datagrama(bruto)
                tipo = meta.get("tipo")

                if tipo == "PING":
                    servidor.sendto(_empacotar_datagrama({"status": "PONG"}), addr)
                    print(f"\n[UDP PING] Recebido de {addr[0]}:{addr[1]}")
                    continue

                if tipo == "PACOTE":
                    origem = meta.get("origem", addr[0])
                    destino = meta.get("destino", "PC_Real")
                    nome_arq = _nome_seguro(meta.get("arquivo", "recebido.bin"))
                    tx_id = meta.get("transmissao_id", 0)
                    seq = meta.get("seq", 1)
                    total_partes = meta.get("total_partes", 1)
                    eh_msg = meta.get("eh_mensagem", False)
                    simulado = meta.get("simulado", False)
                    tam = meta.get("tamanho", len(payload))

                    print(f"\n[UDP] Pacote {seq}/{total_partes} | '{nome_arq}' ({tam} B) de {origem}")

                    chave_tx = f"{addr[0]}:{tx_id}"
                    recebidos = buffers.get(chave_tx)
                    if recebidos is None:
                        recebidos = []
                        buffers.insert(chave_tx, recebidos)

                    if not any(item[0] == seq for item in recebidos):
                        recebidos.append((seq, payload, tam))

                    if len(recebidos) < total_partes:
                        detalhe = f"Pacote {seq}/{total_partes} recebido ({len(recebidos)}/{total_partes})"
                        servidor.sendto(_empacotar_datagrama({"status": "OK", "detalhe": detalhe}), addr)
                        continue

                    buffers.remove(chave_tx)
                    quicksort_hibrido(recebidos, chave=lambda item: item[0])

                    if simulado:
                        tam_total = sum(item[2] for item in recebidos)
                        detalhe = f"Arquivo simulado '{nome_arq}' ({tam_total} B) recebido completo."
                        print(f"[COMPLETO] {detalhe}")
                        servidor.sendto(_empacotar_datagrama({"status": "OK", "detalhe": detalhe}), addr)
                    elif eh_msg:
                        dados = b"".join(item[1] for item in recebidos)
                        texto = dados.decode("utf-8", errors="replace")
                        if not nome_arq.lower().endswith(".txt"):
                            nome_arq += ".txt"
                        caminho = os.path.join(pasta_destino, nome_arq)
                        with open(caminho, "w", encoding="utf-8") as arq:
                            arq.write(f"De: {origem}\nPara: {destino}\n\n{texto}\n")
                        print(f"[MENSAGEM] De {origem}: {texto}")
                        print(f"  Salva em: {caminho}")
                        servidor.sendto(_empacotar_datagrama({"status": "OK", "detalhe": f"Salvo em {caminho}"}), addr)
                    else:
                        dados = b"".join(item[1] for item in recebidos)
                        caminho = os.path.join(pasta_destino, nome_arq)
                        with open(caminho, "wb") as arq:
                            arq.write(dados)
                        print(f"[COMPLETO] '{nome_arq}' ({len(dados)} B) salvo em {caminho}")
                        servidor.sendto(_empacotar_datagrama({"status": "OK", "detalhe": f"Salvo em {caminho}"}), addr)

            except Exception as erro:
                try:
                    servidor.sendto(_empacotar_datagrama({"status": "ERRO", "detalhe": str(erro)}), addr)
                except OSError:
                    pass


def _enviar_para_simulador(
    host_sim: str,
    porta_sim: int,
    nome_local: str,
    destino_sim: str,
    pacote_inicial: Packet,
) -> None:
    """Divide o pacote em <= 1500 B, embaralha e envia via UDP para o simulador."""
    partes = pacote_inicial.dividir()
    del pacote_inicial
    if len(partes) > 1:
        random.shuffle(partes)

    for idx, parte in enumerate(partes, start=1):
        ok, detalhe = enviar_pacote_real(host_sim, porta_sim, parte, nome_local, destino_sim)
        if not ok:
            print(f"[ERRO] Falha no pacote {parte.seq}/{parte.total_partes}: {detalhe}")
            return
        if len(partes) <= 20 or idx <= 10 or idx == len(partes):
            print(f"  Pacote {parte.seq}/{parte.total_partes} enviado ({formatar_tamanho(parte.tamanho)}) -> {detalhe}")
        elif idx == 11:
            print(f"  ... (+{len(partes) - 11} pacotes enviados)")


def executar_cliente_pc_real(porta_local: int = PORTA_PADRAO) -> None:
    """Modo bidirecional do PC real: escuta UDP em segundo plano e permite enviar ao simulador."""
    ip_local = obter_ip_local()
    thread_rec = threading.Thread(
        target=iniciar_servidor_pc_real,
        kwargs={"porta": porta_local, "silencioso_banner": True},
        daemon=True,
    )
    thread_rec.start()

    print("=" * 66)
    print(f"  PC REAL (UDP BIDIRECIONAL) | IP: {ip_local} | Porta local: {porta_local}")
    print(f"  Recebidos salvos em: {PASTA_RECEBIDOS_REAL}")
    print("=" * 66)

    nome_local = input("Nome deste PC (ENTER para PC_Real): ").strip() or "PC_Real"
    host_sim = ""
    porta_sim = PORTA_SIMULADOR

    while True:
        print("\n--- MENU PC REAL ---")
        print(" [1] Enviar arquivo real (pasta transfer/) para o simulador")
        print(" [2] Enviar mensagem de texto para o simulador")
        print(" [3] Ping no simulador")
        print(" [0] Sair")
        opcao = input("pc-real:~$ ").strip()

        if opcao == "0":
            print("Encerrando PC real.")
            break

        if opcao not in ("1", "2", "3"):
            print("[ERRO] Opção inválida.")
            continue

        if not host_sim:
            host_sim = input("IP do PC com o simulador (ex: 192.168.50.1 ou 127.0.0.1): ").strip()
            porta_txt = input(f"Porta UDP do simulador (ENTER para {PORTA_SIMULADOR}): ").strip()
            if porta_txt.isdigit():
                porta_sim = int(porta_txt)

        if opcao == "3":
            ok, ms, detalhe = enviar_ping_real(host_sim, porta_sim)
            if ok:
                print(f"[PING OK] Simulador ({host_sim}:{porta_sim}) respondeu PONG em {ms:.1f} ms")
            else:
                print(f"[ERRO] Sem resposta de {host_sim}:{porta_sim} ({detalhe})")

        elif opcao == "1":
            disponiveis = listar_arquivos_transfer()
            if not disponiveis:
                print("[AVISO] Nenhum arquivo na pasta transfer/.")
                continue
            print("Arquivos em transfer/:")
            for idx, arq in enumerate(disponiveis, start=1):
                print(f"  [{idx}] {arq}")
            escolha = input("Número ou nome do arquivo: ").strip()
            if not escolha:
                continue
            nome_arq = disponiveis[int(escolha) - 1] if escolha.isdigit() and 1 <= int(escolha) <= len(disponiveis) else escolha
            destino = input("Dispositivo destino no simulador (ex: PC1 ou R_Core): ").strip() or "R_Core"
            try:
                dados = ler_arquivo_transfer(nome_arq)
                pacote = Packet(ip_local, host_sim, nome_arq, len(dados), payload=dados)
                _enviar_para_simulador(host_sim, porta_sim, nome_local, destino, pacote)
            except (FileNotFoundError, OSError, ValueError) as erro:
                print(f"[ERRO] {erro}")

        elif opcao == "2":
            destino = input("Dispositivo destino no simulador (ex: PC1 ou R_Core): ").strip() or "R_Core"
            texto = input("Digite a mensagem: ").strip()
            if not texto:
                print("[ERRO] Mensagem vazia.")
                continue
            dados = texto.encode("utf-8")
            nome_msg = f"msg_{nome_local}_para_{destino}_{int(time.time())}.txt"
            pacote = Packet(ip_local, host_sim, nome_msg, len(dados), payload=dados, eh_mensagem=True)
            _enviar_para_simulador(host_sim, porta_sim, nome_local, destino, pacote)


if __name__ == "__main__":
    import sys

    if os.name == "nt" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    porta_arg = PORTA_PADRAO
    if len(sys.argv) > 1:
        try:
            porta_arg = int(sys.argv[1])
        except ValueError:
            print(f"Porta inválida '{sys.argv[1]}', usando {PORTA_PADRAO}.")

    try:
        executar_cliente_pc_real(porta_local=porta_arg)
    except (KeyboardInterrupt, EOFError):
        print("\nPC real encerrado.")
