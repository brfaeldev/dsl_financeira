# Guia Completo e Passo a Passo da DSL Financeira

Este manual mostra **tudo o que a DSL Financeira aceita**, as regras de preenchimento de cada bloco, como rodar seus cenários e modelos prontos para copiar e adaptar.

---

## 1. Passo a Passo: Como Criar e Rodar Seu Próprio Cenário

### Passo 1: Criar o arquivo `.dsl`
Crie um arquivo com extensão `.dsl` dentro da pasta `exemplos/` (por exemplo, `exemplos/minha_carteira.dsl`).
- **Comentários**: Qualquer linha (ou trecho após um comando) iniciada com `#` é ignorada pelo interpretador.
- **Números decimais**: Use sempre **ponto** (`.`) para separar centavos ou casas decimais (ex.: `5000.00`, `0.85`, `10.75`). Também é permitido usar números inteiros (ex.: `5000`, `12`).
- **Nomes (Identificadores)**: Todo nome de índice ou investimento deve estar entre **aspas duplas** (ex.: `"Meu CDB"`, `"Tesouro_IPCA"`).

### Passo 2: Escolher a Ordem do Arquivo
Um arquivo `.dsl` segue naturalmente esta estrutura de cima para baixo:
1. **(Opcional)** Declaração dos **Indexadores** (`INDICE ...`) que você pretende usar;
2. Declaração de um ou mais blocos de **Investimento** (`INVESTIMENTO "..." ... FIM`);
3. **Comandos de Saída e Simulação** (`IMPRIMIR`, `GERAR`, `COMPARAR`, `EXPORTAR`, `SIMULAR`).

> **Regra importante (*Declare-Before-Use*)**: Você sempre deve declarar um `INDICE` ou `INVESTIMENTO` **antes** de usá-lo em um comando abaixo.

### Passo 3: Executar no Terminal
Abra o terminal na pasta raiz do projeto (`c:\Users\bruno\Desktop\dsl_financeira`) e execute:

```powershell
# Executar um arquivo .dsl:
python main.py exemplos/minha_carteira.dsl

# (Opcional) Escolher outra pasta para salvar os gráficos e relatórios:
python main.py exemplos/minha_carteira.dsl -o meus_resultados

# Ou abrir o modo interativo (REPL) para digitar linha por linha no terminal:
python main.py --repl

# Ou abrir a interface visual (Playground Web em Streamlit) no navegador:
pip install streamlit
streamlit run app.py
```

---

## 2. Catálogo Completo de Tudo o Que a Linguagem Aceita

### 2.1. Declaração de Indexadores Globais (`INDICE`)
Serve para cadastrar taxas macroeconômicas (como `CDI`, `SELIC`, `IPCA`, `IGPM`) que serão referenciadas pelos seus investimentos.

| Sintaxe Aceita | Exemplo Prático | O que faz |
| :--- | :--- | :--- |
| `INDICE "<Nome>" <numero> PORCENTO AO_ANO` | `INDICE "CDI" 10.75 PORCENTO AO_ANO` | Registra um índice anual (convertido automaticamente para taxa mensal equivalente de juros compostos). |
| `INDICE "<Nome>" <numero> PORCENTO AO_MES` | `INDICE "TR" 0.08 PORCENTO AO_MES` | Registra um índice já em base mensal. |

---

### 2.2. Bloco de Investimento (`INVESTIMENTO "..." ... FIM`)
Todo investimento começa com `INVESTIMENTO "<Nome>"` e termina com `FIM`:

```text
INVESTIMENTO "Nome_do_Investimento"
    # Parâmetros aqui dentro
FIM
```

Abaixo estão **todos os parâmetros** aceitos dentro do bloco `INVESTIMENTO`:

#### A. Capital e Prazo (Obrigatórios)
Todo investimento **precisa** ter pelo menos uma fonte de capital (`VALOR_INICIAL` e/ou `APORTE`) e um prazo definido (`PERIODO` ou `APORTE ... POR ...`):

| Parâmetro | Sintaxes Aceitas | Exemplos | Regra de Uso |
| :--- | :--- | :--- | :--- |
| **Capital Inicial** | `VALOR_INICIAL <numero>` | `VALOR_INICIAL 10000.00` | Aplicado no mês `0`. Pode ser omitido se houver `APORTE`. |
| **Aporte Mensal + Prazo** | `APORTE <numero> POR <inteiro> MESES`<br>`APORTE <numero> POR <inteiro> ANOS` | `APORTE 500.00 POR 24 MESES`<br>`APORTE 500.00 POR 2 ANOS` | Define o aporte mensal recorrente **e** já define o prazo total da simulação. |
| **Apenas Prazo (sem aporte mensal)** | `PERIODO <inteiro> MESES`<br>`PERIODO <inteiro> ANOS` | `PERIODO 18 MESES`<br>`PERIODO 3 ANOS` | Usado quando você só tem `VALOR_INICIAL` e **não** fará aportes mensais fixos. |

