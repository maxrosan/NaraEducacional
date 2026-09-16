# Dockerfile para frontend React - NARA
FROM node:20-alpine

# Criar diretório de trabalho
WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar dependências
RUN npm ci --legacy-peer-deps

# Copiar código do projeto
COPY . .

# Expor porta do Vite
EXPOSE 5173

# Comando padrão para desenvolvimento
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
