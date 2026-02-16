"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/Card";

interface League {
  id: number;
  nome: string;
  pais: string;
  media_esperada: number;
}

export const LeaguesSettings: React.FC = () => {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [activeLigas, setActiveLigas] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetchLeaguesConfig();
  }, []);

  const fetchLeaguesConfig = async () => {
    try {
      const response = await fetch("/api/cpes/config");
      const data = await response.json();
      setLeagues(data.ligas || []);

      const activeResponse = await fetch("/api/cpes/config/leagues");
      const activeData = await activeResponse.json();
      setActiveLigas(activeData.ativas || []);
    } catch (error) {
      console.error("Erro ao buscar ligas:", error);
      setMessage("Erro ao carregar configuração");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleLeague = (ligaId: number) => {
    setActiveLigas((prev) =>
      prev.includes(ligaId)
        ? prev.filter((id) => id !== ligaId)
        : [...prev, ligaId]
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch("/api/cpes/config/leagues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ liga_ids: activeLigas }),
      });

      if (response.ok) {
        setMessage("✓ Ligas atualizadas com sucesso");
        setTimeout(() => setMessage(""), 3000);
      } else {
        setMessage("✗ Erro ao atualizar ligas");
      }
    } catch (error) {
      console.error("Erro ao salvar:", error);
      setMessage("✗ Erro na requisição");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-6">
        <p className="text-gray-400">Carregando configurações...</p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h2 className="text-2xl font-bold mb-6 text-white">Ligas Monitoradas</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {leagues.map((liga) => (
          <label
            key={liga.id}
            className="flex items-center p-4 bg-gray-800 rounded-lg cursor-pointer hover:bg-gray-700 transition"
          >
            <input
              type="checkbox"
              checked={activeLigas.includes(liga.id)}
              onChange={() => handleToggleLeague(liga.id)}
              className="w-5 h-5 mr-4 accent-green-500"
            />
            <div className="flex-1">
              <p className="font-semibold text-white">{liga.nome}</p>
              <p className="text-sm text-gray-400">
                {liga.pais} • Média: {liga.media_esperada} escanteios
              </p>
            </div>
          </label>
        ))}
      </div>

      <div className="flex gap-4 items-center">
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-6 py-2 rounded-lg font-medium transition"
        >
          {saving ? "Salvando..." : "Salvar Configuração"}
        </button>
        {message && (
          <p
            className={`text-sm font-medium ${
              message.includes("✓") ? "text-green-400" : "text-red-400"
            }`}
          >
            {message}
          </p>
        )}
      </div>

      <p className="text-xs text-gray-500 mt-6">
        Selecionadas {activeLigas.length} de {leagues.length} ligas
      </p>
    </Card>
  );
};
