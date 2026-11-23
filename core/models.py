"""Entidades de domínio do simulador: dispositivos de rede e pacotes de dados."""

import random


class Device:
    """
    Representa um dispositivo conectado à rede (Roteador de setor/core ou PC).

    É o objeto guardado em cada `NetworkNode` da árvore (structures/tree.py) e
    indexado na Tabela Hash global por IP e por Nome (busca O(1) médio).
    """

    TIPOS_VALIDOS = ("ROUTER", "PC")

    def __init__(self, nome: str, ip: str, tipo: str = "PC", mac: str | None = None):
        if tipo not in Device.TIPOS_VALIDOS:
            raise ValueError(f"Tipo de dispositivo inválido: '{tipo}'. Use 'ROUTER' ou 'PC'.")

        self.nome = nome
        self.ip = ip
        self.tipo = tipo
        self.mac = mac or Device._gerar_mac_aleatorio()
        self.caixa_entrada: list = []  # Pacotes recebidos (inbox), preenchida pelo Router

    @staticmethod
    def _gerar_mac_aleatorio() -> str:
        return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))

    def __repr__(self) -> str:
        return f"<Device {self.nome} | {self.ip} | {self.tipo}>"


class Packet:
    """
    Representa um pacote de dados transmitido entre dois dispositivos.

    Consumido pela Fila FIFO de transmissão (structures/queue.py via Router) e
    ordenado em lote pelo QuickSort Híbrido (structures/sorting.py) segundo o
    atributo `tamanho`, implementando a política Shortest Job First (SJF).
    """

    _contador_id = 0

    def __init__(self, origem_ip: str, destino_ip: str, arquivo: str, tamanho: int, conteudo: str = ""):
        Packet._contador_id += 1
        self.id = Packet._contador_id
        self.origem_ip = origem_ip
        self.destino_ip = destino_ip
        self.arquivo = arquivo
        self.tamanho = tamanho  # em MB; critério de ordenação do lote (SJF)
        self.conteudo = conteudo
        self.ttl = 16  # Time To Live simbólico

    def __repr__(self) -> str:
        return f"[Pacote#{self.id} {self.arquivo} | {self.tamanho}MB | {self.origem_ip}->{self.destino_ip}]"


if __name__ == "__main__":
    print("=== TESTE UNITÁRIO: core/models.py ===")

    core = Device("R_Core", "10.0.0.1", tipo="ROUTER")
    pc1 = Device("PC1", "10.0.0.4", tipo="PC")
    print("Dispositivo roteador:", core, "| MAC:", core.mac)
    print("Dispositivo PC:", pc1, "| MAC:", pc1.mac)
    assert core.caixa_entrada == []
    assert len(pc1.mac.split(":")) == 6

    try:
        Device("Invalido", "10.0.0.9", tipo="SWITCH")
        raise AssertionError("Deveria ter rejeitado tipo inválido")
    except ValueError as erro:
        print("Validação de tipo OK:", erro)

    p1 = Packet("10.0.0.4", "10.0.0.5", "notas.txt", 2)
    p2 = Packet("10.0.0.4", "10.0.0.5", "video.mp4", 50)
    print("Pacote 1:", p1)
    print("Pacote 2:", p2)
    assert p2.id == p1.id + 1
    assert p1.ttl == 16

    pc1.caixa_entrada.append(p1)
    assert len(pc1.caixa_entrada) == 1
    print("Entrega na caixa de entrada OK:", pc1.caixa_entrada)

    print("Todos os testes de Device/Packet passaram!")