"""Árvore N-ária da topologia da rede e núcleo de roteamento."""

from .queue import Queue
from .hash_table import HashTable
from .sorting import ordenar_pacotes_por_sequencia


class NetworkNode:
    """Nó da árvore de rede que armazena um dispositivo e seus filhos."""

    def __init__(self, dispositivo):
        self.dispositivo = dispositivo
        self.filhos = []

    def adicionar_filho(self, novo_no: "NetworkNode") -> None:
        self.filhos.append(novo_no)


class RouterTree:
    """Árvore hierárquica da rede enraizada no roteador principal."""

    def __init__(self, raiz: NetworkNode):
        self.raiz = raiz

    def _buscar_no_por_nome_ou_ip(self, identificador: str) -> NetworkNode | None:
        fila = Queue()
        fila.enqueue(self.raiz)

        while not fila.is_empty():
            atual = fila.dequeue()
            disp = atual.dispositivo

            if disp.nome == identificador or disp.ip == identificador:
                return atual

            for filho in atual.filhos:
                fila.enqueue(filho)

        return None

    def adicionar_pc(self, nome_setor: str, no_pc: NetworkNode) -> bool:
        """Anexa um PC como filho do roteador de setor informado."""
        no_setor = self._buscar_no_por_nome_ou_ip(nome_setor)

        if no_setor is None or no_setor.dispositivo.tipo != "ROUTER":
            return False

        no_setor.adicionar_filho(no_pc)
        return True

    def remover_pc(self, ip_alvo: str) -> bool:
        """Remove um PC da árvore a partir do seu IP."""
        fila = Queue()
        fila.enqueue(self.raiz)

        while not fila.is_empty():
            atual = fila.dequeue()

            for i, filho in enumerate(atual.filhos):
                if filho.dispositivo.ip == ip_alvo and filho.dispositivo.tipo == "PC":
                    atual.filhos.pop(i)
                    return True
                fila.enqueue(filho)

        return False

    def buscar_caminho_bfs(self, ip_destino: str) -> list[NetworkNode] | None:
        """Encontra o caminho da raiz até o IP destino usando BFS."""
        fila = Queue()
        veio_de = HashTable(capacity=23)
        visitados = HashTable(capacity=23)

        fila.enqueue(self.raiz)
        visitados.insert(self.raiz.dispositivo.ip, True)
        veio_de.insert(self.raiz.dispositivo.ip, None)

        no_encontrado = None

        while not fila.is_empty():
            atual = fila.dequeue()

            if atual.dispositivo.ip == ip_destino:
                no_encontrado = atual
                break

            for filho in atual.filhos:
                ip_filho = filho.dispositivo.ip
                if visitados.get(ip_filho) is None:
                    visitados.insert(ip_filho, True)
                    veio_de.insert(ip_filho, atual)
                    fila.enqueue(filho)

        if no_encontrado is None:
            return None

        caminho_reverso = []
        passo = no_encontrado
        while passo is not None:
            caminho_reverso.append(passo)
            passo = veio_de.get(passo.dispositivo.ip)

        caminho_ordenado = []
        for i in range(len(caminho_reverso) - 1, -1, -1):
            caminho_ordenado.append(caminho_reverso[i])

        return caminho_ordenado

    def buscar_rota_entre(self, ip_origem: str, ip_destino: str) -> list[NetworkNode] | None:
        """Calcula a rota completa entre origem e destino na árvore."""
        caminho_origem = self.buscar_caminho_bfs(ip_origem)
        caminho_destino = self.buscar_caminho_bfs(ip_destino)

        if caminho_origem is None or caminho_destino is None:
            return None

        indice_lca = 0
        limite = min(len(caminho_origem), len(caminho_destino))
        while indice_lca + 1 < limite and caminho_origem[indice_lca + 1] is caminho_destino[indice_lca + 1]:
            indice_lca += 1

        subida = []
        for i in range(len(caminho_origem) - 1, indice_lca - 1, -1):
            subida.append(caminho_origem[i])

        return subida + caminho_destino[indice_lca + 1:]

    def imprimir_arvore(self) -> str:
        """Retorna a representação visual da árvore de rede."""
        linhas = []
        self._construir_linhas_arvore(self.raiz, "", True, linhas)
        return "\n".join(linhas)

    def _construir_linhas_arvore(
        self, no: NetworkNode, prefixo: str, eh_ultimo: bool, linhas: list[str]
    ) -> None:
        conector = "└── " if eh_ultimo else "├── "
        disp = no.dispositivo
        tag = "[ROOT]" if no == self.raiz else f"[{disp.tipo}]"

        if no == self.raiz:
            linhas.append(f"{disp.nome} ({disp.ip}) {tag}")
        else:
            linhas.append(f"{prefixo}{conector}{disp.nome} ({disp.ip}) {tag}")

        novo_prefixo = prefixo + ("    " if eh_ultimo else "│   ")
        total_filhos = len(no.filhos)

        for i, filho in enumerate(no.filhos):
            self._construir_linhas_arvore(
                filho, novo_prefixo, i == total_filhos - 1, linhas
            )