> **Atenção**: Não coloque `APORTE ... POR ...` e `PERIODO ...` juntos no mesmo investimento, pois ambos definem o prazo total e o analisador semântico apontará conflito.

#### B. Eventos Dinâmicos de Fluxo de Caixa (Opcionais — podem repetir várias vezes)
Permitem simular aportes extras (ex.: 13º salário, PLR, bônus) e retiradas parciais em meses específicos:

| Parâmetro | Sintaxe Aceita | Exemplo | Regra de Uso |
| :--- | :--- | :--- | :--- |
| **Aporte Extra** | `APORTE_EXTRA <numero> NO_MES <inteiro>` | `APORTE_EXTRA 3000.00 NO_MES 12` | O mês deve estar entre `1` e o prazo final em meses. Pode declarar vários no mesmo bloco. |
| **Resgate Parcial** | `RESGATE <numero> NO_MES <inteiro>` | `RESGATE 1500.00 NO_MES 18` | Retira o valor do saldo naquele mês (calculando o IR proporcional via FIFO). O valor não pode exceder o saldo acumulado no mês. |

#### C. Taxa de Rentabilidade (Opcional — escolha apenas 1 formato por investimento)
Se omitida, a taxa padrão é `0%`. Você pode declarar a rentabilidade de **4 formas**:

| Modalidade | Sintaxes Aceitas | Exemplos |
| :--- | :--- | :--- |
| **1. Prefixada Mensal** | `TAXA <numero> PORCENTO AO_MES` | `TAXA 0.85 PORCENTO AO_MES` |
| **2. Prefixada Anual** | `TAXA <numero> PORCENTO AO_ANO` | `TAXA 12.50 PORCENTO AO_ANO` |
| **3. Pós-Fixada (% de Índice)** | `TAXA <numero> PORCENTO DO "<Indice>"` | `TAXA 110.0 PORCENTO DO "CDI"` |
| **4. Híbrida (Índice + Taxa Fixa)** | `TAXA "<Indice>" + <numero> PORCENTO AO_ANO`<br>`TAXA "<Indice>" + <numero> PORCENTO AO_MES`<br>`TAXA <numero> PORCENTO AO_ANO + "<Indice>"` | `TAXA "IPCA" + 6.0 PORCENTO AO_ANO` |

#### D. Inflação e Custos Operacionais (Opcionais)

| Parâmetro | Sintaxes Aceitas | Exemplos | O que faz |
| :--- | :--- | :--- | :--- |
| **Inflação** | `INFLACAO <numero> PORCENTO AO_MES`<br>`INFLACAO <numero> PORCENTO AO_ANO`<br>`INFLACAO "<Indice>"` | `INFLACAO 0.38 PORCENTO AO_MES`<br>`INFLACAO 4.50 PORCENTO AO_ANO`<br>`INFLACAO "IPCA"` | Calcula o **Valor Líquido Real (Poder de Compra)** descontando a inflação acumulada (Equação de Fisher). |
| **Taxa de Administração / Custódia** | `TAXA_ADMINISTRACAO <numero> PORCENTO AO_ANO`<br>`TAXA_ADMINISTRACAO <numero> PORCENTO AO_MES` | `TAXA_ADMINISTRACAO 0.50 PORCENTO AO_ANO` | Desconta mensalmente a taxa de administração (fundos) ou custódia (B3) sobre o patrimônio. |

#### E. Regime de Imposto de Renda (Opcional — escolha apenas 1 formato por investimento)
Se omitido, o investimento é considerado isento (`0%`).

| Modalidade Tributária | Sintaxe Aceita | Exemplo / Comportamento |
| :--- | :--- | :--- |
| **1. Alíquota Fixa ou Isento** | `IMPOSTO <numero> PORCENTO` | `IMPOSTO 15.0 PORCENTO` ou `IMPOSTO 0.0 PORCENTO` (para LCI/LCA/CRI/CRA/Debênture Incentivada). |
| **2. Tabela Regressiva Global** | `IMPOSTO REGRESSIVO` | Aplica a tabela oficial de Renda Fixa conforme o prazo total: `22,5%` (até 6m), `20%` (7 a 12m), `17,5%` (13 a 24m) e `15%` (acima de 24m). |
| **3. Tabela Regressiva por Safra** | `IMPOSTO REGRESSIVO POR_SAFRA` | Calcula o IR individualmente para cada aporte mensal segundo o tempo que **aquele aporte** ficou investido ($n - k$ meses). |
| **4. Come-Cotas (Fundos)** | `IMPOSTO COME_COTAS` | Antecipa o IR a cada 6 meses (`15%` para fundos de longo prazo $>12\text{m}$ ou `20%` para curto prazo $\le 12\text{m}$) reduzindo o saldo semestralmente. |

