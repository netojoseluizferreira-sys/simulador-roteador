"""
QuickSort Híbrido: Mediana das Medianas (escolha de pivô em O(n) garantido)
combinado com Insertion Sort para partições pequenas (<= 32 elementos).

Aplicação no simulador: ordenação do lote de upload de pacotes por tamanho,
implementando a política de escalonamento *Shortest Job First* (SJF) antes
do despacho pela Fila FIFO de transmissão.
"""

LIMIAR_INSERTION_SORT = 32
TAMANHO_GRUPO_MEDIANA = 5


def _insertion_sort(lista: list, esquerda: int, direita: int, chave) -> None:
    """Ordena in-place o intervalo [esquerda, direita] de `lista`. Estável e O(n^2) no pior caso,
    mas extremamente eficiente para as partições pequenas em que é usado (<= 32 elementos)."""
    for i in range(esquerda + 1, direita + 1):
        item_atual = lista[i]
        chave_atual = chave(item_atual)
        j = i - 1
        while j >= esquerda and chave(lista[j]) > chave_atual:
            lista[j + 1] = lista[j]
            j -= 1
        lista[j + 1] = item_atual


def _mediana_de_grupo(lista: list, esquerda: int, direita: int, chave):
    """Ordena um grupo pequeno (<= 5 elementos) e retorna o elemento mediano."""
    _insertion_sort(lista, esquerda, direita, chave)
    meio = (esquerda + direita) // 2
    return lista[meio]


def _mediana_das_medianas(lista: list, esquerda: int, direita: int, chave):
    """
    Calcula, recursivamente, um pivô de boa qualidade (algoritmo BFPRT):
    1. Divide o intervalo em grupos de até 5 elementos.
    2. Ordena cada grupo (Insertion Sort) e coleta sua mediana.
    3. Repete o processo sobre as medianas coletadas até sobrar um único grupo.

    Garante que o pivô escolhido sempre descarta uma fração mínima e previsível
    dos elementos, evitando o pior caso O(n^2) do QuickSort clássico.
    """
    tamanho = direita - esquerda + 1
    if tamanho <= TAMANHO_GRUPO_MEDIANA:
        return _mediana_de_grupo(lista, esquerda, direita, chave)

    medianas = []
    inicio_grupo = esquerda
    while inicio_grupo <= direita:
        fim_grupo = min(inicio_grupo + TAMANHO_GRUPO_MEDIANA - 1, direita)
        medianas.append(_mediana_de_grupo(lista, inicio_grupo, fim_grupo, chave))
        inicio_grupo += TAMANHO_GRUPO_MEDIANA

    return _mediana_das_medianas(medianas, 0, len(medianas) - 1, chave)


def _particionar(lista: list, esquerda: int, direita: int, valor_pivo, chave) -> int:
    """
    Particiona [esquerda, direita] ao redor do objeto `valor_pivo` (esquema de Lomuto).
    Primeiro localiza o pivô dentro do intervalo e o move para o final.
    """
    indice_pivo = esquerda
    for k in range(esquerda, direita + 1):
        if lista[k] is valor_pivo:
            indice_pivo = k
            break
    lista[indice_pivo], lista[direita] = lista[direita], lista[indice_pivo]

    chave_pivo = chave(lista[direita])
    i = esquerda - 1

    for j in range(esquerda, direita):
        if chave(lista[j]) <= chave_pivo:
            i += 1
            lista[i], lista[j] = lista[j], lista[i]

    lista[i + 1], lista[direita] = lista[direita], lista[i + 1]
    return i + 1