class Router:
    """Gerencia a fila de transmissão, o roteamento e a entrega de pacotes."""

    def __init__(self, arvore: RouterTree, tabela_hash: HashTable):
        self.arvore = arvore
        self.tabela_hash = tabela_hash
        self.fila_transmissao = Queue()
        self.buffers_recepcao = HashTable(capacity=53)

    def enfileirar_pacotes(self, pacotes: list) -> int:
        """Adiciona uma lista de pacotes na fila de transmissão."""
        contador = 0
        for pacote in pacotes:
            self.fila_transmissao.enqueue(pacote)
            contador += 1
        return contador

    def total_pacotes_em_transito(self) -> int:
        """Conta quantos pacotes estão aguardando conclusão da entrega."""
        total = 0
        for _chave, lista in self.buffers_recepcao.to_list():
            total += len(lista)
        return total

    def ping(self, identificador_origem: str, identificador_destino: str) -> str:
        """Verifica conectividade e exibe a rota entre dois dispositivos."""
        origem = self.tabela_hash.get(identificador_origem)
        destino = self.tabela_hash.get(identificador_destino)

        if origem is None:
            return f"[ERRO] Origem '{identificador_origem}' não encontrada."
        if destino is None:
            return f"[ERRO] Destino '{identificador_destino}' não encontrado."

        caminho = self.arvore.buscar_rota_entre(origem.ip, destino.ip)
        if caminho is None:
            return f"[ERRO] Rota entre {origem.nome} e {destino.nome} inacessível."

        rota_str = " -> ".join(f"{no.dispositivo.nome} ({no.dispositivo.ip})" for no in caminho)
        saltos = len(caminho) - 1
        return (
            f"[PING OK] {origem.nome} ({origem.ip}) -> {destino.nome} ({destino.ip})\n"
            f"  Rota ({saltos} saltos): {rota_str}"
        )

    def processar_proximo(self) -> str:
        """Processa o próximo pacote da fila, reordena quando completo e entrega ao destino."""
        if self.fila_transmissao.is_empty():
            return "[FILA VAZIA] Nenhum pacote aguardando transmissão."

        pacote = self.fila_transmissao.dequeue()

        origem = self.tabela_hash.get(pacote.origem_ip)
        destino = self.tabela_hash.get(pacote.destino_ip)

        if destino is None:
            if pacote.transmissao_id is not None:
                self.buffers_recepcao.remove(f"{pacote.destino_ip}:{pacote.transmissao_id}")
            return f"[DESCARTE] Destino {pacote.destino_ip} desconectado. '{pacote.arquivo}' descartado."

        if origem is not None:
            caminho = self.arvore.buscar_rota_entre(origem.ip, destino.ip)
        else:
            caminho = self.arvore.buscar_caminho_bfs(destino.ip)

        if caminho is None:
            return f"[ERRO] Falha ao traçar rota para {destino.ip}."

        saltos = len(caminho) - 1
        if saltos > pacote.ttl:
            return f"[DESCARTE] TTL expirado para '{pacote.arquivo}'."

        pacote.ttl -= saltos

        nome_origem = origem.nome if origem else pacote.origem_ip
        rota_str = " -> ".join(no.dispositivo.nome for no in caminho)

        if pacote.total_partes == 1:
            destino.caixa_entrada.append(pacote)
            return (
                f"[ENTREGUE] {pacote} | {nome_origem} -> {destino.nome}\n"
                f"  Rota ({saltos} saltos): {rota_str} | Fila: {self.fila_transmissao.size()}"
            )

        chave_tx = f"{destino.ip}:{pacote.transmissao_id}"
        buffer = self.buffers_recepcao.get(chave_tx)
        if buffer is None:
            buffer = []
            self.buffers_recepcao.insert(chave_tx, buffer)

        buffer.append(pacote)

        if len(buffer) < pacote.total_partes:
            return (
                f"[EM TRÂNSITO] {pacote} | {nome_origem} -> {destino.nome}\n"
                f"  Rota ({saltos} saltos): {rota_str} | "
                f"Recebidos: {len(buffer)}/{pacote.total_partes} | Fila: {self.fila_transmissao.size()}"
            )

        # Reordena os pacotes recebidos e reconstrói o pacote original
        self.buffers_recepcao.remove(chave_tx)
        ordenar_pacotes_por_sequencia(buffer)

        pacote_unido = type(pacote).unir(buffer)
        destino.caixa_entrada.append(pacote_unido)

        return (
            f"[ENTREGUE] {pacote_unido} | {nome_origem} -> {destino.nome}\n"
            f"  Rota ({saltos} saltos): {rota_str} | "
            f"Entregue na caixa de entrada de {destino.nome} | Fila: {self.fila_transmissao.size()}"
        )

    def processar_lote(self, quantidade: int) -> list[str]:
        """Processa até `quantidade` pacotes da fila."""
        if self.fila_transmissao.is_empty():
            return ["[FILA VAZIA] Nenhum pacote aguardando transmissão."]

        logs = []
        for _ in range(quantidade):
            if self.fila_transmissao.is_empty():
                break
            logs.append(self.processar_proximo())
        return logs

    def processar_tudo(self) -> list[str]:
        """Processa todos os pacotes pendentes na fila."""
        if self.fila_transmissao.is_empty():
            return ["[FILA VAZIA] Nenhum pacote aguardando transmissão."]

        logs = []
        while not self.fila_transmissao.is_empty():
            logs.append(self.processar_proximo())
        return logs


