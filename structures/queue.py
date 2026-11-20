class _NoFila:
    """Nó interno da lista encadeada que sustenta a Fila."""

    def __init__(self, dado=None):
        self.dado = dado
        self.proximo = None


class Queue:
    """
    Estrutura de dados Fila encadeada com Nós Sentinelas.
    Os nós sentinelas (_sentinela_inicio e _sentinela_fim) delimitam as extremidades da fila,
    eliminando casos especiais de fila vazia durante inserções e remoções em O(1).
    """

    def __init__(self):
        # Nós sentinelas não armazenam dados válidos da aplicação (dado=None)
        self._sentinela_inicio = _NoFila(None)
        self._sentinela_fim = _NoFila(None)

        # Inicialmente, o sentinela de início aponta direto para o sentinela de fim
        self._sentinela_inicio.proximo = self._sentinela_fim
        self._ultimo_valido = self._sentinela_inicio
        self._tamanho = 0

    def is_empty(self) -> bool:
        """Verifica se a fila está vazia checando se o início aponta direto para o fim."""
        return self._sentinela_inicio.proximo is self._sentinela_fim

    def size(self) -> int:
        """Retorna a quantidade de elementos válidos na fila em O(1)."""
        return self._tamanho

    def enqueue(self, item) -> None:
        """
        Insere um novo elemento imediatamente antes do sentinela de fim em O(1).
        Sem necessidade de verificar se a fila estava vazia.
        """
        novo_no = _NoFila(item)
        novo_no.proximo = self._sentinela_fim

        self._ultimo_valido.proximo = novo_no
        self._ultimo_valido = novo_no
        self._tamanho += 1

    def dequeue(self):
        """
        Remove e retorna o primeiro elemento válido após o sentinela de início em O(1).
        """
        if self.is_empty():
            return None

        no_removido = self._sentinela_inicio.proximo
        self._sentinela_inicio.proximo = no_removido.proximo

        # Se removemos o único elemento válido, o último válido volta a ser o sentinela de início
        if self._sentinela_inicio.proximo is self._sentinela_fim:
            self._ultimo_valido = self._sentinela_inicio

        self._tamanho -= 1
        return no_removido.dado

    def peek(self):
        """Consulta o primeiro elemento válido após o sentinela de início sem removê-lo."""
        if self.is_empty():
            return None
        return self._sentinela_inicio.proximo.dado

    def to_list(self) -> list:
        """
        Percorre os nós válidos entre _sentinela_inicio e _sentinela_fim sem alterá-los,
        retornando uma lista para inspeção no terminal.
        """
        elementos = []
        atual = self._sentinela_inicio.proximo
        while atual is not self._sentinela_fim:
            elementos.append(atual.dado)
            atual = atual.proximo
        return elementos


if __name__ == "__main__":
    print("=== TESTE UNITÁRIO: structures/queue.py (COM NÓS SENTINELAS) ===")
    fila = Queue()

    assert fila.is_empty() is True
    assert fila.size() == 0
    assert fila.dequeue() is None
    assert fila.peek() is None

    fila.enqueue("Pacote_1 (doc.txt)")
    fila.enqueue("Pacote_2 (foto.png)")
    fila.enqueue("Pacote_3 (video.mp4)")

    print("Tamanho após 3 inserções:", fila.size())
    print("Frente da fila (peek):", fila.peek())
    print("Estado interno (to_list):", fila.to_list())

    removido_1 = fila.dequeue()
    removido_2 = fila.dequeue()
    print(f"Removidos na ordem FIFO: {removido_1} -> {removido_2}")
    print("Restante na fila:", fila.to_list())

    removido_3 = fila.dequeue()
    assert fila.is_empty() is True
    assert fila._sentinela_inicio.proximo is fila._sentinela_fim

    # Testa reinserção após esvaziar completamente (garante integridade dos sentinelas)
    fila.enqueue("Pacote_4 (reteste.pdf)")
    assert fila.size() == 1
    assert fila.peek() == "Pacote_4 (reteste.pdf)"
    print("Reinserção após esvaziar OK:", fila.to_list())
    print("Todos os testes com Nós Sentinelas passaram!")