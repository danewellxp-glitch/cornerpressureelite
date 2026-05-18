# Netdata Setup CPES (odin)

Monitoramento contínuo Postgres + Docker containers + métricas custom Fase H, sinais e fontes de odds. Instalado em 2026-05-18 no `odin` (192.168.1.18).

## Acesso

Netdata binda **localhost only** por segurança. Acesso via SSH tunnel do PC:

```bash
# No PC do Daniel:
ssh -L 19999:localhost:19999 daniel@odin -N &
# Abrir: http://localhost:19999
```

## Componentes

| Componente | Função |
|---|---|
| `netdata` v2.10.3 (binpkg-deb) | Agente principal |
| go.d/postgres | Auto-discovery Postgres (charts `postgres_cpes_postgres.*`) |
| cgroups | Auto-discovery Docker containers (`cgroup_cpes-*`) |
| python.d/cpes_metrics | Collector custom SQL — 6 charts CPES |
| health.d/cpes_custom | 5 alertas custom |

## Charts custom

| Chart ID | Conteúdo |
|---|---|
| `cpes_metrics.dual_write` | Cobertura dual-write Fase H A1 (events/odds/stats/lineups, %) |
| `cpes_metrics.signals` | Sinais emitidos vs bloqueados 24h |
| `cpes_metrics.sources_odds` | Distribuição fontes odds (betano_bridge / cache / cache_stale / apifootball) |
| `cpes_metrics.sources_stats` | Distribuição fontes stats (bridge_betano / sofascore / apifootball) |
| `cpes_metrics.blocked_reasons` | Bloqueios P5 por razão |
| `cpes_metrics.af` | AF runtime usage (proxy via `source='apifootball'`) |

## Alertas

| Alerta | Threshold |
|---|---|
| `cpes_dual_write_events` | WARN < 85%, CRIT < 70% |
| `cpes_dual_write_odds` | WARN < 85%, CRIT < 70% |
| `cpes_dual_write_stats` | WARN < 75%, CRIT < 50% |
| `cpes_af_odds_usage_high` | WARN > 50, CRIT > 100 (24h aggregate) |
| `cpes_signals_too_blocked` | WARN > 30%, CRIT > 60% (% bloqueados) |

## Postgres conexão

cpes-postgres **não está exposto em host port**. Netdata conecta via IP da rede Docker `cornerpressureelite_cpes-network` (estável desde criação do container):

```
postgres://netdata:<PWD>@172.18.0.2:5432/cpes
```

Se a rede Docker for recriada o IP pode mudar. Verificar com:
```bash
docker inspect cpes-postgres | grep IPAddress
```

E atualizar `/etc/netdata/go.d/postgres.conf` e `/etc/netdata/python.d/cpes_metrics.conf`.

## Usuário Postgres read-only

```sql
CREATE USER netdata WITH PASSWORD 'netdata_readonly_2026';
GRANT pg_monitor TO netdata;
GRANT CONNECT ON DATABASE cpes TO netdata;
GRANT USAGE ON SCHEMA public TO netdata;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO netdata;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO netdata;
```

## Telegram (pendente)

Configurar quando Daniel criar bot:

1. `/msg @BotFather` → criar bot → obter **TOKEN**
2. `/msg @userinfobot` → obter **CHAT_ID**
3. Editar `/etc/netdata/health_alarm_notify.conf`:
   ```
   SEND_TELEGRAM="YES"
   TELEGRAM_BOT_TOKEN="<TOKEN>"
   DEFAULT_RECIPIENT_TELEGRAM="<CHAT_ID>"
   ```
4. `sudo systemctl reload netdata` (ou `netdatacli reload-health`)
5. Testar: `/usr/libexec/netdata/plugins.d/alarm-notify.sh test sysadmin`

## Aplicar em ambiente novo

Configs versionados aqui são `.example`. Para deploy:

```bash
# 1. Criar usuário Postgres (ver SQL acima)
# 2. Instalar Netdata
bash <(curl -SsL https://my-netdata.io/kickstart.sh) --stable-channel --disable-telemetry --dont-wait
# 3. Instalar psycopg2 (sistema)
sudo apt install -y python3-psycopg2
# 4. Copiar configs (substituir <PWD> pela senha real)
sudo cp netdata.conf.example /etc/netdata/netdata.conf
sed 's|NETDATA_PG_PWD_PLACEHOLDER|<PWD>|g' postgres.conf.example \
    | sudo tee /etc/netdata/go.d/postgres.conf
sed 's|NETDATA_PG_PWD_PLACEHOLDER|<PWD>|g' cpes_metrics.conf.example \
    | sudo tee /etc/netdata/python.d/cpes_metrics.conf
sudo cp cpes_metrics.chart.py /usr/libexec/netdata/python.d/
sudo cp cpes_custom.conf.example /etc/netdata/health.d/cpes_custom.conf
# 5. Habilitar python.d/cpes_metrics
echo "cpes_metrics: yes" | sudo tee -a /etc/netdata/python.d.conf
# 6. Permissões + adicionar netdata ao grupo docker
sudo chown netdata:netdata /etc/netdata/go.d/postgres.conf \
    /etc/netdata/python.d/cpes_metrics.conf \
    /etc/netdata/health.d/cpes_custom.conf
sudo chmod 640 /etc/netdata/go.d/postgres.conf /etc/netdata/python.d/cpes_metrics.conf
sudo usermod -aG docker netdata
# 7. Restart
sudo systemctl restart netdata
```

## Validação

```bash
# Charts custom existem?
curl -s 'http://localhost:19999/api/v1/charts' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([k for k in d['charts'] if k.startswith('cpes_metrics.')])"

# Alertas custom carregaram?
curl -s 'http://localhost:19999/api/v1/alarms?all=true' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([k for k in d['alarms'] if 'cpes_dual_write' in k or 'cpes_af_odds' in k or 'cpes_signals_too' in k])"
```

## Pendências

- **Telegram bot** (acima)
- **AF alert semantics**: `cpes_af_odds_usage_high` usa agregado 24h como métrica "instantânea" → alerta dispara CRITICAL mesmo quando AF cai pra zero hoje (lookback ainda mostra valores 24h). Refactor: collector poderia exportar count das últimas 1h em vez de 24h.

## Rollback

```bash
sudo /usr/libexec/netdata/netdata-uninstaller.sh --yes
docker exec cpes-postgres psql -U cpes_user -d cpes -c "DROP USER netdata;"
```

## Gotchas conhecidos

1. **`cpes_metrics.` (não `cpes.`)** — quando job_key == module_name no python.d, o chart prefix vira `<module_name>.`, não o `name:` do conf. Alerts precisam usar chart ID real.
2. **`update_every` no JOB**, não no root do conf — apesar de `apply_defaults` mergear globais, o RuntimeCounters pop espera valor explícito por-job em algumas versões.
3. **`calc:` usa ternário** `(cond) ? (a) : (b)`, não `max()`/`min()`/funções Python.
4. **Dimensão ID ≠ display name** — `lines: [['emitted', 'emitidos', ...]]` → `$emitted` no calc, NÃO `$emitidos`.
5. **`requiretty` no sudoers** do odin — debug manual de python.d.plugin precisa `sudo -S` com password inline.
6. **`python3-psycopg2` apt** (não pip) — netdata usa `/usr/bin/python3` do sistema; pip user/venv não cobre.
7. **RAM 256-266MB** vs target 100MB — Netdata v2.10.3 adicionou `network-viewer.plugin`, `otel-signal-viewer-plugin`, `systemd-journal.plugin` que ignoram `[plugins]` disables legados. Pode ser reduzido futuramente.