if __name__ == "__main__":
    import random
    import sys
    from core.models import Device, Packet, converter_para_bytes

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ht = HashTable(capacity=11)
    dev_core = Device("R_Core", "10.0.0.1", "ROUTER")
    dev_lab1 = Device("R_Lab1", "10.0.0.2", "ROUTER")
    dev_lab2 = Device("R_Lab2", "10.0.0.3", "ROUTER")
    dev_pc1 = Device("PC1", "10.0.0.4", "PC")
    dev_pc2 = Device("PC2", "10.0.0.5", "PC")
    dev_pc3 = Device("PC3", "10.0.0.6", "PC")

    for d in (dev_core, dev_lab1, dev_lab2, dev_pc1, dev_pc2, dev_pc3):
        ht.insert(d.ip, d)
        ht.insert(d.nome, d)

    no_core = NetworkNode(dev_core)
    no_core.adicionar_filho(NetworkNode(dev_lab1))
    no_core.adicionar_filho(NetworkNode(dev_lab2))

    arvore = RouterTree(no_core)
    assert arvore.adicionar_pc("R_Lab1", NetworkNode(dev_pc1)) is True
    assert arvore.adicionar_pc("R_Lab2", NetworkNode(dev_pc2)) is True
    assert arvore.adicionar_pc("R_Lab1", NetworkNode(dev_pc3)) is True

    assert [n.dispositivo.nome for n in arvore.buscar_rota_entre("10.0.0.4", "10.0.0.5")] == [
        "PC1", "R_Lab1", "R_Core", "R_Lab2", "PC2"
    ]
    assert [n.dispositivo.nome for n in arvore.buscar_rota_entre("10.0.0.4", "10.0.0.6")] == [
        "PC1", "R_Lab1", "PC3"
    ]

    roteador = Router(arvore, ht)
    tam_arq = converter_para_bytes(25, "KB")
    pacote_inicial = Packet("10.0.0.4", "10.0.0.5", "aula.pdf", tam_arq)
    partes = pacote_inicial.dividir()
    del pacote_inicial
    random.shuffle(partes)
    roteador.enfileirar_pacotes(partes)

    logs_10 = roteador.processar_lote(10)
    assert len(logs_10) == 10
    roteador.processar_tudo()

    assert len(dev_pc2.caixa_entrada) == 1
    assert dev_pc2.caixa_entrada[0].tamanho == tam_arq
    assert dev_pc2.caixa_entrada[0].ttl == 12
    print("tree.py OK")