---

### 2.3. Comandos de Saída, Simulação e Exportação
Colocados fora dos blocos `INVESTIMENTO`:

| Comando | Sintaxe Aceita | Exemplo | O que gera |
| :--- | :--- | :--- | :--- |
| **Resumo no Terminal** | `IMPRIMIR RESUMO "<Inv>"` | `IMPRIMIR RESUMO "Meu_CDB"` | Imprime no terminal Total Investido, Rendimento Bruto, IR, Valor Final Líquido (e Valor Real / Resgates, se houver). |
| **Simular Aposentadoria / Renda Passiva** | `SIMULAR RENDA "<Inv>" RETIRADA <numero> AO_MES`<br>`SIMULAR RENDA "<Inv>" RETIRADA <numero> AO_ANO` | `SIMULAR RENDA "Carteira" RETIRADA 4000.00 AO_MES` | Mostra qual a retirada máxima perpétua e por quantos meses/anos o patrimônio acumulado aguenta a retirada desejada. |
| **Gráfico Estático PNG** | `GERAR GRAFICO "<Inv1>" ["<Inv2>" ...]` | `GERAR GRAFICO "Meu_CDB"` | Salva `output/grafico_Meu_CDB.png` com as curvas Bruta, Líquida, Líquida Real e Total Investido. |
| **Gráfico Comparativo PNG** | `COMPARAR GRAFICO "<Inv1>" "<Inv2>" [...]` | `COMPARAR GRAFICO "CDB" "LCI" "Tesouro"` | Salva um único `.png` comparando lado a lado todos os investimentos listados. |
| **Gráfico Interativo HTML** | `GERAR GRAFICO_INTERATIVO "<Inv1>" ["<Inv2>" ...]` | `GERAR GRAFICO_INTERATIVO "CDB" "LCI"` | Salva um arquivo `.html` interativo (Plotly) em `output/` para abrir no navegador e inspecionar mês a mês com o mouse. |
| **Exportar Planilha CSV** | `EXPORTAR CSV "<Inv1>" ["<Inv2>" ...]` | `EXPORTAR CSV "Meu_CDB"` | Salva `output/evolucao_Meu_CDB.csv` com a evolução mês a mês (`0..n`) pronta para abrir no Excel. |
| **Exportar JSON** | `EXPORTAR JSON "<Inv1>" ["<Inv2>" ...]` | `EXPORTAR JSON "CDB" "LCI"` | Salva arquivo `.json` estruturado com parâmetros, resumo e série temporal mensal. |
| **Relatório Consolidado Markdown** | `GERAR RELATORIO "<arquivo.md>" ["<Inv1>" ...]` | `GERAR RELATORIO "relatorio.md"` | Gera `output/relatorio.md` com tabela comparativa de todos os investimentos, destaque do vencedor e lista de gráficos. |

---

## 3. O Que Não Fazer (Regras Validadas pela Análise Semântica)

Se algum desses erros ocorrer, o interpretador mostrará `[Erro Semantico] (Linha X, Coluna Y)` explicando o motivo:
1. **Não declarar prazo ou capital**: Todo bloco `INVESTIMENTO` precisa ter prazo (`PERIODO` ou `APORTE ... POR ...`) e capital positivo (`VALOR_INICIAL` ou `APORTE`).
2. **Conflito entre `APORTE` e `PERIODO`**: Se o investimento tem aportes mensais, use apenas `APORTE 500.00 POR 12 MESES` (não adicione `PERIODO 12 MESES` embaixo).
3. **Conflito de `IMPOSTO` ou `TAXA`**: Declare apenas uma linha de `TAXA` e no máximo uma linha de `IMPOSTO` por bloco.
4. **Valores negativos ou fora de faixa**: Taxas, aportes e valores iniciais não podem ser negativos; alíquotas de imposto devem estar entre `0` e `100`; prazos devem ser maiores que zero.
5. **Evento fora do prazo ou resgate maior que o saldo**: Em `APORTE_EXTRA ... NO_MES X` ou `RESGATE ... NO_MES X`, o mês `X` deve estar entre `1` e o total de meses do investimento, e o valor do resgate não pode superar o saldo acumulado naquele mês.

---

## 4. Exemplo Completo Passo a Passo

Você pode rodar o arquivo de referência completo criado junto com este guia:

```powershell
python main.py exemplos/referencia_completa.dsl
```
