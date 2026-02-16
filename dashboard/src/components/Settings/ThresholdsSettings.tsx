"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/Card";

interface ThresholdConfig {
  [key: string]: {
    valor: number;
    descricao: string;
  };
}

export const ThresholdsSettings: React.FC = () => {
  const [thresholds, setThresholds] = useState<ThresholdConfig>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetchThresholds();
  }, []);

  const fetchThresholds = async () => {
    try {
      const response = await fetch("/api/cpes/config/thresholds");
      const data = await response.json();
      setThresholds(data.thresholds || {});
    } catch (error) {
      console.error("Erro ao buscar thresholds:", error);
      setMessage("Erro ao carregar configuração");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key: string, value: string) => {
    setThresholds((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        valor: parseFloat(value) || 0,
      },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updates: { [key: string]: number } = {};
      for (const [key, config] of Object.entries(thresholds)) {
        updates[key] = config.valor;
      }

      const response = await fetch("/api/cpes/config/thresholds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        setMessage("✓ Thresholds atualizados com sucesso");
        setTimeout(() => setMessage(""), 3000);
      } else {
        setMessage("✗ Erro ao atualizar thresholds");
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

  const formatLabel = (key: string) => {
    return key
      .replace(/_/g, " ")
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  return (
    <Card className="p-6">
      <h2 className="text-2xl font-bold mb-6 text-white">
        Limiares de Decisão
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {Object.entries(thresholds).map(([key, config]) => (
          <div key={key} className="bg-gray-800 rounded-lg p-4">
            <label className="block mb-2">
              <span className="text-sm font-medium text-gray-200">
                {formatLabel(key)}
              </span>
              <p className="text-xs text-gray-400 mb-3">{config.descricao}</p>
            </label>
            <div className="flex items-center gap-3">
              <input
                type="number"
                step="0.1"
                value={config.valor}
                onChange={(e) => handleChange(key, e.target.value)}
                className="flex-1 bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:border-green-500 focus:outline-none"
              />
              <span className="text-white font-medium w-10 text-right">
                {config.valor.toFixed(2)}
              </span>
            </div>
          </div>
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
    </Card>
  );
};
