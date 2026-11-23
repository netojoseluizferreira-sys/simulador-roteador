"""Gerenciador de endereços IP (DHCP simulado)."""


class DHCPServer:
    """Aloca e libera IPs livres consultando a tabela de dispositivos."""

    def __init__(self, tabela_dispositivos, rede_base: str = "10.0.0", inicio: int = 10, fim: int = 254):
        self.tabela_dispositivos = tabela_dispositivos
        self.rede_base = rede_base
        self.inicio = inicio
        self.fim = fim
        self._ips_liberados: list[str] = []

    def _gerar_faixa_ips(self):
        for octeto in range(self.inicio, self.fim + 1):
            yield f"{self.rede_base}.{octeto}"

    def alocar_ip(self) -> str | None:
        """Retorna o primeiro IP disponível ou None se a faixa estiver esgotada."""
        while self._ips_liberados:
            candidato = self._ips_liberados.pop()
            if self.tabela_dispositivos.get(candidato) is None:
                return candidato

        for candidato in self._gerar_faixa_ips():
            if self.tabela_dispositivos.get(candidato) is None:
                return candidato

        return None

    def liberar_ip(self, ip: str) -> None:
        """Devolve um IP ao pool para reutilização."""
        if ip not in self._ips_liberados:
            self._ips_liberados.append(ip)

    def ips_disponiveis_restantes(self) -> int:
        """Conta quantos IPs da faixa ainda estão livres."""
        total = 0
        for candidato in self._gerar_faixa_ips():
            if self.tabela_dispositivos.get(candidato) is None:
                total += 1
        return total


if __name__ == "__main__":
    from structures.hash_table import HashTable

    tabela = HashTable(capacity=11)
    dhcp = DHCPServer(tabela, rede_base="10.0.0", inicio=10, fim=12)

    ip1 = dhcp.alocar_ip()
    tabela.insert(ip1, "DeviceA")
    ip2 = dhcp.alocar_ip()
    tabela.insert(ip2, "DeviceB")
    ip3 = dhcp.alocar_ip()
    tabela.insert(ip3, "DeviceC")

    assert [ip1, ip2, ip3] == ["10.0.0.10", "10.0.0.11", "10.0.0.12"]
    assert dhcp.alocar_ip() is None
    assert dhcp.ips_disponiveis_restantes() == 0

    tabela.remove(ip2)
    dhcp.liberar_ip(ip2)
    assert dhcp.alocar_ip() == ip2
    print("dhcp.py OK")