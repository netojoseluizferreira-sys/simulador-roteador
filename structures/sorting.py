"""Ordenação com QuickSort híbrido (Mediana das Medianas + Insertion Sort)."""

LIMIAR_INSERTION_SORT = 32
TAMANHO_GRUPO_MEDIANA = 5


def _insertion_sort(lista: list, esquerda: int, direita: int, chave) -> None:
    for i in range(esquerda + 1, direita + 1):
        item_atual = lista[i]
        chave_atual = chave(item_atual)
        j = i - 1
        while j >= esquerda and chave(lista[j]) > chave_atual:
            lista[j + 1] = lista[j]
            j -= 1
        lista[j + 1] = item_atual


def _mediana_de_grupo(lista: list, esquerda: int, direita: int, chave):
    _insertion_sort(lista, esquerda, direita, chave)
    return lista[(esquerda + direita) // 2]


def _mediana_das_medianas(lista: list, esquerda: int, direita: int, chave):
    """Seleciona um pivô balanceado dividindo o intervalo em grupos de 5."""
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


def _particionar_3_vias(lista: list, esquerda: int, direita: int, chave_pivo, chave) -> tuple[int, int]:
    """Particiona o intervalo em menores, iguais e maiores que o pivô."""
    lt = esquerda
    i = esquerda
    gt = direita

    while i <= gt:
        chave_atual = chave(lista[i])
        if chave_atual < chave_pivo:
            lista[lt], lista[i] = lista[i], lista[lt]
            lt += 1
            i += 1
        elif chave_atual > chave_pivo:
            lista[i], lista[gt] = lista[gt], lista[i]
            gt -= 1
        else:
            i += 1

    return lt, gt


def _quicksort_hibrido(lista: list, esquerda: int, direita: int, chave) -> None:
    while esquerda < direita:
        if direita - esquerda + 1 <= LIMIAR_INSERTION_SORT:
            _insertion_sort(lista, esquerda, direita, chave)
            return

        pivo = _mediana_das_medianas(lista, esquerda, direita, chave)
        lt, gt = _particionar_3_vias(lista, esquerda, direita, chave(pivo), chave)

        if lt - esquerda < direita - gt:
            _quicksort_hibrido(lista, esquerda, lt - 1, chave)
            esquerda = gt + 1
        else:
            _quicksort_hibrido(lista, gt + 1, direita, chave)
            direita = lt - 1


def quicksort_hibrido(lista: list, chave=lambda item: item) -> list:
    """Ordena a lista in-place em ordem crescente conforme `chave`."""
    if len(lista) > 1:
        _quicksort_hibrido(lista, 0, len(lista) - 1, chave)
    return lista


def ordenar_pacotes_por_tamanho(pacotes: list) -> list:
    """Ordena pacotes por tamanho crescente."""
    return quicksort_hibrido(pacotes, chave=lambda pacote: pacote.tamanho)


def ordenar_pacotes_por_sequencia(pacotes: list) -> list:
    """Ordena pacotes divididos pelo número de sequência."""
    return quicksort_hibrido(pacotes, chave=lambda pacote: pacote.seq)


if __name__ == "__main__":
    import random
    from core.models import Packet, converter_para_bytes

    pequena = [9, 3, 7, 1, 5, 2, 8, 4, 6]
    quicksort_hibrido(pequena)
    assert pequena == sorted([9, 3, 7, 1, 5, 2, 8, 4, 6])

    grande = [random.randint(0, 100_000) for _ in range(5000)]
    esperado = sorted(grande)
    quicksort_hibrido(grande)
    assert grande == esperado

    ja_ordenada = list(range(2000))
    quicksort_hibrido(ja_ordenada)
    assert ja_ordenada == list(range(2000))

    invertida = list(range(2000, 0, -1))
    quicksort_hibrido(invertida)
    assert invertida == list(range(1, 2001))

    todos_iguais = [7] * 2000
    quicksort_hibrido(todos_iguais)
    assert todos_iguais == [7] * 2000

    pacote = Packet("10.0.0.10", "10.0.0.11", "video.mp4", converter_para_bytes(50, "MB"))
    partes = pacote.dividir()
    del pacote
    random.shuffle(partes)
    ordenar_pacotes_por_sequencia(partes)
    assert [p.seq for p in partes] == list(range(1, len(partes) + 1))

    com_duplicatas = [5, 3, 5, 1, 5, 2, 5]
    quicksort_hibrido(com_duplicatas)
    assert com_duplicatas == [1, 2, 3, 5, 5, 5, 5]
    print("sorting.py OK")