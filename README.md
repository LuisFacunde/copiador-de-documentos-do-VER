# 📋 Processador de Exames de Pacientes — Sistema de Lotes

## O que faz?

Este sistema **copia exames de pacientes** de um diretório de origem para um destino organizado em **lotes de até 2.500 prontuários**, aplicando filtros e mantendo um **histórico em banco de dados local** para evitar reprocessamento.

### Funcionalidades principais

- ✅ **Lotes automáticos** — Processa até 2.500 prontuários por execução
- ✅ **Histórico SQLite** — Não reprocessa prontuários já copiados
- ✅ **Log por lote** — Arquivo de log detalhado salvo na pasta do lote
- ✅ **Subpastas organizadas** — Saída em `Lote N - DD-MM-AAAA`
- ✅ **CLI com argumentos** — `--force`, `--origem`, `--destino`, `--silencioso`

### Critérios de filtro

- ✅ **Tipos**: Apenas Retinografia (RET) e OCT (Papila)
- ✅ **Período**: De 01/01/2020 a 30/06/2026
- ✅ **Critério de Inclusão (±4 meses)**: O paciente deve possuir pelo menos um exame RET e um exame OCTPAPILA realizados no intervalo de -120 a +120 dias entre si.
- ✅ **Cópia Integral**: Atendido o critério de inclusão, todos os exames RET e OCTPAPILA do paciente no período (2020 a 2026) são copiados.

---

## 📁 Estrutura do Projeto

```
copiador_de_documentos/
├── processar_exames.py           # Entry point (CLI com argparse)
├── dados/
│   ├── planilha_de_testes.xlsx   # Planilha com prontuários
│   └── historico.db              # Banco SQLite (gerado automaticamente)
├── src/
│   ├── __init__.py
│   ├── config.py                 # Configurações e constantes
│   ├── copiador.py               # Lógica de cópia de arquivos
│   ├── filtros.py                # Filtros de tipo, período e janela temporal
│   ├── historico.py              # Módulo de banco de dados (SQLite)
│   ├── leitor_planilha.py        # Leitura da planilha Excel
│   ├── logger.py                 # Módulo de logging por lote
│   ├── parser.py                 # Parser de nomes de arquivo
│   └── relatorio.py              # Relatório final formatado
└── README.md
```

---

## 📁 Estrutura de Saída (Destino)

A saída é organizada em subpastas por lote, facilitando controle e rastreabilidade:

```
anexos_exames_copias/
├── Lote 1 - 05-08-2026/
│   ├── log_lote_1.txt            # Log detalhado do lote
│   ├── 2324530/
│   │   ├── 2324530-xxx-RETIN.pdf
│   │   └── 2324530-xxx-OCT.pdf
│   └── 2324531/
│       └── ...
├── Lote 2 - 12-08-2026/
│   ├── log_lote_2.txt
│   └── ...
└── Lote 3 - 19-08-2026/
    └── ...
```

---

## 🚀 Como Usar

### 1. Prepare o ambiente

Certifique-se de ter **Python 3.10+** e o pacote `openpyxl`:

```bash
pip install openpyxl
```

### 2. Configure os caminhos

Edite `src/config.py` e ajuste:

```python
PLANILHA_PRONTUARIOS = _BASE / 'dados' / 'sua_planilha.xlsx'
DIR_EXAMES_ORIGEM = r'\\192.168.4.18\c$\apache24\htdocs\fav_exames\anexo'
DIR_EXAMES_DESTINO = 'C:/caminho/para/exames_destino'
```

### 3. Execute o script

**Uso básico** (processa até 2.500 prontuários pendentes):

```bash
python processar_exames.py
```

**Reprocessar tudo** (ignora histórico):

```bash
python processar_exames.py --force
```

**Especificar diretórios**:

```bash
python processar_exames.py --origem "D:/exames" --destino "D:/copias"
```

**Modo silencioso** (suprime detalhes no console, mantém log):

```bash
python processar_exames.py --silencioso
```

**Combinando flags**:

```bash
python processar_exames.py --force --silencioso --destino "D:/copias"
```

---

## ⚙️ Argumentos CLI

| Argumento      | Descrição                                                     | Padrão                  |
| -------------- | ------------------------------------------------------------- | ----------------------- |
| `--force`      | Reprocessa prontuários já copiados em lotes anteriores        | `False`                 |
| `--origem`     | Diretório de origem dos exames                                | Definido em `config.py` |
| `--destino`    | Diretório de destino das cópias (lotes serão criados dentro)  | Definido em `config.py` |
| `--silencioso` | Suprime saída detalhada no console (log em arquivo é mantido) | `False`                 |

