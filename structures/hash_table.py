class _NoHash:
    """Nó de lista encadeada usado para resolver colisões (encadeamento separado)."""

    def __init__(self, chave, valor):
        self.chave = chave
        self.valor = valor
        self.proximo = None


class HashTable:
    """
    Tabela Hash com tratamento de colisões por Encadeamento Separado.

    O vetor de baldes (`_baldes`) é a única estrutura "nativa" usada, pois é a
    base indispensável de qualquer tabela hash (não existe equivalente próprio
    para um vetor de tamanho fixo em Python). Cada balde, porém, é a cabeça de
    uma lista encadeada manual (`_NoHash`) — a resolução de colisões em si não
    usa list/dict nativos.

    Aplicação no simulador: indexação O(1) médio de dispositivos (IP/Nome -> Device)
    e rastreamento de predecessores durante a BFS de roteamento (tree.py).
    """

    FATOR_CARGA_MAXIMO = 0.75

    def __init__(self, capacity: int = 11):
        self._capacidade = capacity if capacity > 0 else 11
        self._baldes = [None] * self._capacidade
        self._tamanho = 0

    def _hash(self, chave) -> int:
        """Função hash polinomial (variante djb2) -> índice válido no vetor de baldes."""
        codigo = 5381
        for caractere in str(chave):
            codigo = ((codigo * 33) + ord(caractere)) & 0xFFFFFFFF
        return codigo % self._capacidade

    def insert(self, chave, valor) -> None:
        """Insere ou atualiza um par chave/valor em O(1) médio."""
        indice = self._hash(chave)
        atual = self._baldes[indice]

        while atual is not None:
            if atual.chave == chave:
                atual.valor = valor
                return
            atual = atual.proximo

        novo_no = _NoHash(chave, valor)
        novo_no.proximo = self._baldes[indice]
        self._baldes[indice] = novo_no
        self._tamanho += 1

        if self._fator_de_carga() > HashTable.FATOR_CARGA_MAXIMO:
            self._redimensionar()

    def get(self, chave):
        """Busca o valor associado a uma chave em O(1) médio. Retorna None se ausente."""
        atual = self._baldes[self._hash(chave)]
        while atual is not None:
            if atual.chave == chave:
                return atual.valor
            atual = atual.proximo
        return None

    def remove(self, chave) -> bool:
        """Remove uma chave da tabela. Retorna True se removida, False se não encontrada."""
        indice = self._hash(chave)
        atual = self._baldes[indice]
        anterior = None

        while atual is not None:
            if atual.chave == chave:
                if anterior is None:
                    self._baldes[indice] = atual.proximo
                else:
                    anterior.proximo = atual.proximo
                self._tamanho -= 1
                return True
            anterior = atual
            atual = atual.proximo

        return False

    def contains(self, chave) -> bool:
        """Verifica em O(1) médio se uma chave está presente na tabela."""
        atual = self._baldes[self._hash(chave)]
        while atual is not None:
            if atual.chave == chave:
                return True
            atual = atual.proximo
        return False

    def to_list(self) -> list:
        """Retorna todos os pares (chave, valor) armazenados, para listagem/depuração."""
        pares = []
        for cabeca in self._baldes:
            atual = cabeca
            while atual is not None:
                pares.append((atual.chave, atual.valor))
                atual = atual.proximo
        return pares

    def __len__(self) -> int:
        return self._tamanho

    def _fator_de_carga(self) -> float:
        return self._tamanho / self._capacidade

    def _redimensionar(self) -> None:
        """
        Dobra a capacidade (arredondando para o próximo primo) e redistribui todos
        os elementos existentes, mantendo o fator de carga controlado após o rehash.
        """
        baldes_antigos = self._baldes
        self._capacidade = HashTable._proximo_primo(self._capacidade * 2)
        self._baldes = [None] * self._capacidade
        self._tamanho = 0

        for cabeca in baldes_antigos:
            atual = cabeca
            while atual is not None:
                self.insert(atual.chave, atual.valor)
                atual = atual.proximo

    @staticmethod
    def _eh_primo(numero: int) -> bool:
        if numero < 2:
            return False
        if numero in (2, 3):
            return True
        if numero % 2 == 0:
            return False
        divisor = 3
        while divisor * divisor <= numero:
            if numero % divisor == 0:
                return False
            divisor += 2
        return True

    @staticmethod
    def _proximo_primo(numero: int) -> int:
        candidato = numero if numero % 2 != 0 else numero + 1
        while not HashTable._eh_primo(candidato):
            candidato += 2
        return candidato


if __name__ == "__main__":
    print("=== TESTE UNITÁRIO: structures/hash_table.py (ENCADEAMENTO SEPARADO) ===")
    tabela = HashTable(capacity=5)  # capacidade pequena para forçar colisões e resize

    assert tabela.get("10.0.0.1") is None
    assert len(tabela) == 0

    tabela.insert("10.0.0.1", "R_Core")
    tabela.insert("10.0.0.2", "R_Lab1")
    tabela.insert("R_Core", "10.0.0.1")  # mesma entidade indexada também pelo nome

    print("Busca por IP:", tabela.get("10.0.0.1"))
    print("Busca por Nome:", tabela.get("R_Core"))
    assert tabela.get("10.0.0.1") == "R_Core"
    assert tabela.get("R_Core") == "10.0.0.1"

    # Atualização de valor existente não deve aumentar o tamanho
    tabela.insert("10.0.0.1", "R_Core_Atualizado")
    assert tabela.get("10.0.0.1") == "R_Core_Atualizado"
    assert len(tabela) == 3

    # Força colisões/redimensionamento inserindo várias chaves
    for i in range(3, 30):
        tabela.insert(f"10.0.0.{i}", f"Device{i}")

    assert len(tabela) == 3 + 27
    assert tabela.get("10.0.0.15") == "Device15"
    print(f"Tamanho final: {len(tabela)} | Capacidade após resize: {tabela._capacidade} (primo)")
    assert tabela._fator_de_carga() <= HashTable.FATOR_CARGA_MAXIMO

    assert tabela.contains("10.0.0.2") is True
    assert tabela.remove("10.0.0.2") is True
    assert tabela.contains("10.0.0.2") is False
    assert tabela.remove("10.0.0.2") is False  # já removida

    print("Quantidade de pares (to_list):", len(tabela.to_list()))
    print("Todos os testes de HashTable passaram!")