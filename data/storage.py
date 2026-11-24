"""Persistência em JSON do estado da rede (dispositivos e pacotes)."""

import json
import os

from core.models import Device, Packet
from structures.tree import NetworkNode

CAMINHO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado_rede.json")


def _serializar_pacote(pacote: Packet) -> dict:
    return {
        "id": pacote.id,
        "origem_ip": pacote.origem_ip,
        "destino_ip": pacote.destino_ip,
        "arquivo": pacote.arquivo,
        "tamanho": pacote.tamanho,
        "ttl": pacote.ttl,
        "transmissao_id": pacote.transmissao_id,
        "seq": pacote.seq,
        "total_partes": pacote.total_partes,
    }


def _desserializar_pacote(dados: dict) -> Packet:
    pacote = Packet(
        origem_ip=dados["origem_ip"],
        destino_ip=dados["destino_ip"],
        arquivo=dados["arquivo"],
        tamanho=dados["tamanho"],
        transmissao_id=dados.get("transmissao_id"),
        seq=dados.get("seq", 1),
        total_partes=dados.get("total_partes", 1),
    )
    pacote.id = dados.get("id", pacote.id)
    pacote.ttl = dados.get("ttl", 16)
    return pacote


def _coletar_dispositivos(no: NetworkNode, nome_pai: str | None, lista: list[dict]) -> None:
    disp = no.dispositivo
    lista.append({
        "nome": disp.nome,
        "ip": disp.ip,
        "tipo": disp.tipo,
        "mac": disp.mac,
        "pai": nome_pai,
        "caixa_entrada": [_serializar_pacote(p) for p in disp.caixa_entrada],
    })
    for filho in no.filhos:
        _coletar_dispositivos(filho, disp.nome, lista)


def salvar_estado(simulador, caminho: str = CAMINHO_PADRAO) -> str:
    """Salva dispositivos, pacotes recebidos/entregues, fila e pacotes em trânsito em JSON."""
    dispositivos: list[dict] = []
    _coletar_dispositivos(simulador.arvore.raiz, None, dispositivos)

    pacotes_entregues = []
    for disp in dispositivos:
        for pacote in disp["caixa_entrada"]:
            pacotes_entregues.append({
                "destinatario": disp["nome"],
                **pacote,
            })

    fila = [_serializar_pacote(p) for p in simulador.roteador.fila_transmissao.to_list()]

    em_transito = {}
    for chave_tx, buffer in simulador.roteador.buffers_recepcao.to_list():
        em_transito[chave_tx] = [_serializar_pacote(p) for p in buffer]

    dados = {
        "proximo_packet_id": Packet._contador_id,
        "dhcp_ips_liberados": list(simulador.dhcp._ips_liberados),
        "dispositivos": dispositivos,
        "pacotes_entregues": pacotes_entregues,
        "fila_transmissao": fila,
        "em_transito": em_transito,
    }

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=2, ensure_ascii=False)

    return caminho


def carregar_estado(simulador, caminho: str = CAMINHO_PADRAO) -> bool:
    """Carrega o estado salvo do JSON para o simulador. Retorna True se carregado."""
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

    # Restaura o nó raiz (R_Core)
    raiz_dados = dispositivos_salvos[0]
    simulador.core.mac = raiz_dados.get("mac", simulador.core.mac)
    simulador.core.caixa_entrada = [
        _desserializar_pacote(p) for p in raiz_dados.get("caixa_entrada", [])
    ]

    nos_por_nome = {simulador.core.nome: simulador.no_raiz}

    # Reconstrói roteadores de setor e PCs mantendo a hierarquia
    for item in dispositivos_salvos[1:]:
        disp = Device(
            nome=item["nome"],
            ip=item["ip"],
            tipo=item["tipo"],
            mac=item.get("mac"),
        )
        disp.caixa_entrada = [
            _desserializar_pacote(p) for p in item.get("caixa_entrada", [])
        ]
        no = NetworkNode(disp)
        no_pai = nos_por_nome.get(item.get("pai"), simulador.no_raiz)
        no_pai.adicionar_filho(no)
        nos_por_nome[disp.nome] = no
        simulador._indexar_dispositivo(disp)

    # Restaura fila de transmissão
    for p_dados in dados.get("fila_transmissao", []):
        simulador.roteador.fila_transmissao.enqueue(_desserializar_pacote(p_dados))

    # Restaura pacotes em trânsito (buffer de recepção)
    for chave_tx, lista_pacotes in dados.get("em_transito", {}).items():
        buffer = [_desserializar_pacote(p) for p in lista_pacotes]
        if buffer:
            simulador.roteador.buffers_recepcao.insert(chave_tx, buffer)

    # Restaura pool DHCP e contador de IDs
    simulador.dhcp._ips_liberados = list(dados.get("dhcp_ips_liberados", []))
    Packet._contador_id = max(Packet._contador_id, dados.get("proximo_packet_id", 0))
    return True
