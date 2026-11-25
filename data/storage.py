"""Persistência em JSON do estado da rede, mensagens, arquivos e sockets UDP."""

import base64
from datetime import datetime
import json
import os
import sys

import core.sockets as _sockets
from core.models import Device, Packet
from structures.tree import NetworkNode

PASTA_DATA = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PADRAO = os.path.join(PASTA_DATA, "estado_rede.json")
CAMINHO_SOCKETS = os.path.join(PASTA_DATA, "estado_sockets.json")

_ESTADO_SOCKETS_MEMORIA: dict = {
    "total_recebidos_udp": 0,
    "envios_udp": [],
    "recebimentos_udp": [],
}
_HISTORICO_MEMORIA: dict = {
    "mensagens": [],
    "arquivos_enviados": [],
    "arquivos_recebidos": [],
}
_SIMULADOR_ATIVO = None
_CAMINHO_ATIVO: str = CAMINHO_PADRAO
_HOOKS_ATIVOS = False


def _agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _chave_unica(item: dict) -> tuple:
    return (
        item.get("transmissao_id") or item.get("id"),
        item.get("arquivo"),
        item.get("origem_ip") or item.get("origem"),
        item.get("destino_ip") or item.get("destino") or item.get("destinatario"),
    )


def _mesclar_sem_duplicar(atuais: list[dict], historico: list[dict]) -> list[dict]:
    resultado = list(atuais)
    vistos = {_chave_unica(item) for item in resultado}
    for antigo in historico:
        chave = _chave_unica(antigo)
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(antigo)
    return resultado


def _serializar_pacote(pacote: Packet, incluir_payload_binario: bool = False) -> dict:
    dados = {
        "id": pacote.id,
        "origem_ip": pacote.origem_ip,
        "destino_ip": pacote.destino_ip,
        "arquivo": pacote.arquivo,
        "tamanho": pacote.tamanho,
        "ttl": pacote.ttl,
        "transmissao_id": pacote.transmissao_id,
        "seq": pacote.seq,
        "total_partes": pacote.total_partes,
        "eh_mensagem": pacote.eh_mensagem,
        "caminho_salvo": pacote.caminho_salvo,
    }
    if pacote.payload is not None:
        if pacote.eh_mensagem:
            dados["mensagem"] = pacote.payload.decode("utf-8", errors="replace")
        elif incluir_payload_binario:
            dados["payload_b64"] = base64.b64encode(pacote.payload).decode("ascii")
    return dados


def _desserializar_pacote(dados: dict) -> Packet:
    payload = None
    if "mensagem" in dados:
        payload = dados["mensagem"].encode("utf-8")
    elif "payload_b64" in dados:
        payload = base64.b64decode(dados["payload_b64"].encode("ascii"))

    pacote = Packet(
        origem_ip=dados["origem_ip"],
        destino_ip=dados["destino_ip"],
        arquivo=dados["arquivo"],
        tamanho=dados["tamanho"],
        transmissao_id=dados.get("transmissao_id"),
        seq=dados.get("seq", 1),
        total_partes=dados.get("total_partes", 1),
        payload=payload,
        eh_mensagem=dados.get("eh_mensagem", False),
        caminho_salvo=dados.get("caminho_salvo"),
    )
    pacote.id = dados.get("id", pacote.id)
    pacote.ttl = dados.get("ttl", 16)
    return pacote


def _resolver_nome_dispositivo(simulador, ip_ou_nome: str) -> str:
    disp = simulador.tabela_dispositivos.get(ip_ou_nome)
    return disp.nome if disp is not None else ip_ou_nome


def _coletar_dispositivos(no: NetworkNode, nome_pai: str | None, lista: list[dict]) -> None:
    disp = no.dispositivo
    lista.append({
        "nome": disp.nome,
        "ip": disp.ip,
        "tipo": disp.tipo,
        "mac": disp.mac,
        "modo": disp.modo,
        "host_real": disp.host_real,
        "porta_real": disp.porta_real,
        "pai": nome_pai,
        "caixa_entrada": [_serializar_pacote(p) for p in disp.caixa_entrada],
    })
    for filho in no.filhos:
        _coletar_dispositivos(filho, disp.nome, lista)


