import type { NextConfig } from "next";

// API URL - usa variável de ambiente ou padrão para Docker
const apiBase =
  process.env.CPES_API_URL ||
  (process.env.NODE_ENV === "production"
    ? "http://api:8000"
    : "http://localhost:8000");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/cpes/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
  // Configurações para produção
  poweredByHeader: false,
  compress: true,
  productionBrowserSourceMaps: false,
};

export default nextConfig;
