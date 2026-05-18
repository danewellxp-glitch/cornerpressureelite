# -*- coding: utf-8 -*-
"""Coletor custom Netdata para métricas CPES (Fase H + sinais + sources)."""

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from bases.FrameworkServices.SimpleService import SimpleService

ORDER = [
    'dual_write',
    'signals',
    'sources_odds',
    'sources_stats',
    'blocked_reasons',
    'af',
]

CHARTS = {
    'dual_write': {
        'options': [None, 'Cobertura Dual-Write Fase H A1 (24h)', 'percent',
                    'fase_h', 'cpes.dual_write', 'line'],
        'lines': [
            ['events_pct', 'events', 'absolute'],
            ['odds_pct', 'odds', 'absolute'],
            ['stats_pct', 'stats', 'absolute'],
            ['lineups_pct', 'lineups', 'absolute'],
        ],
    },
    'signals': {
        'options': [None, 'Sinais Emitidos vs Bloqueados (24h)', 'count',
                    'sinais', 'cpes.signals', 'stacked'],
        'lines': [
            ['emitted', 'emitidos', 'absolute'],
            ['blocked', 'bloqueados', 'absolute'],
        ],
    },
    'sources_odds': {
        'options': [None, 'Distribuicao Fontes Odds (24h)', 'count',
                    'fontes', 'cpes.sources_odds', 'stacked'],
        'lines': [
            ['odds_betano_bridge', 'betano_bridge', 'absolute'],
            ['odds_betano_cache', 'betano_cache', 'absolute'],
            ['odds_betano_cache_stale', 'betano_cache_stale', 'absolute'],
            ['odds_apifootball', 'apifootball', 'absolute'],
        ],
    },
    'sources_stats': {
        'options': [None, 'Distribuicao Fontes Stats (24h)', 'count',
                    'fontes', 'cpes.sources_stats', 'stacked'],
        'lines': [
            ['stats_bridge_betano', 'bridge_betano', 'absolute'],
            ['stats_sofascore', 'sofascore', 'absolute'],
            ['stats_apifootball', 'apifootball', 'absolute'],
        ],
    },
    'blocked_reasons': {
        'options': [None, 'Sinais Bloqueados por Razao (24h)', 'count',
                    'sinais', 'cpes.blocked_reasons', 'stacked'],
        'lines': [
            ['br_odd_moved_too_much', 'odd_moved', 'absolute'],
            ['br_line_disappeared', 'line_disappeared', 'absolute'],
            ['br_refetch_none', 'refetch_none', 'absolute'],
            ['br_refetch_stale', 'refetch_stale', 'absolute'],
            ['br_refetch_exception', 'refetch_exception', 'absolute'],
        ],
    },
    'af': {
        'options': [None, 'AF Runtime Usage Proxy (24h)', 'count',
                    'af_usage', 'cpes.af', 'line'],
        'lines': [
            ['af_odds', 'odds', 'absolute'],
            ['af_stats', 'stats', 'absolute'],
            ['af_events', 'events', 'absolute'],
        ],
    },
}

DUAL_WRITE_TABLES = [
    ('events_pct', 'events_history'),
    ('odds_pct', 'odds_history'),
    ('stats_pct', 'stats_history'),
    ('lineups_pct', 'lineups_history'),
]


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = ORDER
        self.definitions = CHARTS
        self.dsn = configuration.get('dsn', '')

    def check(self):
        if not HAS_PSYCOPG2:
            self.error("psycopg2 nao instalada (pip install psycopg2-binary)")
            return False
        try:
            conn = psycopg2.connect(self.dsn, connect_timeout=5)
            conn.close()
        except Exception as e:
            self.error("Erro conexao DB: {0}".format(e))
            return False
        return True

    def _connect(self):
        return psycopg2.connect(self.dsn, connect_timeout=5)

    def get_data(self):
        data = {}
        try:
            conn = self._connect()
            cur = conn.cursor()

            # 1. Dual-write coverage (4 tabelas)
            for key, table in DUAL_WRITE_TABLES:
                cur.execute(
                    "SELECT COALESCE(ROUND(100.0 * "
                    "COUNT(*) FILTER (WHERE sofa_event_id IS NOT NULL) / "
                    "NULLIF(COUNT(*), 0), 0), 0)::int "
                    "FROM {0} WHERE captured_at > NOW() - INTERVAL '24 hours';".format(table)
                )
                row = cur.fetchone()
                data[key] = int(row[0]) if row and row[0] is not None else 0

            # 2. Sinais emitidos (coluna real: 'timestamp', NAO created_at)
            cur.execute(
                "SELECT COUNT(*) FROM sinais "
                "WHERE timestamp > NOW() - INTERVAL '24 hours';"
            )
            data['emitted'] = int(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT COUNT(*) FROM blocked_signals "
                "WHERE blocked_at > NOW() - INTERVAL '24 hours';"
            )
            data['blocked'] = int(cur.fetchone()[0] or 0)

            # 3. Distribuicao fontes odds
            cur.execute(
                "SELECT source, COUNT(*) FROM odds_history "
                "WHERE captured_at > NOW() - INTERVAL '24 hours' GROUP BY source;"
            )
            odds_sources = dict(cur.fetchall())
            data['odds_betano_bridge'] = int(odds_sources.get('betano_bridge', 0))
            data['odds_betano_cache'] = int(odds_sources.get('betano_cache', 0))
            data['odds_betano_cache_stale'] = int(odds_sources.get('betano_cache_stale', 0))
            data['odds_apifootball'] = int(odds_sources.get('apifootball', 0))

            # 4. Distribuicao fontes stats (note: 'bridge_betano' invertido vs odds)
            cur.execute(
                "SELECT source, COUNT(*) FROM stats_history "
                "WHERE captured_at > NOW() - INTERVAL '24 hours' GROUP BY source;"
            )
            stats_sources = dict(cur.fetchall())
            data['stats_bridge_betano'] = int(stats_sources.get('bridge_betano', 0))
            data['stats_sofascore'] = int(stats_sources.get('sofascore', 0))
            data['stats_apifootball'] = int(stats_sources.get('apifootball', 0))

            # 5. Bloqueios por razao
            cur.execute(
                "SELECT reason, COUNT(*) FROM blocked_signals "
                "WHERE blocked_at > NOW() - INTERVAL '24 hours' GROUP BY reason;"
            )
            reasons = dict(cur.fetchall())
            data['br_odd_moved_too_much'] = int(reasons.get('odd_moved_too_much', 0))
            data['br_line_disappeared'] = int(reasons.get('line_disappeared', 0))
            data['br_refetch_none'] = int(reasons.get('refetch_none', 0))
            data['br_refetch_stale'] = int(reasons.get('refetch_stale', 0))
            data['br_refetch_exception'] = int(reasons.get('refetch_exception', 0))

            # 6. AF usage (proxy: linhas com source='apifootball' 24h)
            cur.execute(
                "SELECT COUNT(*) FROM odds_history "
                "WHERE source='apifootball' AND captured_at > NOW() - INTERVAL '24 hours';"
            )
            data['af_odds'] = int(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT COUNT(*) FROM stats_history "
                "WHERE source='apifootball' AND captured_at > NOW() - INTERVAL '24 hours';"
            )
            data['af_stats'] = int(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT COUNT(*) FROM events_history "
                "WHERE source='apifootball' AND captured_at > NOW() - INTERVAL '24 hours';"
            )
            data['af_events'] = int(cur.fetchone()[0] or 0)

            cur.close()
            conn.close()

        except Exception as e:
            self.error("Erro coleta: {0}".format(e))
            return None

        return data
