# Uso do painel

- **Visão geral:** última medição recebida, ponto de orvalho estimado, pressão
  absoluta, sequência e tempo desde o último recebimento. Os cartões mostram
  sempre a última leitura da estação; os filtros afetam gráficos, tabela e CSV.
- **Histórico:** últimas 24 horas, 7/30/365 dias, dia específico, meses de um ano
  ou estações meteorológicas do hemisfério sul. Verão do ano escolhido começa
  em dezembro do ano anterior. Datas na tela usam Brasília (UTC−3); dia é
  06h–18h e noite é 18h–06h. O filtro de meses seleciona registros cronológicos.
- **Gráficos:** acima de 600 registros, apresentam médias por intervalo para
  reduzir o tamanho da resposta. A legenda informa o agrupamento, e o tooltip
  mostra quantas amostras formam o ponto. Falhas prolongadas interrompem a linha.
- **CSV:** exporta todos os registros originais do filtro, sem o agrupamento do
  gráfico ou o limite das 100 linhas da tabela. Usa UTF-8 com BOM, separador
  ponto e vírgula, vírgula decimal e horário UTC identificado no cabeçalho.
- **Estações e sensores:** lista os dispositivos efetivamente presentes no banco.
  Identificadores iniciados por `teste` ou `diagnostico` ficam ocultos por padrão;
  use a opção de mostrar diagnósticos para consultá-los. Não são apagados.
  O total considera todo o histórico, desde a primeira leitura indicada na tabela.
- **Configurações:** nome local, limites de atenção, atualização da tela e intervalo
  esperado de coleta (30/60 s). Salvos neste navegador. Não alteram o Arduino,
  o ESP32, a rede Wi-Fi nem o intervalo real de aquisição.
- **Acesso:** se `ESTACAO_API_TOKEN` estiver preenchido, informe o mesmo token em
  Configurações → Configurar acesso. É mantido apenas na sessão do navegador e
  enviado no cabeçalho Authorization; nunca na URL do CSV.

O estado indica ausência de leituras após três intervalos esperados. Ele se
baseia no recebimento no servidor, sem medir bateria, RSSI ou funcionamento
elétrico dos sensores. Os avisos comparam a última leitura com limites locais;
não fazem previsão meteorológica nem enviam notificações externas.

O número no sino conta condições ainda não visualizadas da estação selecionada.
Abrir Alertas marca as condições atuais como vistas neste navegador, inclusive
após recarregar a página. O cartão da visão geral continua contando condições
ativas. Se a condição normalizar e voltar a ocorrer, será um novo aviso.

Pressão fora de 300–1100 hPa gera aviso para verificar o BMP280; o valor recebido
é preservado. Não há correção ao nível do mar sem altitude configurada. Campos
BMP nulos aparecem como indisponíveis. O ponto de orvalho é estimado pela
aproximação de Magnus para temperatura de −40 a 60 °C e umidade maior que zero.

Referências: [faixa do BMP280 (Bosch)](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp280-ds001.pdf),
[aproximação de Magnus (NOAA)](https://www.ncei.noaa.gov/sites/default/files/2026-01/TMY%20Tech%20User%20Guide%20-%201.29.26.pdf).

### Rotas de consulta

`GET /api/estacoes` lista dispositivos e contagens. `GET /api/painel` retorna
última leitura, resumo, série e até 100 registros. `GET /api/exportar.csv`
exporta os registros originais. As duas últimas exigem `dispositivo` e aceitam
`inicio`/`fim` ISO 8601 com fuso, `turno=todos|dia|noite` e `meses=1,2,...`.
O intervalo inclui início, exclui fim e tem no máximo 366 dias. Sem datas,
consulta as últimas 24 horas. Todas respeitam o token opcional da API existente.

