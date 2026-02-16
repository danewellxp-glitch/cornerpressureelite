"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Calendar, Clock, AlertCircle, Zap } from "lucide-react";
import { Card } from "@/components/ui/Card";

interface UpcomingGame {
  id: number;
  timestamp: number;
  hora_inicio: string;
  minutos_ate: number;
  home: string;
  away: string;
  liga: string;
  placar: string;
  status: string;
}

interface UpcomingGamesResponse {
  atualizado: string | null;
  proximos: UpcomingGame[];
}

/**
 * Próximos jogos programados com polling adaptativo.
 * Ajusta frequência de atualização baseado no tempo até o próximo jogo.
 */
export function UpcomingGames() {
  const [games, setGames] = useState<UpcomingGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [pollInterval, setPollInterval] = useState(600000); // 10 min default
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Calcular intervalo de polling adaptativo baseado no tempo até próximo jogo
  const calculatePollInterval = useCallback((games: UpcomingGame[]): number => {
    if (games.length === 0) return 1800000; // 30 min - sistema dormindo, sem jogos

    const nextGame = games[0];
    const minutesUntil = nextGame.minutos_ate;

    // Lógica adaptativa conservadora
    if (minutesUntil > 120) return 900000; // 15 min - jogos longe
    if (minutesUntil > 90) return 600000; // 10 min - economia
    if (minutesUntil > 30) return 120000; // 2 min - preparação
    if (minutesUntil > 0) return 30000; // 30 seg - pré-jogo
    return 10000; // 10 seg - durante jogo
  }, []);

  // Buscar próximos jogos
  const fetchUpcomingGames = useCallback(async () => {
    try {
      const response = await fetch("/api/cpes/upcoming-games");
      if (!response.ok) throw new Error("Failed to fetch");

      const data: UpcomingGamesResponse = await response.json();
      setGames(data.proximos || []);
      setLastUpdate(new Date());

      // Recalcular intervalo baseado nos novos dados
      const newInterval = calculatePollInterval(data.proximos || []);
      setPollInterval(newInterval);
    } catch (error) {
      console.error("Erro ao buscar próximos jogos:", error);
    } finally {
      setLoading(false);
    }
  }, [calculatePollInterval]);

  // Setup polling com intervalo adaptativo
  useEffect(() => {
    // Busca inicial
    fetchUpcomingGames();

    // Setup polling
    const setupPolling = () => {
      if (pollingRef.current) clearInterval(pollingRef.current);

      pollingRef.current = setInterval(() => {
        fetchUpcomingGames();
      }, pollInterval);
    };

    setupPolling();

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [pollInterval, fetchUpcomingGames]);

  // Formatar minutos até o jogo
  const formatTimeUntil = (minutes: number): string => {
    if (minutes < 0) return "Em andamento";
    if (minutes === 0) return "Começando agora!";
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  // Cor de status baseado no tempo
  const getStatusColor = (minutes: number): string => {
    if (minutes < 0) return "from-yellow-900/50 to-orange-900/50 border-orange-500/30";
    if (minutes < 30) return "from-red-900/50 to-red-900/50 border-red-500/30"; // Crítico
    if (minutes < 90) return "from-yellow-900/50 to-yellow-900/50 border-yellow-500/30"; // Preparação
    return "from-blue-900/50 to-blue-900/50 border-blue-500/30"; // Normal
  };

  const getTimeStyle = (minutes: number): string => {
    if (minutes < 30) return "text-red-400 font-bold";
    if (minutes < 90) return "text-yellow-400 font-semibold";
    return "text-cyan-400";
  };

  if (loading) {
    return (
      <Card className="p-6">
        <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-cyan-400">
          <Calendar className="h-5 w-5" />
          Próximos 3 jogos
        </h2>
        <div className="text-center py-8">
          <p className="text-gray-400 animate-pulse">Carregando agenda...</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xl font-semibold text-cyan-400">
          <Calendar className="h-5 w-5" />
          Próximos 3 jogos
        </h2>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Zap className="h-4 w-4" />
          <span>Polling: {Math.round(pollInterval / 1000)}s</span>
        </div>
      </div>

      {games.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-zinc-900/30 p-8 text-center">
          <p className="text-sm text-zinc-500">
            Sem jogos programados para as próximas horas.
          </p>
          <p className="mt-2 text-xs text-zinc-600">
            Sistema monitorando... próximos jogos aparecerão aqui.
          </p>
          {lastUpdate && (
            <p className="mt-3 text-xs text-gray-600">
              Verificado às {lastUpdate.toLocaleTimeString("pt-BR")}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {games.slice(0, 3).map((game, idx) => (
            <div
              key={game.id}
              className={`bg-gradient-to-r ${getStatusColor(game.minutos_ate)} border rounded-lg p-4 transition-all ${
                idx === 0 && game.minutos_ate < 30 ? "ring-2 ring-red-500/50" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-4">
                {/* Esquerda: Time da casa */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">
                    {game.home}
                  </p>
                </div>

                {/* Centro: Hora e placar */}
                <div className="flex flex-col items-center gap-1">
                  <p className={`text-sm ${getTimeStyle(game.minutos_ate)}`}>
                    {game.hora_inicio}
                  </p>
                  <p className="text-xs text-gray-400">{game.placar}</p>
                </div>

                {/* Direita: Time visitante */}
                <div className="flex-1 min-w-0 text-right">
                  <p className="text-sm font-semibold text-white truncate">
                    {game.away}
                  </p>
                </div>
              </div>

              {/* Info abaixo */}
              <div className="mt-3 flex items-center justify-between text-xs">
                <div className="flex items-center gap-4">
                  <span className="text-gray-400">{game.liga}</span>
                  <span className="text-gray-500">
                    {game.status === "NS" ? "Não iniciado" : game.status}
                  </span>
                </div>

                {/* Tempo até */}
                <div className="flex items-center gap-2">
                  {game.minutos_ate < 30 && game.minutos_ate >= 0 && (
                    <AlertCircle className="h-4 w-4 text-red-400 animate-pulse" />
                  )}
                  <span className={getTimeStyle(game.minutos_ate)}>
                    {game.minutos_ate < 0 ? (
                      <span className="text-yellow-400">Em andamento</span>
                    ) : (
                      formatTimeUntil(game.minutos_ate)
                    )}
                  </span>
                </div>
              </div>
            </div>
          ))}

          {/* Info polling */}
          <div className="mt-4 flex items-center justify-between rounded-lg bg-gray-800 p-3 text-xs">
            <div className="flex items-center gap-2 text-gray-400">
              <Clock className="h-4 w-4" />
              <span>Polling inteligente • {games.length > 3 ? "3 de " : ""}{games.length} jogos</span>
            </div>
            <span className="text-gray-500">
              {lastUpdate?.toLocaleTimeString("pt-BR")}
            </span>
          </div>
        </div>
      )}
    </Card>
  );
}

