"use client";

import { FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface SystemLogsProps {
  lines: string[];
}

function LogLine({ line }: { line: string }) {
  const isError = line.includes("ERROR");
  const isWarning = line.includes("WARNING");
  const isSignal = line.includes("Sinal") && line.includes("enviado");
  const isCycle = line.includes("Ciclo #");

  const className = cn(
    "font-mono text-xs truncate",
    isError && "text-red-400",
    isWarning && "text-amber-400",
    isSignal && "text-emerald-400 font-medium",
    isCycle && "text-cyan-400",
    !isError && !isWarning && !isSignal && !isCycle && "text-zinc-500"
  );

  return (
    <div className={className}>
      {line.length > 120 ? line.slice(0, 117) + "..." : line}
    </div>
  );
}

export function SystemLogs({ lines }: SystemLogsProps) {
  return (
    <section className="animate-fade-in">
      <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-cyan-400">
        <FileText className="h-5 w-5" />
        Log do sistema
      </h2>
      <div className="max-h-48 overflow-y-auto rounded-xl border border-white/5 bg-zinc-950 p-4 font-mono">
        {lines.length === 0 ? (
          <p className="text-sm text-zinc-500">[Log vazio]</p>
        ) : (
          <div className="space-y-1">
            {lines.map((line, i) => (
              <LogLine key={i} line={line} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
