# 📋 Script de Processamento de Exames de Pacientes

## O que faz?

Este script **copia exames de pacientes** com base em critérios específicos:

- ✅ **Tipos**: Apenas Retinografia (RET) e OCT (Papila)
- ✅ **Período**: De 01/01/2020 a 30/06/2026
- ✅ **Critério de 4 meses**: Para cada tipo de exame, copia apenas aqueles que não são mais antigos que 4 meses (120 dias) do exame mais recente

---

## 📁 Estrutura de Diretórios

### Entrada (diretório de origem)

```
exames_origem/
├── 2324530/
│   ├── 2324530-7194197-20250219-RETIN-AO-1739989244
│   ├── 2324530-7194197-20250119-OCT-AO-1739989244
│   ├── 2324530-7194197-20241119-RETIN-OD-1739989244
│   └── 2324530-7194197-20231215-OCT-OE-1739989244
├── 2324531/
│   ├── 2324531-7194198-20260110-RETIN-AO-1739989245
│   └── 2324531-7194198-20260210-OCT-AO-1739989245
└── 2324532/
    └── ...
```

### Saída (diretório de destino)

A mesma estrutura será criada com apenas os arquivos que atendem aos critérios:

```
exames_destino/
├── 2324530/
│   ├── 2324530-7194197-20250219-RETIN-AO-1739989244
│   └── 2324530-7194197-20250119-OCT-AO-1739989244
├── 2324531/
│   ├── 2324531-7194198-20260110-RETIN-AO-1739989245
│   └── 2324531-7194198-20260210-OCT-AO-1739989245
└── 2324532/
    └── ...
```

---

## 🚀 Como Usar

### 1. Prepare o arquivo de prontuários

Crie um arquivo `pronunciarios.txt` com **um prontuário por linha**:

```txt
2324530
2324531
2324532
2324533
```

### 2. Configure os caminhos no script

Abra `processar_exames.py` e ajuste:

```python
LISTA_PRONUNCIARIOS = 'pronunciarios.txt'              # Seu arquivo
DIR_EXAMES_ORIGEM = '/caminho/para/exames_origem'    # Diretório com as pastas de prontuários
DIR_EXAMES_DESTINO = '/caminho/para/exames_destino'  # Onde copiar os arquivos
```

**Exemplos de caminhos:**

- **Windows**: `C:/dados/exames_origem`
- **Linux/Mac**: `/home/user/dados/exames_origem`

### 3. Execute o script

```bash
python processar_exames.py
```

### 4. Verifique o resultado

O script gera um **relatório detalhado** mostrando:
- ✓ Quantos prontuários foram processados
- ✓ Quantos arquivos foram copiados
- ⊘ Erros e avisos

---

## 📊 Exemplo de Saída

```
📋 Total de prontuários a processar: 3

   📅 RET mais recente: 19/02/2025 | Limite de 4 meses: 19/10/2024
   📅 OCT mais recente: 19/01/2025 | Limite de 4 meses: 19/09/2024
✓ 2324530/2324530-7194197-20250219-RETIN-AO-1739989244 (RET) - 19/02/2025
✓ 2324530/2324530-7194197-20250119-OCT-AO-1739989244 (OCT) - 19/01/2025
      ⊘ 2324530-7194197-20231215-OCT-OE-1739989244 (OCT) - 15/12/2023 (anterior aos 4 meses)

   📅 RET mais recente: 10/01/2026 | Limite de 4 meses: 10/09/2025
   📅 OCT mais recente: 10/02/2026 | Limite de 4 meses: 10/10/2025
✓ 2324531/2324531-7194198-20260110-RETIN-AO-1739989245 (RET) - 10/01/2026
✓ 2324531/2324531-7194198-20260210-OCT-AO-1739989245 (OCT) - 10/02/2026

======================================================================
📊 RELATÓRIO FINAL
======================================================================
✓ Prontuários com exames válidos: 2
⊘ Prontuários sem exames válidos: 1
✓ Arquivos copiados com sucesso: 4
----------------------------------------------------------------------
⊘ Arquivos com erro de parse: 0
⊘ Arquivos com tipo inválido (nem RET nem OCT): 0
⊘ Arquivos fora do período permitido: 1
⊘ Arquivos fora do critério de 4 meses: 1
❌ Erros na cópia: 0
======================================================================
```

---

## 🔧 Requisitos

- **Python 3.6+** (qualquer versão recente)
- Nenhuma biblioteca adicional necessária (usa apenas módulos padrão)

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
- `RETIN` → Tipo (RET = Retinografia, OCT = OCT)
- `AO` → Olho (ignorado)
- `1739989244` → Timestamp (ignorado)

---

## ⚙️ Critérios de Filtro

### 1. **Tipo de Exame**
- ✅ `RETIN` (Retinografia) → Cópia como `RET`
- ✅ `OCT` (Papila) → Cópia como `OCT`
- ❌ Outros tipos são ignorados

### 2. **Período de Data**
- ✅ De `01/01/2020` a `30/06/2026`
- ❌ Fora deste período = descartado

### 3. **Critério de 4 Meses**
Para **cada tipo de exame independentemente** (RET e OCT separados):

1. Encontra o exame **mais recente**
2. Calcula a data limite: `data_mais_recente - 120 dias`
3. Copia todos os exames que atendem à condição: `data_exame >= data_limite`

**Exemplo:**
- OCT mais recente: `19/02/2025`
- Limite de 4 meses: `19/10/2024`
- Copia: OCT de 19/10/2024 até 19/02/2025
- Ignora: OCT anterior a 19/10/2024

---

## 🐛 Troubleshooting

### "Arquivo de prontuários não encontrado"
- Verifique se `pronunciarios.txt` está no mesmo diretório do script
- Ou forneça o caminho completo no script

### "Pasta não encontrada"
- A estrutura de diretórios está correta?
- O prontuário existe em `DIR_EXAMES_ORIGEM`?

### Nenhum arquivo foi copiado
- Verifique se os nomes dos arquivos seguem o padrão esperado
- Verifique se os tipos são `RETIN` ou `OCT`
- Confirme se as datas estão no período permitido

### Permissão negada
- Verifique se tem permissão de leitura em `DIR_EXAMES_ORIGEM`
- Verifique se tem permissão de escrita em `DIR_EXAMES_DESTINO`

---

## 💡 Dicas

1. **Teste com poucos prontuários** antes de processar muitos
2. **Ative verbose=True** (padrão) para ver o que está acontecendo
3. **Guarde o relatório final** para auditoria
4. **Faça backup** dos dados originais antes de usar

---

## 📞 Suporte

Se encontrar problemas, verifique:
- ✅ Arquivo `pronunciarios.txt` existe?
- ✅ Diretórios de origem/destino existem?
- ✅ Formato do nome do arquivo está correto?
- ✅ Tem permissões suficientes?
