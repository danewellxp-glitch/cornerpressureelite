# CPES Dashboard - Next.js
FROM node:20-alpine

WORKDIR /app

# Dependências
COPY package.json package-lock.json* ./
RUN npm ci

# Código
COPY . .

# URL da API (pode ser sobrescrita via env)
ENV CPES_API_URL=http://api:8000
ENV NODE_ENV=production

# Build para produção
RUN npm run build

EXPOSE 3001
CMD ["npm", "start"]
