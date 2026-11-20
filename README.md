# Simulador de Roteador Hierárquico (CLI)

Simulador de rede e roteamento de pacotes via terminal desenvolvido em Python puro, aplicando na prática estruturas de dados clássicas e algoritmos de ordenação e busca implementados do zero (sem uso de estruturas nativas equivalentes para o núcleo do sistema).

> **Instituição:** Universidade Federal de Alagoas (UFAL) – Campus Arapiraca  
> **Curso:** Ciência da Computação (2º Período)  
> **Disciplina:** Estrutura de Dados  
> **Autores:** José Luiz Ferreira Neto e Luiz Gustavo Dantas Leão  

---

## Estruturas e Algoritmos Implementados

| Estrutura / Algoritmo | Arquivo | Aplicação no Simulador |
| :--- | :--- | :--- |
| **Tabela Hash** (encadeamento separado) | `structures/hash_table.py` | Indexação $O(1)$ médio de dispositivos (`IP`/`Nome` $\rightarrow$ `Device`) e rastreamento de predecessores na BFS. |
| **Árvore N-ária Enraizada + BFS** | `structures/tree.py` | Representação da topologia física da rede (`R_Core` $\rightarrow$ setores $\rightarrow$ `PCs`) e descoberta de rotas via Busca em Largura a partir da raiz. |
| **Fila Encadeada (FIFO)** | `structures/queue.py` | Buffer de transmissão de pacotes (ordem de despacho) e fila auxiliar de exploração da BFS. |
| **QuickSort Híbrido** | `structures/sorting.py` | Ordenação de lotes de upload por tamanho (*Shortest Job First*), combinando **Mediana das Medianas** para escolha de pivô e **Insertion Sort** para partições de até 32 elementos. |
| **Busca Linear + Hash (DHCP)** | `core/dhcp.py` | Alocação dinâmica de endereços IP livres para novos dispositivos conectados à rede. |

---

## Estrutura do Projeto

```text
simulador-roteador/
├── structures/
│   ├── hash_table.py      # Tabela Hash com tratamento de colisões
│   ├── queue.py           # Fila FIFO encadeada (head/tail)
│   ├── tree.py            # Árvore N-ária + roteamento BFS
│   └── sorting.py         # QuickSort + Mediana das Medianas + Insertion Sort (<= 32)
├── core/
│   ├── models.py          # Entidades Device e Packet
│   └── dhcp.py            # Gerenciador de pool de IPs
└── main.py                # Interface interativa via terminal (CLI)