---

## 📦 Sistema de Lotes

### Como funciona

1. A planilha é lida e os prontuários são extraídos
2. Prontuários já processados são excluídos (consultando o banco de histórico)
3. Os primeiros **2.500** prontuários pendentes são selecionados para o lote atual
4. O número do lote é determinado automaticamente (incremento do último)
5. Uma subpasta é criada: `Lote {N} - {DD-MM-AAAA}`
6. Os prontuários são processados e os arquivos copiados para dentro da pasta do lote
7. Cada cópia é registrada no banco de histórico
8. Um log completo é salvo na pasta do lote
9. O relatório final informa quantos prontuários restam pendentes

### Exemplo de fluxo

```
Execução 1: Planilha tem 6.000 prontuários
  → Lote 1: processa 2.500 | pendentes: 3.500

Execução 2: Mesma planilha
  → Lote 2: processa 2.500 | pendentes: 1.000

Execução 3: Mesma planilha
  → Lote 3: processa 1.000 | pendentes: 0

Execução 4: Mesma planilha
  → "Todos os prontuários já foram processados. Use --force para reprocessar."
```

---

## 🗄️ Banco de Dados (Histórico)

O sistema utiliza **SQLite** (módulo nativo do Python, sem instalação adicional) para manter histórico.

**Localização**: `dados/historico.db`

### Tabelas

#### `lote`

| Coluna              | Tipo    | Descrição                                          |
| ------------------- | ------- | -------------------------------------------------- |
| `id`                | INTEGER | Chave primária                                     |
| `numero`            | INTEGER | Número sequencial do lote                          |
| `data_envio`        | TEXT    | Data do envio (DD-MM-AAAA)                         |
| `data_inicio`       | TEXT    | Timestamp de início do processamento               |
| `data_fim`          | TEXT    | Timestamp de fim do processamento                  |
| `total_prontuarios` | INTEGER | Prontuários com exames copiados                    |
| `total_arquivos`    | INTEGER | Total de arquivos copiados                         |
| `status`            | TEXT    | `em_andamento`, `concluido`, `concluido_com_erros` |

#### `historico_copias`

| Coluna       | Tipo    | Descrição                      |
| ------------ | ------- | ------------------------------ |
| `id`         | INTEGER | Chave primária                 |
| `lote_id`    | INTEGER | FK para tabela `lote`          |
| `prontuario` | TEXT    | Número do prontuário           |
| `arquivo`    | TEXT    | Nome do arquivo copiado        |
| `tipo_exame` | TEXT    | Tipo do exame (RET, OCTPAPILA) |
| `data_exame` | TEXT    | Data do exame (ISO 8601)       |
| `data_copia` | TEXT    | Timestamp da cópia             |

---

## 📄 Log por Lote

Cada lote gera um arquivo de log dentro da sua pasta de destino:

```
Lote 1 - 05-08-2026/
└── log_lote_1.txt
```

### Formato do log

```
[2026-08-05 13:20:00] INFO  | ======================================================================
[2026-08-05 13:20:00] INFO  | 📦 LOTE 1 — 05-08-2026
[2026-08-05 13:20:00] INFO  | ======================================================================
[2026-08-05 13:20:00] INFO  | 📋 Prontuários na planilha: 6000
[2026-08-05 13:20:00] INFO  | 📋 Prontuários neste lote: 2500
[2026-08-05 13:20:00] INFO  | 📋 Prontuários pendentes após este lote: 3500
[2026-08-05 13:20:01] INFO  | [1/2500] Processando prontuário: 2324530
[2026-08-05 13:20:01] INFO  | ✓ 2324530/2324530-xxx-RETIN.pdf (RET) — 19/02/2025
[2026-08-05 13:20:01] INFO  | ✓ 2324530/2324530-xxx-OCT.pdf (OCTPAPILA) — 19/01/2025
...
```

> O arquivo de log registra **tudo** (nível DEBUG), incluindo detalhes que são omitidos no console.

---

## 📊 Exemplo de Saída (Console)

