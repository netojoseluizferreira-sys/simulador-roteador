"""
Gerenciador de pool de endereços IP (DHCP simulado).

Combina Busca Linear (varredura da faixa de IPs configurada) com consultas O(1)
médio à Tabela Hash global de dispositivos para descobrir, sem colisão, qual é
o próximo IP livre a alocar para um dispositivo recém-conectado.
"""


class DHCPServer:
    """
    Gerencia a faixa de endereços IP da rede simulada (ex.: 10.0.0.10 a 10.0.0.254).

    `tabela_dispositivos` é a mesma HashTable (IP/Nome -> Device) usada pelo
    restante do simulador: cada IP candidato é checado nela em O(1) médio
    enquanto a Busca Linear percorre a faixa em busca do primeiro IP livre.
    """

    def __init__(self, tabela_dispositivos, rede_base: str = "10.0.0", inicio: int = 10, fim: int = 254):
        self.tabela_dispositivos = tabela_dispositivos
        self.rede_base = rede_base
        self.inicio = inicio
        self.fim = fim
        self._ips_liberados: list[str] = []  # IPs devolvidos ao pool após desconexão

    def _gerar_faixa_ips(self):
        """Gera, sob demanda, a sequência de IPs possíveis na faixa configurada."""
        for octeto in range(self.inicio, self.fim + 1):
            yield f"{self.rede_base}.{octeto}"

    def alocar_ip(self) -> str | None:
        """
        Retorna o primeiro IP livre disponível, ou None se a faixa estiver esgotada.

        Primeiro tenta reaproveitar um IP recém-liberado (O(1) amortizado); se não
        houver nenhum, faz Busca Linear na faixa completa, validando cada
        candidato em O(1) médio na Tabela Hash.
        """
        while self._ips_liberados:
            candidato = self._ips_liberados.pop()
            if self.tabela_dispositivos.get(candidato) is None:
                return candidato

        for candidato in self._gerar_faixa_ips():  # Busca Linear
            if self.tabela_dispositivos.get(candidato) is None:  # consulta O(1) na Hash
                return candidato

        return None

    def liberar_ip(self, ip: str) -> None:
        """Devolve um IP ao pool quando o dispositivo correspondente é desconectado."""
        self._ips_liberados.append(ip)

    def ips_disponiveis_restantes(self) -> int:
        """Quantidade de IPs ainda não alocados na faixa (aproximação informativa, O(n))."""
        total = 0
        for candidato in self._gerar_faixa_ips():
            if self.tabela_dispositivos.get(candidato) is None:
                total += 1
        return total


if __name__ == "__main__":
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from structures.hash_table import HashTable

    print("=== TESTE UNITÁRIO: core/dhcp.py ===")

    tabela = HashTable(capacity=11)
    dhcp = DHCPServer(tabela, rede_base="10.0.0", inicio=10, fim=12)  # faixa minúscula: só 3 IPs

    # Cada IP só passa a ser considerado "ocupado" quando o dispositivo é
    # de fato cadastrado na Tabela Hash (responsabilidade de quem chama o DHCP)
    ip1 = dhcp.alocar_ip()
    tabela.insert(ip1, "DeviceA")

    ip2 = dhcp.alocar_ip()
    tabela.insert(ip2, "DeviceB")

    ip3 = dhcp.alocar_ip()
    tabela.insert(ip3, "DeviceC")

    print("IPs alocados em sequência:", ip1, ip2, ip3)
    assert [ip1, ip2, ip3] == ["10.0.0.10", "10.0.0.11", "10.0.0.12"]

    ip4 = dhcp.alocar_ip()
    print("Pool esgotado, retornou:", ip4)
    assert ip4 is None
    assert dhcp.ips_disponiveis_restantes() == 0

    # Libera um IP (desconexão) e tabela; deve voltar a ficar disponível
    tabela.remove(ip2)
    dhcp.liberar_ip(ip2)
    ip5 = dhcp.alocar_ip()
    print("IP reaproveitado após desconexão:", ip5)
    assert ip5 == ip2

    print("Todos os testes de DHCPServer passaram!")