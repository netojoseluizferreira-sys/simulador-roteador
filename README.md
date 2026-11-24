# Simulador de Roteador Hierárquico (CLI)

Simulador híbrido de rede e roteamento de pacotes via terminal desenvolvido em Python puro (sem dependências externas), aplicando na prática estruturas de dados clássicas e algoritmos de ordenação e busca implementados do zero — com suporte a dispositivos e arquivos **simulados** ou **reais via UDP**.

> **Instituição:** Universidade Federal de Alagoas (UFAL) – Campus Arapiraca  
> **Curso:** Ciência da Computação (2º Período)  
> **Disciplina:** Estrutura de Dados  
> **Autores:** José Luiz Ferreira Neto e Luiz Gustavo Dantas Leão  

---

## Estruturas e Algoritmos Implementados

| Estrutura / Algoritmo | Arquivo | Aplicação no Simulador |
| :--- | :--- | :--- |
| **Tabela Hash** (encadeamento separado) | `structures/hash_table.py` | Indexação O(1) médio de dispositivos (`IP`/`Nome` --> `Device`), rastreamento de predecessores na BFS e buffers de recepção de pacotes. |
| **Árvore N-ária Enraizada + BFS** | `structures/tree.py` | Representação da topologia física da rede (`R_Core` --> setores --> `PCs`) e cálculo de rotas completas entre origem e destino via BFS + menor ancestral comum (LCA). |
| **Fila Encadeada com Nós Sentinelas** | `structures/queue.py` | Fila de transmissão de pacotes em O(1) e fila auxiliar da BFS. |
| **QuickSort Híbrido (3 vias)** | `structures/sorting.py` | Reordenação de pacotes recebidos fora de ordem (por sequência) e ordenação de dispositivos por IP, combinando **Mediana das Medianas**, **particionamento em 3 vias** e **Insertion Sort** para partições de até 32 elementos. |
| **Busca Linear + Hash (DHCP)** | `core/dhcp.py` | Alocação dinâmica e reaproveitamento de endereços IP livres para novos dispositivos. |

---

## Funcionalidades Principais

* **Topologia Hierárquica:** conexão de roteadores de setor ao `R_Core`, conexão de **PCs simulados** ou **PCs reais (via cabo/LAN)** e desconexão com liberação de IP no DHCP.
* **Divisão e Reordenação de Pacotes (MTU 1500 B):** cada envio instancia um `Packet`, divide em pacotes de até **1500 bytes**, enfileira fora de ordem, permite processar **1, 10 ou todos os pacotes**, reordena na recepção e reconstrói o pacote original.
* **Modo Híbrido de Envios:**
  * **Arquivos simulados:** seleção de unidade (`B`, `KB`, `MB`, `GB`, `TB`) antes do valor numérico.
  * **Arquivos reais:** leitura de arquivos colocados em `transfer/`, salvos automaticamente em `data/pcs/<PC>/` (para PCs simulados) ou transmitidos pacote a pacote via **UDP** para PCs reais.
  * **Mensagens de texto:** salvas em `.txt` na pasta do PC destino e legíveis diretamente no terminal pela caixa de entrada.
* **Comunicação UDP Bidirecional (`core/sockets.py`):** o simulador escuta UDP na porta `5001` e o PC real executa `python -m core.sockets` (porta `5000`), permitindo enviar e receber arquivos, mensagens e pings nos dois sentidos.
* **Persistência Automática em JSON (`data/storage.py`):** salva dispositivos, fila, pacotes em trânsito e caixas de entrada ao sair (`0`) e recarrega automaticamente ao iniciar.

---

## Estrutura do Projeto

```text
simulador-roteador/
├── core/
│   ├── models.py          # Entidades Device e Packet (MTU 1500 B, divisão/união)
│   ├── dhcp.py            # Gerenciador de pool de IPs
│   └── sockets.py         # Camada UDP bidirecional, transfer/ e receptor de PC real
├── structures/
│   ├── hash_table.py      # Tabela Hash com encadeamento separado
│   ├── queue.py           # Fila encadeada com nós sentinelas
│   ├── tree.py            # Árvore N-ária, roteamento BFS e entrega de pacotes
│   └── sorting.py         # QuickSort Híbrido (3 vias + Mediana das Medianas + Insertion Sort)
├── data/
│   └── storage.py         # Persistência do estado da rede em JSON
├── transfer/              # Pasta para colocar arquivos reais a serem transferidos
└── main.py                # Interface interativa via terminal (Windows / Linux / macOS)
```

---

## Como Executar

### 1. Simulador Principal (Windows e Linux/macOS)

```bash
# Windows
python main.py

# Linux / macOS
python3 main.py
```

### 2. Conectar um PC Real via Cabo / Rede Local (UDP)

No segundo computador (conectado via cabo Ethernet ou na mesma rede local), execute:

```bash
# Windows
python -m core.sockets

# Linux / macOS
python3 -m core.sockets
```

* O terminal exibirá o **IP local** e a porta (`5000`) para cadastrar no simulador (opção `[3] -> [2] PC real`).
* O simulador principal escuta automaticamente na porta **`5001`** para receber arquivos, mensagens e pings enviados de volta pelo PC real.

### 3. Testes Unitários dos Módulos

```bash
python -m core.models
python -m core.dhcp
python -m structures.hash_table
python -m structures.queue
python -m structures.sorting
python -m structures.tree
```