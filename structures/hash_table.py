"""Tabela Hash com encadeamento separado e redimensionamento dinâmico."""


class _NoHash:
    def __init__(self, chave, valor):
        self.chave = chave
        self.valor = valor
        self.proximo = None


class HashTable:
    """Tabela Hash com busca, inserção e remoção em O(1) médio."""

    FATOR_CARGA_MAXIMO = 0.75

    def __init__(self, capacity: int = 11):
        self._capacidade = capacity if capacity > 0 else 11
        self._baldes = [None] * self._capacidade
        self._tamanho = 0

    def _hash(self, chave) -> int:
        codigo = 5381
        for caractere in str(chave):
            codigo = ((codigo * 33) + ord(caractere)) & 0xFFFFFFFF
        return codigo % self._capacidade

    def insert(self, chave, valor) -> None:
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
        atual = self._baldes[self._hash(chave)]
        while atual is not None:
            if atual.chave == chave:
                return atual.valor
            atual = atual.proximo
        return None

    def remove(self, chave) -> bool:
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
        atual = self._baldes[self._hash(chave)]
        while atual is not None:
            if atual.chave == chave:
                return True
            atual = atual.proximo
        return False

    def to_list(self) -> list:
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
    tabela = HashTable(capacity=5)
    assert tabela.get("10.0.0.1") is None
    assert len(tabela) == 0

    tabela.insert("10.0.0.1", "R_Core")
    tabela.insert("10.0.0.2", "R_Lab1")
    tabela.insert("R_Core", "10.0.0.1")
    assert tabela.get("10.0.0.1") == "R_Core"
    assert tabela.get("R_Core") == "10.0.0.1"

    tabela.insert("10.0.0.1", "R_Core_Atualizado")
    assert tabela.get("10.0.0.1") == "R_Core_Atualizado"
    assert len(tabela) == 3

    for i in range(3, 30):
        tabela.insert(f"10.0.0.{i}", f"Device{i}")

    assert len(tabela) == 30
    assert tabela.get("10.0.0.15") == "Device15"
    assert tabela._fator_de_carga() <= HashTable.FATOR_CARGA_MAXIMO

    assert tabela.contains("10.0.0.2") is True
    assert tabela.remove("10.0.0.2") is True
    assert tabela.contains("10.0.0.2") is False
    assert tabela.remove("10.0.0.2") is False
    print("hash_table.py OK")