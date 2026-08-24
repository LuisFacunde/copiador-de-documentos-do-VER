# 📋 Processador de Exames de Pacientes

## Requisitos

- Python 3.10+
- Dependências: `openpyxl`, `pyyaml`

---

## Instalação

### Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuração

Cada série de pesquisa é configurada em `series/<nome>/config.yaml`.
Para criar uma nova série, basta criar essa pasta e o arquivo YAML — **nenhum código precisa ser alterado**.

Parâmetros disponíveis:

```yaml
nome: ret_oct_papila

planilha: dados/planilhas/Planilha.xlsx
aba_planilha: "Nome da Aba"
coluna_prontuario: PRONT

dirs_origem:
   - '\\servidor\pasta\exames'
dir_destino: C:/caminho/para/destino

banco_historico: dados/bd/ret_oct_papila.db # gerado automaticamente

data_min: "2020-01-01"
data_max: "2026-06-30"

mapa_tipos: # substring no nome do arquivo → rótulo interno
   RETIN: RET
   OCTPAPILA: OCTPAPILA

tipos_obrigatorios: # todos devem estar presentes (com correspondência na janela)
   - RET
   - OCTPAPILA

janela_dias: 120 # tolerância em dias entre os tipos obrigatórios
extensao_permitida: ".pdf"
limite_pacientes_lote: 2500
```

---

## Execução

**Listar séries disponíveis:**

```bash
python processar_exames.py --listar-series
```

**Processar uma série:**

```bash
python processar_exames.py ret_oct_papila
```

**Reprocessar ignorando o histórico:**

```bash
python processar_exames.py ret_oct_papila --force
```

**Modo silencioso** (log em arquivo é sempre salvo):

```bash
python processar_exames.py ret_oct_papila --silencioso
```

---

## Formato do Nome do Arquivo

O sistema espera arquivos nomeados no formato:

```
PRONTUARIO-ID-YYYYMMDD-TIPO[-...].pdf
```

Exemplo: `2324530-7194197-20250219-RETIN-AO-1739989244.pdf`

Os tipos reconhecidos são definidos em `mapa_tipos` no `config.yaml` de cada série.

---

## Saída

Os arquivos copiados são organizados em subpastas por lote dentro do `dir_destino`:

```
<dir_destino>/
└── Lote 1 - 24-08-2026/
    ├── log_lote_1.txt
    ├── 2324530/
    │   ├── 2324530-...-RETIN.pdf
    │   └── 2324530-...-OCTPAPILA.pdf
    └── 2324531/
        └── ...
```

Cada série mantém seu próprio histórico SQLite em `dados/bd/<nome>.db`.