def _listar_recebidos_pc_real() -> list[dict]:
    """Inspeciona os arquivos e mensagens salvos em data/recebidos/ pelo socket do PC real."""
    pasta = _sockets.PASTA_RECEBIDOS_REAL
    if not os.path.isdir(pasta):
        return []

    itens = []
    for nome in sorted(os.listdir(pasta)):
        caminho = os.path.join(pasta, nome)
        if not os.path.isfile(caminho) or nome == ".gitkeep":
            continue
        eh_msg = nome.lower().endswith(".txt") and nome.startswith("msg_")
        item = {
            "arquivo": nome,
            "tamanho": os.path.getsize(caminho),
            "eh_mensagem": eh_msg,
            "caminho_salvo": caminho,
        }
        if eh_msg:
            try:
                with open(caminho, "r", encoding="utf-8", errors="replace") as arq:
                    item["conteudo"] = arq.read().strip()
            except OSError:
                pass
        itens.append(item)
    return itens


def _resumir_transferencias(simulador, dispositivos: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Separa mensagens, arquivos enviados e arquivos recebidos (entregues, em trânsito e na fila)."""
    mensagens: list[dict] = []
    arquivos_enviados: list[dict] = []
    arquivos_recebidos: list[dict] = []

    # 1. Itens já entregues nas caixas de entrada dos dispositivos
    for disp in dispositivos:
        for p in disp["caixa_entrada"]:
            origem_nome = _resolver_nome_dispositivo(simulador, p["origem_ip"])
            destino_nome = disp["nome"]
            base = {
                "id": p["id"],
                "transmissao_id": p.get("transmissao_id") or p["id"],
                "arquivo": p["arquivo"],
                "tamanho": p["tamanho"],
                "origem": origem_nome,
                "origem_ip": p["origem_ip"],
                "destino": destino_nome,
                "destino_ip": p["destino_ip"],
                "modo_destino": disp["modo"],
                "caminho_salvo": p.get("caminho_salvo"),
                "status": "ENTREGUE",
            }
            if p.get("eh_mensagem"):
                mensagens.append({
                    **base,
                    "mensagem": p.get("mensagem", ""),
                })
            else:
                tipo_arquivo = "REAL" if p.get("caminho_salvo") or disp["modo"] == "REAL" else "SIMULADO"
                arquivos_enviados.append({**base, "tipo_arquivo": tipo_arquivo})
                arquivos_recebidos.append({
                    "id": p["id"],
                    "transmissao_id": p.get("transmissao_id") or p["id"],
                    "arquivo": p["arquivo"],
                    "tamanho": p["tamanho"],
                    "remetente": origem_nome,
                    "origem_ip": p["origem_ip"],
                    "destinatario": destino_nome,
                    "destino_ip": p["destino_ip"],
                    "modo_destino": disp["modo"],
                    "tipo_arquivo": tipo_arquivo,
                    "caminho_salvo": p.get("caminho_salvo"),
                })

    # 2. Agrupa pacotes pendentes (fila + em trânsito) por transmissão
    pendentes_por_tx: dict[tuple, dict] = {}

    for _chave_tx, buffer in simulador.roteador.buffers_recepcao.to_list():
        for p in buffer:
            chave = (p.destino_ip, p.transmissao_id or p.id, p.arquivo)
            grupo = pendentes_por_tx.setdefault(chave, {
                "pacote_ref": p,
                "tamanho_acumulado": 0,
                "recebidos": 0,
                "na_fila": 0,
            })
            grupo["tamanho_acumulado"] += p.tamanho
            grupo["recebidos"] += 1

    for p in simulador.roteador.fila_transmissao.to_list():
        chave = (p.destino_ip, p.transmissao_id or p.id, p.arquivo)
        grupo = pendentes_por_tx.setdefault(chave, {
            "pacote_ref": p,
            "tamanho_acumulado": 0,
            "recebidos": 0,
            "na_fila": 0,
        })
        grupo["tamanho_acumulado"] += p.tamanho
        grupo["na_fila"] += 1

    for grupo in pendentes_por_tx.values():
        p = grupo["pacote_ref"]
        status = "EM_TRANSITO" if grupo["recebidos"] > 0 else "NA_FILA"
        origem_nome = _resolver_nome_dispositivo(simulador, p.origem_ip)
        destino_nome = _resolver_nome_dispositivo(simulador, p.destino_ip)
        item_pendente = {
            "id": p.id,
            "transmissao_id": p.transmissao_id or p.id,
            "arquivo": p.arquivo,
            "tamanho": grupo["tamanho_acumulado"],
            "origem": origem_nome,
            "origem_ip": p.origem_ip,
            "destino": destino_nome,
            "destino_ip": p.destino_ip,
            "partes_recebidas": grupo["recebidos"],
            "total_partes": p.total_partes,
            "status": status,
        }
        if p.eh_mensagem:
            texto_parcial = p.payload.decode("utf-8", errors="replace") if p.payload and p.total_partes == 1 else ""
            mensagens.append({**item_pendente, "mensagem": texto_parcial})
        else:
            tipo_arquivo = "REAL" if p.payload is not None else "SIMULADO"
            arquivos_enviados.append({**item_pendente, "tipo_arquivo": tipo_arquivo})

    mensagens = _mesclar_sem_duplicar(mensagens, _HISTORICO_MEMORIA["mensagens"])
    arquivos_enviados = _mesclar_sem_duplicar(arquivos_enviados, _HISTORICO_MEMORIA["arquivos_enviados"])
    arquivos_recebidos = _mesclar_sem_duplicar(arquivos_recebidos, _HISTORICO_MEMORIA["arquivos_recebidos"])
    return mensagens, arquivos_enviados, arquivos_recebidos


def salvar_estado_sockets(caminho: str = CAMINHO_SOCKETS) -> str:
    """Salva em JSON o histórico e contadores da camada de sockets UDP."""
    dados_sockets = {
        "atualizado_em": _agora_iso(),
        "porta_simulador": _sockets.PORTA_SIMULADOR,
        "porta_pc_real": _sockets.PORTA_PADRAO,
        "total_recebidos_udp": _ESTADO_SOCKETS_MEMORIA["total_recebidos_udp"],
        "envios_udp": list(_ESTADO_SOCKETS_MEMORIA["envios_udp"]),
        "recebimentos_udp": list(_ESTADO_SOCKETS_MEMORIA["recebimentos_udp"]),
        "arquivos_recebidos_pc_real": _listar_recebidos_pc_real(),
    }
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados_sockets, arquivo, indent=2, ensure_ascii=False)
    return caminho


def carregar_estado_sockets(caminho: str = CAMINHO_SOCKETS) -> dict:
    """Carrega o estado persistido de sockets UDP, caso exista."""
    if not os.path.exists(caminho):
        return dict(_ESTADO_SOCKETS_MEMORIA)
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return dict(_ESTADO_SOCKETS_MEMORIA)

    _ESTADO_SOCKETS_MEMORIA["total_recebidos_udp"] = dados.get("total_recebidos_udp", 0)
    _ESTADO_SOCKETS_MEMORIA["envios_udp"] = list(dados.get("envios_udp", []))
    _ESTADO_SOCKETS_MEMORIA["recebimentos_udp"] = list(dados.get("recebimentos_udp", []))
    return dados


def salvar_estado(simulador, caminho: str = CAMINHO_PADRAO) -> str:
    """Salva dispositivos, mensagens, arquivos enviados/recebidos, fila, trânsito e sockets em JSON."""
    global _SIMULADOR_ATIVO, _CAMINHO_ATIVO
    _SIMULADOR_ATIVO = simulador
    _CAMINHO_ATIVO = caminho

    dispositivos: list[dict] = []
    _coletar_dispositivos(simulador.arvore.raiz, None, dispositivos)

    pacotes_entregues = []
    for disp in dispositivos:
        for pacote in disp["caixa_entrada"]:
            pacotes_entregues.append({
                "destinatario": disp["nome"],
                **pacote,
            })

    mensagens, arquivos_enviados, arquivos_recebidos = _resumir_transferencias(simulador, dispositivos)
    _HISTORICO_MEMORIA["mensagens"] = mensagens
    _HISTORICO_MEMORIA["arquivos_enviados"] = arquivos_enviados
    _HISTORICO_MEMORIA["arquivos_recebidos"] = arquivos_recebidos

    fila = [
        _serializar_pacote(p, incluir_payload_binario=True)
        for p in simulador.roteador.fila_transmissao.to_list()
    ]

    em_transito = {}
    for chave_tx, buffer in simulador.roteador.buffers_recepcao.to_list():
        em_transito[chave_tx] = [_serializar_pacote(p, incluir_payload_binario=True) for p in buffer]

    sockets_info = {
        "porta_simulador": _sockets.PORTA_SIMULADOR,
        "porta_pc_real": _sockets.PORTA_PADRAO,
        "total_recebidos_udp": _ESTADO_SOCKETS_MEMORIA["total_recebidos_udp"],
        "envios_udp": list(_ESTADO_SOCKETS_MEMORIA["envios_udp"]),
        "recebimentos_udp": list(_ESTADO_SOCKETS_MEMORIA["recebimentos_udp"]),
        "arquivos_recebidos_pc_real": _listar_recebidos_pc_real(),
    }

    dados = {
        "atualizado_em": _agora_iso(),
        "proximo_packet_id": Packet._contador_id,
        "dhcp_ips_liberados": list(simulador.dhcp._ips_liberados),
        "dispositivos": dispositivos,
        "mensagens": mensagens,
        "arquivos_enviados": arquivos_enviados,
        "arquivos_recebidos": arquivos_recebidos,
        "pacotes_entregues": pacotes_entregues,
        "fila_transmissao": fila,
        "em_transito": em_transito,
        "sockets": sockets_info,
    }

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=2, ensure_ascii=False)

    if caminho == CAMINHO_PADRAO:
        salvar_estado_sockets()

    return caminho


def carregar_estado(simulador, caminho: str = CAMINHO_PADRAO) -> bool:
    """Carrega o estado salvo do JSON para o simulador e restaura dados de sockets."""
    global _SIMULADOR_ATIVO, _CAMINHO_ATIVO
    _SIMULADOR_ATIVO = simulador
    _CAMINHO_ATIVO = caminho

    if caminho == CAMINHO_PADRAO:
        carregar_estado_sockets()

    if not os.path.exists(caminho):
        return False

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return False

    dispositivos_salvos = dados.get("dispositivos", [])
    if not dispositivos_salvos:
        return False

    raiz_dados = dispositivos_salvos[0]
    simulador.core.mac = raiz_dados.get("mac", simulador.core.mac)
    simulador.core.caixa_entrada = [
        _desserializar_pacote(p) for p in raiz_dados.get("caixa_entrada", [])
    ]

    nos_por_nome = {simulador.core.nome: simulador.no_raiz}

    for item in dispositivos_salvos[1:]:
        disp = Device(
            nome=item["nome"],
            ip=item["ip"],
            tipo=item["tipo"],
            mac=item.get("mac"),
            modo=item.get("modo", "SIMULADO"),
            host_real=item.get("host_real"),
            porta_real=item.get("porta_real"),
        )
        disp.caixa_entrada = [
            _desserializar_pacote(p) for p in item.get("caixa_entrada", [])
        ]
        no = NetworkNode(disp)
        no_pai = nos_por_nome.get(item.get("pai"), simulador.no_raiz)
        no_pai.adicionar_filho(no)
        nos_por_nome[disp.nome] = no
        simulador._indexar_dispositivo(disp)

    for p_dados in dados.get("fila_transmissao", []):
        simulador.roteador.fila_transmissao.enqueue(_desserializar_pacote(p_dados))

    for chave_tx, lista_pacotes in dados.get("em_transito", {}).items():
        buffer = [_desserializar_pacote(p) for p in lista_pacotes]
        if buffer:
            simulador.roteador.buffers_recepcao.insert(chave_tx, buffer)

    _HISTORICO_MEMORIA["mensagens"] = list(dados.get("mensagens", []))
    _HISTORICO_MEMORIA["arquivos_enviados"] = list(dados.get("arquivos_enviados", []))
    _HISTORICO_MEMORIA["arquivos_recebidos"] = list(dados.get("arquivos_recebidos", []))

    sockets_salvos = dados.get("sockets", {})
    if sockets_salvos:
        _ESTADO_SOCKETS_MEMORIA["total_recebidos_udp"] = max(
            _ESTADO_SOCKETS_MEMORIA["total_recebidos_udp"],
            sockets_salvos.get("total_recebidos_udp", 0),
        )
        if sockets_salvos.get("envios_udp"):
            _ESTADO_SOCKETS_MEMORIA["envios_udp"] = list(sockets_salvos["envios_udp"])
        if sockets_salvos.get("recebimentos_udp"):
            _ESTADO_SOCKETS_MEMORIA["recebimentos_udp"] = list(sockets_salvos["recebimentos_udp"])

    simulador.dhcp._ips_liberados = list(dados.get("dhcp_ips_liberados", []))
    Packet._contador_id = max(Packet._contador_id, dados.get("proximo_packet_id", 0))
    return True


def _instalar_persistencia_sockets() -> None:
    """Conecta persistência automática aos envios e recebimentos UDP de core.sockets."""
    global _HOOKS_ATIVOS
    if _HOOKS_ATIVOS:
        return
    _HOOKS_ATIVOS = True

    enviar_original = _sockets.enviar_pacote_real
    partes_enviadas_por_tx: dict[tuple, set[int]] = {}

    def _enviar_com_persistencia(
        host: str,
        porta: int,
        pacote,
        nome_origem: str,
        nome_destino: str,
        timeout: float = _sockets.TIMEOUT_UDP,
    ) -> tuple[bool, str]:
        ok, detalhe = enviar_original(host, porta, pacote, nome_origem, nome_destino, timeout=timeout)
        if ok:
            tx_id = getattr(pacote, "transmissao_id", None) or pacote.id
            seq = getattr(pacote, "seq", 1)
            total = getattr(pacote, "total_partes", 1)
            chave_tx = (host, porta, tx_id, pacote.arquivo)
            seqs = partes_enviadas_por_tx.setdefault(chave_tx, set())
            seqs.add(seq)
            if len(seqs) >= total:
                partes_enviadas_por_tx.pop(chave_tx, None)
                _ESTADO_SOCKETS_MEMORIA["envios_udp"].append({
                    "horario": _agora_iso(),
                    "origem": nome_origem,
                    "destino": nome_destino,
                    "host_destino": host,
                    "porta_destino": porta,
                    "arquivo": pacote.arquivo,
                    "eh_mensagem": getattr(pacote, "eh_mensagem", False),
                    "total_partes": total,
                })
                salvar_estado_sockets()
        return ok, detalhe

    _sockets.enviar_pacote_real = _enviar_com_persistencia
    modulo_tree = sys.modules.get("structures.tree")
    if modulo_tree is not None and hasattr(modulo_tree, "enviar_pacote_real"):
        modulo_tree.enviar_pacote_real = _enviar_com_persistencia

    init_original = _sockets.ReceptorSimuladorUDP.__init__

    def _init_receptor(self, simulador, host: str = "0.0.0.0", porta: int = _sockets.PORTA_SIMULADOR):
        self._inicializando_persistencia = True
        self._total_recebidos_interno = 0
        init_original(self, simulador, host=host, porta=porta)
        if simulador is _SIMULADOR_ATIVO:
            self._total_recebidos_interno = _ESTADO_SOCKETS_MEMORIA["total_recebidos_udp"]
        self._inicializando_persistencia = False

    def _get_total_recebidos(self) -> int:
        return getattr(self, "_total_recebidos_interno", 0)

    def _set_total_recebidos(self, valor: int) -> None:
        anterior = getattr(self, "_total_recebidos_interno", 0)
        self._total_recebidos_interno = valor
        if getattr(self, "_inicializando_persistencia", False):
            return
        if valor > anterior:
            _ESTADO_SOCKETS_MEMORIA["total_recebidos_udp"] = valor
            ultimo_pacote = None
            for disp in self.simulador.listar_dispositivos():
                if disp.caixa_entrada:
                    cand = disp.caixa_entrada[-1]
                    if ultimo_pacote is None or cand.id > ultimo_pacote[1].id:
                        ultimo_pacote = (disp.nome, cand)
            if ultimo_pacote is not None:
                nome_dest, pkt = ultimo_pacote
                _ESTADO_SOCKETS_MEMORIA["recebimentos_udp"].append({
                    "horario": _agora_iso(),
                    "origem_ip": pkt.origem_ip,
                    "destinatario": nome_dest,
                    "arquivo": pkt.arquivo,
                    "tamanho": pkt.tamanho,
                    "eh_mensagem": pkt.eh_mensagem,
                    "caminho_salvo": pkt.caminho_salvo,
                })
            if self.simulador is _SIMULADOR_ATIVO:
                salvar_estado(self.simulador, _CAMINHO_ATIVO)

    _sockets.ReceptorSimuladorUDP.__init__ = _init_receptor
    _sockets.ReceptorSimuladorUDP.total_recebidos = property(_get_total_recebidos, _set_total_recebidos)


_instalar_persistencia_sockets()
