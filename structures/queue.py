"""Fila encadeada com nós sentinelas."""


class _NoFila:
    def __init__(self, dado=None):
        self.dado = dado
        self.proximo = None


class Queue:
    """Fila encadeada com inserção e remoção em O(1)."""

    def __init__(self):
        self._sentinela_inicio = _NoFila(None)
        self._sentinela_fim = _NoFila(None)
        self._sentinela_inicio.proximo = self._sentinela_fim
        self._ultimo_valido = self._sentinela_inicio
        self._tamanho = 0

    def is_empty(self) -> bool:
        return self._sentinela_inicio.proximo is self._sentinela_fim

    def size(self) -> int:
        return self._tamanho

    def enqueue(self, item) -> None:
        novo_no = _NoFila(item)
        novo_no.proximo = self._sentinela_fim
        self._ultimo_valido.proximo = novo_no
        self._ultimo_valido = novo_no
        self._tamanho += 1

    def dequeue(self):
        if self.is_empty():
            return None

        no_removido = self._sentinela_inicio.proximo
        self._sentinela_inicio.proximo = no_removido.proximo

        if self._sentinela_inicio.proximo is self._sentinela_fim:
            self._ultimo_valido = self._sentinela_inicio

        self._tamanho -= 1
        return no_removido.dado

    def peek(self):
        if self.is_empty():
            return None
        return self._sentinela_inicio.proximo.dado

    def to_list(self) -> list:
        elementos = []
        atual = self._sentinela_inicio.proximo
        while atual is not self._sentinela_fim:
            elementos.append(atual.dado)
            atual = atual.proximo
        return elementos


if __name__ == "__main__":
    fila = Queue()
    assert fila.is_empty() is True
    assert fila.size() == 0
    assert fila.dequeue() is None
    assert fila.peek() is None

    fila.enqueue("Pacote_1")
    fila.enqueue("Pacote_2")
    fila.enqueue("Pacote_3")
    assert fila.size() == 3
    assert fila.peek() == "Pacote_1"

    assert fila.dequeue() == "Pacote_1"
    assert fila.dequeue() == "Pacote_2"
    assert fila.dequeue() == "Pacote_3"
    assert fila.is_empty() is True

    fila.enqueue("Pacote_4")
    assert fila.size() == 1
    assert fila.peek() == "Pacote_4"
    print("queue.py OK")