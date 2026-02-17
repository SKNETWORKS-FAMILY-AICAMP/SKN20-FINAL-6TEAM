# Frontend Dockerfile - Vite + React
FROM node:20-alpine3.21

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Run Vite development server with host flag
CMD ["npm", "run", "dev", "--", "--host"]
