import Link from "next/link";
import { LeaguesSettings } from "@/components/Settings/LeaguesSettings";
import { ThresholdsSettings } from "@/components/Settings/ThresholdsSettings";

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/"
            className="text-gray-400 hover:text-white transition mb-4 inline-block"
          >
            ← Voltar ao Dashboard
          </Link>
          <h1 className="text-4xl font-bold text-white">Configurações</h1>
          <p className="text-gray-400 mt-2">
            Personalize ligas monitoradas e limiares de decisão
          </p>
        </div>

        {/* Settings Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <LeaguesSettings />
          <ThresholdsSettings />
        </div>

        {/* Info Box */}
        <div className="mt-8 bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 text-green-400">Sobre</h3>
          <ul className="text-sm text-gray-300 space-y-2">
            <li>
              <strong>Ligas Monitoradas:</strong> Escolha quais ligas serão
              analisadas em tempo real. Alterações levam efeito no próximo ciclo
              de polling.
            </li>
            <li>
              <strong>Min Score:</strong> Valor mínimo do pressure_score para
              gerar sinais NORMAL e PREMIUM.
            </li>
            <li>
              <strong>Min Edge:</strong> Valor mínimo de edge (diferença entre
              projeção e linha) para considerar uma oportunidade.
            </li>
            <li>
              <strong>Impacto:</strong> Limites mais altos = sinais mais
              conservadores. Limites mais baixos = mais sinais, mais falsos
              positivos.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