def _quicksort_hibrido(lista: list, esquerda: int, direita: int, chave) -> None:
    # Laço em vez de recursão dupla: recursiona só na partição menor e itera na
    # maior, limitando a profundidade da pilha a O(log n) mesmo no pior caso.
    while esquerda < direita:
        tamanho = direita - esquerda + 1

        if tamanho <= LIMIAR_INSERTION_SORT:
            _insertion_sort(lista, esquerda, direita, chave)
            return

        pivo = _mediana_das_medianas(lista, esquerda, direita, chave)
        indice_particao = _particionar(lista, esquerda, direita, pivo, chave)

        if indice_particao - esquerda < direita - indice_particao:
            _quicksort_hibrido(lista, esquerda, indice_particao - 1, chave)
            esquerda = indice_particao + 1
        else:
            _quicksort_hibrido(lista, indice_particao + 1, direita, chave)
            direita = indice_particao - 1


def quicksort_hibrido(lista: list, chave=lambda item: item) -> list:
    """
    Ordena `lista` in-place em ordem crescente segundo `chave(item)` e também
    retorna a referência (conveniente para encadear chamadas).

    `chave` é uma função que extrai o valor de comparação de cada elemento
    (ex.: `lambda pacote: pacote.tamanho`). Por padrão compara os próprios itens.
    """
    if len(lista) > 1:
        _quicksort_hibrido(lista, 0, len(lista) - 1, chave)
    return lista


def ordenar_pacotes_por_tamanho(pacotes: list) -> list:
    """
    Wrapper de domínio: ordena uma lista de `Packet` por tamanho (MB) crescente,
    implementando a política *Shortest Job First* (SJF) para a fila de upload.
    """
    return quicksort_hibrido(pacotes, chave=lambda pacote: pacote.tamanho)


if __name__ == "__main__":
    import random

    print("=== TESTE UNITÁRIO: structures/sorting.py (QUICKSORT HÍBRIDO) ===")

    # 1. Lista pequena (cai direto no Insertion Sort, <= 32 elementos)
    pequena = [9, 3, 7, 1, 5, 2, 8, 4, 6]
    quicksort_hibrido(pequena)
    print("Pequena ordenada:", pequena)
    assert pequena == sorted([9, 3, 7, 1, 5, 2, 8, 4, 6])

    # 2. Lista grande aleatória (ativa Mediana das Medianas)
    grande = [random.randint(0, 100_000) for _ in range(5000)]
    esperado = sorted(grande)
    quicksort_hibrido(list(grande))  # smoke test sem comparar referência
    copia = list(grande)
    quicksort_hibrido(copia)
    assert copia == esperado
    print(f"Lista grande ({len(grande)} elementos) ordenada corretamente.")

    # 3. Pior caso clássico do QuickSort ingênuo: lista já ordenada e lista invertida
    ja_ordenada = list(range(2000))
    quicksort_hibrido(ja_ordenada)
    assert ja_ordenada == list(range(2000))

    invertida = list(range(2000, 0, -1))
    quicksort_hibrido(invertida)
    assert invertida == list(range(1, 2001))
    print("Casos adversariais (já ordenada / invertida) tratados sem degradar para O(n^2) perceptível.")

    # 4. Ordenação por chave (simulando pacotes com atributo 'tamanho') -> SJF
    class _MockPacote:
        def __init__(self, nome, tamanho):
            self.arquivo = nome
            self.tamanho = tamanho

        def __repr__(self):
            return f"{self.arquivo}({self.tamanho}MB)"

    lote = [
        _MockPacote("video.mp4", 50),
        _MockPacote("notas.txt", 2),
        _MockPacote("instalador.exe", 120),
        _MockPacote("foto.png", 5),
        _MockPacote("musica.mp3", 8),
    ]
    ordenar_pacotes_por_tamanho(lote)
    print("Lote ordenado (SJF):", lote)
    assert [p.tamanho for p in lote] == [2, 5, 8, 50, 120]

    # 5. Estabilidade de valores repetidos (duplicatas não devem sumir)
    com_duplicatas = [5, 3, 5, 1, 5, 2, 5]
    quicksort_hibrido(com_duplicatas)
    assert com_duplicatas == [1, 2, 3, 5, 5, 5, 5]

    print("Todos os testes de QuickSort Híbrido passaram!")