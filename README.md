# Atualização de Precatórios – App Streamlit

Versão web do `PREC-EXTRA-2018-2020.py`. A entrada de dados é feita em um formulário
(`st.form`), os índices vêm de planilhas públicas do Google Sheets e o resultado é
baixado em Excel (.xlsx) e em CSV no mesmo formato do `RELATORIO-FINAL-UNIFICADO.csv`.

## Estrutura

```
app.py            # interface Streamlit (formulário, tela de resultado, downloads)
calculos.py       # motor de cálculo (mesma lógica do script original)
fontes.py         # leitura das bases: Google Sheets ou CSV local (fallback)
relatorio.py      # geração do Excel e do CSV
config.py         # links das planilhas do Google Sheets
dados/            # CSVs locais usados quando um link não está configurado
requirements.txt
.streamlit/
```

## 1. Preparar as planilhas no Google Sheets

1. Crie uma planilha (ex.: "BASES-PRECATORIO") com 5 abas: `IPCA15`, `POUPANCA`, `SELIC`, `IPCA`, `GRACA`.
2. Em cada aba: **Arquivo > Importar > Upload** do CSV correspondente da pasta `dados/`,
   escolhendo *Substituir planilha atual* e separador **ponto e vírgula**.
3. **Importante – casas decimais:** o Google exporta o valor *como ele aparece na tela*.
   Selecione a coluna `n_indice` e use **Formatar > Número > Texto simples** (ou aumente as
   casas decimais) para não perder precisão. Mesma coisa nas colunas de data: mantenha `dd/mm/aaaa`.
4. Compartilhe: **Compartilhar > Acesso geral > Qualquer pessoa com o link – Leitor**.
5. Para cada aba, clique nela e copie o link da barra do navegador (termina em `#gid=NUMERO`).

Para atualizar os índices todo mês basta acrescentar a linha nova na planilha; o app relê a cada
1 hora (ou na hora, pelo botão **Recarregar índices** na barra lateral).

## 2. Configurar os links

Escolha **uma** das opções:

- **config.py** (mais simples, os links ficam no repositório – as planilhas já são públicas):
  cole cada link em `PLANILHAS`.
- **Secrets do Streamlit Cloud** (não ficam no GitHub): copie o conteúdo de
  `.streamlit/secrets.toml.exemplo` para *App > Settings > Secrets*.

Link vazio = o app usa o CSV de `dados/`.

## 3. Subir para o GitHub

```bash
git init
git add .
git commit -m "App Streamlit de atualização de precatórios"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/precatorio-app.git
git push -u origin main
```

(Ou crie o repositório no site do GitHub e use *Add file > Upload files*, mantendo as pastas.)

> Repositório privado funciona no Streamlit Community Cloud, desde que você autorize o acesso.

## 4. Publicar no Streamlit Community Cloud

1. Acesse https://share.streamlit.io e clique em **Create app > Deploy a public app from GitHub**.
2. Repository: `SEU_USUARIO/precatorio-app` · Branch: `main` · Main file path: `app.py`.
3. (Opcional) Em *Advanced settings*, escolha Python 3.11 ou 3.12 e cole os Secrets.
4. **Deploy**. A cada `git push` o app é atualizado automaticamente.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Diferenças em relação ao script local

- `PAGAMENTOS-EFETUADOS.csv` foi substituído pelo formulário: ano da proposta, data final,
  principal, juros e a tabela de pagamentos (data + valor). A ordem é numerada pela data.
- Validações: valores em branco, pagamento antes da data-base ou depois da data final.
- Aviso quando a data final passa do último índice disponível (o cálculo usa o último valor
  existente, igual ao script original).
- O Excel tem uma aba `Relatorio` (valores numéricos com formato R$, linha FINAL em destaque,
  parâmetros no topo) e uma aba `Entrada` com os pagamentos digitados.
- A lógica de cálculo não mudou: com os mesmos dados o CSV gerado é idêntico ao atual.
