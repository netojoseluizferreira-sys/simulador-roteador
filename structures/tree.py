from queue import Queue

# TODO: Quando imperador subir o hash_table.py e o models.py:
# 1. Descomentar a linha abaixo:
# from structures.hash_table import HashTable
# 2. Apagar a classe temporária HashTable logo abaixo.


class HashTable:
    """
    Adaptador temporário usando dict nativo apenas para testes isolados.
    Mantém a mesma interface (.insert e .get) da HashTable definitiva.
    """

    def __init__(self, capacity: int = 11):
        self._dados = {}

    def insert(self, chave: str, valor) -> None:
        self._dados[chave] = valor

    def get(self, chave: str):
        return self._dados.get(chave, None)


class NetworkNode:
    """
    Nó da Árvore N-ária da rede.
    Segue o modelo enraizado clássico: guarda apenas a lista de filhos (sem ponteiro para o pai).
    """

    def __init__(self, dispositivo):
        self.dispositivo = dispositivo  # Objeto Device (nome, ip, tipo, caixa_entrada)
        self.filhos = []                # Lista de NetworkNode conectados abaixo deste nó

    def adicionar_filho(self, novo_no: "NetworkNode") -> None:
        """Conecta um nó filho diretamente abaixo deste nó."""
        self.filhos.append(novo_no)


class RouterTree:
    """
    Árvore N-ária que representa a topologia hierárquica da rede.
    A raiz (root) é o Roteador Principal (Gateway) por onde passam todas as rotas.
    """

    def __init__(self, raiz: NetworkNode):
        self.raiz = raiz

    def _buscar_no_por_nome_ou_ip(self, identificador: str) -> NetworkNode | None:
        """Percorre a árvore via BFS para localizar um nó pelo nome ou IP."""
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
        """
        Localiza o roteador de setor indicado e anexa o novo PC como seu filho.
        Retorna True se anexado com sucesso ou False se o setor for inválido.
        """
        no_setor = self._buscar_no_por_nome_ou_ip(nome_setor)

        if no_setor is None or no_setor.dispositivo.tipo != "ROUTER":
            return False

        no_setor.adicionar_filho(no_pc)
        return True

    def remover_pc(self, ip_alvo: str) -> bool:
        """
        Remove um PC folha da árvore a partir do seu IP usando BFS para localizar seu pai.
        """
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
        """
        Executa uma Busca em Largura (BFS) a partir da raiz (R_Core) até o IP destino.
        Reutiliza a Queue própria para exploração e a HashTable para rastrear predecessores.
        """
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

        # Reconstrói o trajeto do destino até a raiz consultando a HashTable
        caminho_reverso = []
        passo = no_encontrado
        while passo is not None:
            caminho_reverso.append(passo)
            passo = veio_de.get(passo.dispositivo.ip)

        # Inverte manualmente para retornar na ordem: Raiz -> ... -> Destino
        caminho_ordenado = []
        for i in range(len(caminho_reverso) - 1, -1, -1):
            caminho_ordenado.append(caminho_reverso[i])

        return caminho_ordenado

    def imprimir_arvore(self) -> str:
        """Gera uma string visual da hierarquia completa da rede para o terminal."""
        linhas = []
        self._construir_linhas_arvore(self.raiz, "", True, linhas)
        return "\n".join(linhas)

    def _construir_linhas_arvore(
        self, no: NetworkNode, prefixo: str, eh_ultimo: bool, linhas: list[str]
    ) -> None:
        """Método recursivo auxiliar (percurso em pré-ordem) para formatar os galhos."""
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
    """
    Núcleo de roteamento integrado à Árvore N-ária.
    Gerencia a Fila FIFO de transmissão, valida dispositivos na Tabela Hash
    e despacha pacotes seguindo a rota descoberta pela BFS.
    """

    def __init__(self, arvore: RouterTree, tabela_hash: HashTable):
        self.arvore = arvore
        self.tabela_hash = tabela_hash
        self.fila_transmissao = Queue()

    def enfileirar_pacotes(self, pacotes: list) -> int:
        """
        Recebe uma lista de pacotes (já ordenados pelo QuickSort Híbrido)
        e os insere na Fila FIFO de transmissão.
        """
        contador = 0
        for pacote in pacotes:
            self.fila_transmissao.enqueue(pacote)
            contador += 1
        return contador

    def ping(self, identificador_origem: str, identificador_destino: str) -> str:
        """
        Consulta origem e destino na Tabela Hash em O(1) e executa a BFS na Árvore
        para exibir o trajeto desde o Roteador Core até o destino.
        """
        origem = self.tabela_hash.get(identificador_origem)
        destino = self.tabela_hash.get(identificador_destino)

        if origem is None:
            return f"[ERRO] Origem '{identificador_origem}' não encontrada na Tabela Hash."
        if destino is None:
            return f"[ERRO] Destino '{identificador_destino}' não encontrado na Tabela Hash."

        caminho = self.arvore.buscar_caminho_bfs(destino.ip)
        if caminho is None:
            return f"[ERRO] Destino {destino.nome} ({destino.ip}) inacessível na árvore."

        rota_str = " -> ".join(f"{no.dispositivo.nome} ({no.dispositivo.ip})" for no in caminho)
        saltos = len(caminho) - 1
        return (
            f"[PING OK] {origem.nome} ({origem.ip}) -> Gateway -> {destino.nome} ({destino.ip})\n"
            f"  Rota BFS ({saltos} saltos): {rota_str}"
        )

    def processar_proximo(self) -> str:
        """
        Retira o primeiro pacote da Fila de transmissão (step), valida origem/destino
        na Tabela Hash, calcula a rota via BFS na Árvore e entrega na caixa de entrada.
        """
        if self.fila_transmissao.is_empty():
            return "[FILA VAZIA] Nenhum pacote aguardando transmissão."

        pacote = self.fila_transmissao.dequeue()

        origem = self.tabela_hash.get(pacote.origem_ip)
        destino = self.tabela_hash.get(pacote.destino_ip)

        if destino is None:
            return f"[DESCARTE] Destino {pacote.destino_ip} desconectado. Pacote '{pacote.arquivo}' descartado."

        caminho = self.arvore.buscar_caminho_bfs(destino.ip)
        if caminho is None:
            return f"[ERRO ROTA] Falha ao traçar rota BFS para {destino.ip}."

        # Entrega efetiva do pacote no dispositivo destinatário
        destino.caixa_entrada.append(pacote)

        nome_origem = origem.nome if origem else pacote.origem_ip
        rota_str = " -> ".join(no.dispositivo.nome for no in caminho)

        return (
            f"[ENTREGUE] '{pacote.arquivo}' ({pacote.tamanho}MB) | {nome_origem} -> {destino.nome}\n"
            f"  Trajeto BFS: {rota_str} | Restantes na fila: {self.fila_transmissao.size()}"
        )

    def processar_tudo(self) -> list[str]:
        """Processa todos os pacotes pendentes na Fila de transmissão até esvaziá-la."""
        if self.fila_transmissao.is_empty():
            return ["[FILA VAZIA] Nenhum pacote aguardando transmissão."]

        logs = []
        while not self.fila_transmissao.is_empty():
            logs.append(self.processar_proximo())
        return logs