```
📋 Total de prontuários na planilha: 6000
⏭  Prontuários já processados (ignorados): 2500

======================================================================
📦 LOTE 2 — 05-08-2026
======================================================================
📋 Prontuários neste lote: 2500
📋 Prontuários pendentes após este lote: 1000

[1/2500] Processando prontuário: 2324530
   📅 RET mais recente: 19/02/2025 | Limite de 120 dias: 22/10/2024
✓ 2324530/2324530-7194197-20250219-RETIN-AO-1739989244.pdf (RET) — 19/02/2025
...

======================================================================
📊  RELATÓRIO FINAL
📦  Lote 2 — 05-08-2026
======================================================================
✓  Prontuários com exames copiados : 1847
⊘  Prontuários sem exames válidos  : 653
✓  Arquivos PDF copiados           : 4210
⏭  Arquivos já existentes (pulados) : 0
----------------------------------------------------------------------
⊘  Arquivos com nome inválido      : 12
⊘  Arquivos com tipo inválido      : 340
⊘  Arquivos fora do período        : 89
⊘  Arquivos fora da janela         : 156
❌  Erros na cópia                 : 0
----------------------------------------------------------------------
📋  Prontuários pendentes (próximo lote): 1000
======================================================================

📁 Arquivos salvos em: C:/copias/Lote 2 - 05-08-2026
📄 Log salvo em: C:/copias/Lote 2 - 05-08-2026/log_lote_2.txt
```

---

## 📝 Formato do Nome do Arquivo

O script espera o seguinte formato:

```
PRONTUARIO-ID-YYYYMMDD-TIPO-OLHO-TIMESTAMP
```

**Exemplo:**

```
2324530-7194197-20250219-RETIN-AO-1739989244
```

**Partes:**

- `2324530` → Prontuário
- `7194197` → ID (ignorado)
- `20250219` → Data (19/02/2025)
- `RETIN` → Tipo (RET = Retinografia, OCTPAPILA = OCT Papila)
- `AO` → Olho (ignorado)
- `1739989244` → Timestamp (ignorado)

---

## ⚙️ Critérios de Filtro

### 1. **Tipo de Exame**

- ✅ `RETIN` (Retinografia) → Cópia como `RET`
- ✅ `OCTPAPILA` (OCT Papila) → Cópia como `OCTPAPILA`
- ❌ Outros tipos são ignorados

### 2. **Período de Data**

- ✅ De `01/01/2020` a `30/06/2026`
- ❌ Fora deste período = descartado

### 3. **Critério de 4 Meses (120 dias)**

Para **cada tipo de exame independentemente** (RET e OCTPAPILA separados):

1. Encontra o exame **mais recente**
2. Calcula a data limite: `data_mais_recente - 120 dias`
3. Copia todos os exames com `data >= data_limite`

---

## 🔧 Requisitos

- **Python 3.10+**
- **openpyxl** — Leitura de planilhas Excel (`pip install openpyxl`)
- **sqlite3** — Módulo nativo do Python (sem instalação)

---

## 🐛 Troubleshooting

### "Planilha não encontrada"

- Verifique se o caminho em `config.py` está correto
- Verifique se a planilha existe no diretório `dados/`

### "Todos os prontuários já foram processados"

- Use `--force` para reprocessar: `python processar_exames.py --force`

### "Pasta não encontrada" para um prontuário

- A pasta do prontuário não existe no diretório de origem
- Verifique se o nome na planilha corresponde ao nome da pasta

### Problemas de permissão

- Verifique permissão de leitura em `DIR_EXAMES_ORIGEM`
- Verifique permissão de escrita em `DIR_EXAMES_DESTINO`

### Banco de dados corrompido

- Delete `dados/historico.db` e execute novamente (o banco será recriado)
- ⚠️ Isso resetará todo o histórico de lotes

---

## 💡 Dicas

1. **Teste com `--force`** se precisar reprocessar prontuários já copiados
2. **Use `--silencioso`** para execuções em produção (o log é sempre salvo)
3. **Consulte o banco** com qualquer cliente SQLite para auditorias
4. **Guarde as pastas de lote** — cada uma contém seu log para rastreabilidade
5. **Faça backup** dos dados originais antes de usar

---

## 📞 Suporte

Se encontrar problemas, verifique:

- ✅ Planilha existe em `dados/`?
- ✅ Diretórios de origem/destino existem e são acessíveis?
- ✅ Formato do nome do arquivo está correto?
- ✅ Python 3.10+ instalado?
- ✅ Pacote `openpyxl` instalado?
