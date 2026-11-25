# ORB bot: paper trading com Opening Range Breakout

Bot em Python que opera, **apenas em simulação**, a estratégia de rompimento da faixa de abertura em
ações dos EUA, com backtest, controle de risco e journal diário.

> Projeto educacional. **Não é recomendação de investimento**, a estratégia não demonstrou vantagem
> e não deve ser usada com dinheiro real.

## Requisitos

- Python 3.11+ e [uv](https://docs.astral.sh/uv/)
- Nenhuma conta ou chave para o modo simulado (dados do Yahoo Finance, fonte não oficial)

## Instalação

```bash
cd bot
uv sync
uv run pytest
```

## Configuração (opcional)

Sem arquivo de configuração o bot usa os padrões. Para ajustar, a partir da raiz do repositório:

```bash
mkdir -p config && cp bot/.env.example config/.env
```

| Variável | Padrão | Função |
|---|---|---|
| `BROKER` | `sim` | `sim` (corretora local) ou `alpaca` (conta paper; adaptador não testado contra a API real) |
| `SIM_STARTING_CASH` | `10000` | saldo fictício |
| `WATCHLIST` | 10 ativos líquidos | símbolos separados por vírgula |
| `BOT_ENABLED` | `true` | `false` impede novas entradas |
| `NOTIFICATIONS_ENABLED` | `true` | notificações no macOS |
| `SEC_USER_AGENT` | vazio | `Nome email@exemplo.com`; liga os comunicados 8-K no journal (exigência da SEC) |

Nunca faça commit do arquivo `.env`.

## Uso

Dentro de `bot/`:

```bash
uv run orb-bot status      # saldo, posições e se há pregão
uv run orb-bot backtest    # replay recente, com custos e benchmark aleatório
uv run orb-bot run-day     # dia completo: entradas, encerramento e journal
```

Também há `session`, `flatten` e `journal` para rodar cada etapa. Relatórios saem em `backtests/` e
os journals em `logs/`, na raiz do repositório.

## Regras

| Horário de Nova York | Ação |
|---|---|
| 9:30–9:45 | monta a faixa de abertura |
| 9:45–11:00 | compra no 1º candle de 5 min que fecha acima da faixa, com volume e gap filtrados; stop na mínima, alvo em 2R |
| fechamento − 5 min | encerra as posições |

Risco: 2% por trade, posição de até 25% da conta, até 3 trades por dia, limites de perda diária (6%) e
semanal (10%). Os parâmetros estão em `bot/src/orb_bot/config/constants.py`.

Para interromper novas entradas, crie o arquivo `bot/KILL`.

## Agendamento (macOS, opcional)

```bash
cd bot
ORB_BOT_START_HOUR=10 ./launchd/install.sh   # hora local, antes da abertura de Nova York
```

O computador precisa ficar **acordado, conectado à rede e à energia até o fechamento**. Se ele dormir,
as posições não são encerradas no horário. Para uso contínuo, prefira um servidor.

## Arquitetura

```
bot/src/orb_bot/
  domain/    estratégia, risco, simulador e interfaces (sem I/O)
  services/  sessão, encerramento, journal e backtest
  infra/     corretoras, dados de mercado, notícias e estado em disco
  config/    parâmetros, variáveis de ambiente e calendários
```

## Limitações

- Há cerca de 60 dias de candles de 5 minutos no Yahoo: amostra pequena para conclusões.
- A simulação aplica slippage fixo e, para posições encerradas com atraso, não reflete o salto de preço
  da noite.
- Calendários de feriados e eventos precisam ser atualizados (`config/`).