if __name__ == "__main__":
    # Classes simuladas locais (usadas apenas neste teste enquanto core/models.py não existe)
    class _MockDevice:
        def __init__(self, nome: str, ip: str, tipo: str = "PC"):
            self.nome = nome
            self.ip = ip
            self.tipo = tipo
            self.caixa_entrada = []

        def __repr__(self):
            return f"{self.nome} ({self.ip})"

    class _MockPacket:
        def __init__(self, origem_ip: str, destino_ip: str, arquivo: str, tamanho: int, conteudo: str = ""):
            self.origem_ip = origem_ip
            self.destino_ip = destino_ip
            self.arquivo = arquivo
            self.tamanho = tamanho
            self.conteudo = conteudo

        def __repr__(self):
            return f"[{self.arquivo} | {self.tamanho}MB]"

    print("=== TESTE UNITÁRIO: structures/tree.py (100% AUTÔNOMO) ===")
    ht = HashTable(capacity=11)

    dev_core = _MockDevice("R_Core", "10.0.0.1", "ROUTER")
    dev_lab1 = _MockDevice("R_Lab1", "10.0.0.2", "ROUTER")
    dev_lab2 = _MockDevice("R_Lab2", "10.0.0.3", "ROUTER")
    dev_pc1 = _MockDevice("PC1", "10.0.0.4", "PC")
    dev_pc2 = _MockDevice("PC2", "10.0.0.5", "PC")

    for d in (dev_core, dev_lab1, dev_lab2, dev_pc1, dev_pc2):
        ht.insert(d.ip, d)
        ht.insert(d.nome, d)

    no_core = NetworkNode(dev_core)
    no_lab1 = NetworkNode(dev_lab1)
    no_lab2 = NetworkNode(dev_lab2)
    no_core.adicionar_filho(no_lab1)
    no_core.adicionar_filho(no_lab2)

    arvore = RouterTree(no_core)
    assert arvore.adicionar_pc("R_Lab1", NetworkNode(dev_pc1)) is True
    assert arvore.adicionar_pc("R_Lab2", NetworkNode(dev_pc2)) is True

    print("\n1. Topologia da Árvore:")
    print(arvore.imprimir_arvore())

    roteador = Router(arvore, ht)

    print("\n2. Teste PING:")
    print(roteador.ping("PC1", "PC2"))

    print("\n3. Teste Enfileiramento e Processamento (step):")
    roteador.enfileirar_pacotes([
        _MockPacket("10.0.0.4", "10.0.0.5", "notas.txt", 2, "Resumo"),
        _MockPacket("10.0.0.4", "10.0.0.5", "video.mp4", 50, "Aula"),
    ])
    print(roteador.processar_proximo())
    print(roteador.processar_proximo())
    assert len(dev_pc2.caixa_entrada) == 2
    print("\nCaixa de entrada do PC2:", dev_pc2.caixa_entrada)
    print("Todos os testes de Tree e Router passaram!")