"""Modelos de dispositivos e pacotes da rede."""

import random


class Device:
    """Dispositivo da rede (roteador ou PC)."""

    TIPOS_VALIDOS = ("ROUTER", "PC")

    def __init__(self, nome: str, ip: str, tipo: str = "PC", mac: str | None = None):
        if not nome or not nome.strip():
            raise ValueError("Nome do dispositivo não pode ser vazio.")
        if not ip or not ip.strip():
            raise ValueError("IP do dispositivo não pode ser vazio.")
        if tipo not in Device.TIPOS_VALIDOS:
            raise ValueError(f"Tipo de dispositivo inválido: '{tipo}'. Use 'ROUTER' ou 'PC'.")

        self.nome = nome.strip()
        self.ip = ip.strip()
        self.tipo = tipo
        self.mac = mac or Device._gerar_mac_aleatorio()
        self.caixa_entrada: list = []

    @staticmethod
    def _gerar_mac_aleatorio() -> str:
        return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))

    def __repr__(self) -> str:
        return f"<Device {self.nome} | {self.ip} | {self.tipo}>"


UNIDADES_TAMANHO: dict[str, int] = {
    "B": 1,
    "KB": 1024,
    "MB": 1024 ** 2,
    "GB": 1024 ** 3,
    "TB": 1024 ** 4,
}


def converter_para_bytes(valor: float, unidade: str) -> int:
    """Converte um tamanho na unidade informada para bytes."""
    chave = unidade.strip().upper()
    if chave not in UNIDADES_TAMANHO:
        raise ValueError(f"Unidade inválida: '{unidade}'. Use: {', '.join(UNIDADES_TAMANHO)}.")
    if valor <= 0:
        raise ValueError("Tamanho do arquivo deve ser maior que zero.")
    return max(1, int(round(valor * UNIDADES_TAMANHO[chave])))


def formatar_tamanho(tamanho_bytes: int) -> str:
    """Formata um valor em bytes para a unidade mais adequada."""
    if tamanho_bytes < 1024:
        return f"{tamanho_bytes} B"
    valor = float(tamanho_bytes)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            return f"{valor:.2f} {unidade}"
        valor /= 1024
    return f"{tamanho_bytes} B"


def calcular_qtd_blocos(tamanho_bytes: int) -> int:
    """Calcula a quantidade de blocos de forma proporcional ao tamanho do arquivo."""
    if tamanho_bytes <= 1:
        return 1
    if tamanho_bytes < 1024:
        return min(tamanho_bytes, 4)
    if tamanho_bytes < 1024 ** 2:
        kb = tamanho_bytes / 1024
        return min(10, max(5, 5 + int(kb // 200)))
    if tamanho_bytes < 1024 ** 3:
        mb = tamanho_bytes / (1024 ** 2)
        return min(18, max(10, 10 + int(mb // 100)))
    if tamanho_bytes < 1024 ** 4:
        gb = tamanho_bytes / (1024 ** 3)
        return min(30, max(18, 18 + int(gb // 80)))
    tb = tamanho_bytes / (1024 ** 4)
    return min(50, max(32, 32 + int(tb * 2)))


class Packet:
    """Pacote de dados transmitido entre dois dispositivos."""

    _contador_id = 0

    def __init__(
        self,
        origem_ip: str,
        destino_ip: str,
        arquivo: str,
        tamanho: int,
        transmissao_id: int | None = None,
        seq: int = 1,
        total_partes: int = 1,
    ):
        if not arquivo or not arquivo.strip():
            raise ValueError("Nome do arquivo do pacote não pode ser vazio.")
        if tamanho <= 0:
            raise ValueError("Tamanho do pacote deve ser maior que zero.")
        if seq < 1 or total_partes < 1 or seq > total_partes:
            raise ValueError("Sequência de pacote inválida.")

        Packet._contador_id += 1
        self.id = Packet._contador_id
        self.origem_ip = origem_ip
        self.destino_ip = destino_ip
        self.arquivo = arquivo.strip()
        self.tamanho = tamanho
        self.ttl = 16
        self.transmissao_id = transmissao_id
        self.seq = seq
        self.total_partes = total_partes

    def dividir(self) -> list["Packet"]:
        """Divide este pacote em pacotes menores conforme o tamanho do arquivo."""
        qtd = calcular_qtd_blocos(self.tamanho)
        tx_id = self.id
        base, resto = divmod(self.tamanho, qtd)

        partes: list[Packet] = []
        for i in range(1, qtd + 1):
            tam_parte = base + (1 if i <= resto else 0)
            partes.append(
                Packet(
                    origem_ip=self.origem_ip,
                    destino_ip=self.destino_ip,
                    arquivo=self.arquivo,
                    tamanho=tam_parte,
                    transmissao_id=tx_id,
                    seq=i,
                    total_partes=qtd,
                )
            )
        return partes

    @classmethod
    def unir(cls, partes_ordenadas: list["Packet"]) -> "Packet":
        """Reconstrói o pacote original a partir das partes já ordenadas."""
        if not partes_ordenadas:
            raise ValueError("Lista de pacotes não pode estar vazia.")

        primeiro = partes_ordenadas[0]
        tamanho_total = sum(p.tamanho for p in partes_ordenadas)
        menor_ttl = min(p.ttl for p in partes_ordenadas)

        pacote_final = cls(
            origem_ip=primeiro.origem_ip,
            destino_ip=primeiro.destino_ip,
            arquivo=primeiro.arquivo,
            tamanho=tamanho_total,
            transmissao_id=primeiro.transmissao_id,
            seq=1,
            total_partes=1,
        )
        pacote_final.ttl = menor_ttl
        return pacote_final

    def __repr__(self) -> str:
        tam_str = formatar_tamanho(self.tamanho)
        if self.total_partes > 1:
            return (
                f"[Pacote {self.seq}/{self.total_partes} | {self.arquivo} | "
                f"{tam_str} | {self.origem_ip}->{self.destino_ip}]"
            )
        return (
            f"[Pacote#{self.id} {self.arquivo} | {tam_str} | "
            f"{self.origem_ip}->{self.destino_ip} | TTL={self.ttl}]"
        )


if __name__ == "__main__":
    core = Device("R_Core", "10.0.0.1", tipo="ROUTER")
    pc1 = Device("PC1", "10.0.0.4", tipo="PC")
    assert core.caixa_entrada == []
    assert len(pc1.mac.split(":")) == 6

    tam_mb = converter_para_bytes(50, "MB")
    pacote_inicial = Packet("10.0.0.4", "10.0.0.5", "video.mp4", tam_mb)
    partes = pacote_inicial.dividir()
    del pacote_inicial

    assert len(partes) == calcular_qtd_blocos(tam_mb)
    assert all(isinstance(p, Packet) for p in partes)
    assert sum(p.tamanho for p in partes) == tam_mb

    unido = Packet.unir(partes)
    assert unido.tamanho == tam_mb
    assert unido.total_partes == 1

    # Escala de blocos conforme tamanho
    assert calcular_qtd_blocos(500) < calcular_qtd_blocos(converter_para_bytes(50, "MB"))
    assert calcular_qtd_blocos(converter_para_bytes(50, "MB")) < calcular_qtd_blocos(converter_para_bytes(2, "GB"))
    assert calcular_qtd_blocos(converter_para_bytes(2, "GB")) < calcular_qtd_blocos(converter_para_bytes(1, "TB"))

    pc1.caixa_entrada.append(unido)
    assert len(pc1.caixa_entrada) == 1
    print("models.py OK")