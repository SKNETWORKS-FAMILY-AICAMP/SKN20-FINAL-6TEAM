# Frontend Dockerfile - Vite + React
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Run Vite development server with host flag
CMD ["npm", "run", "dev", "--", "--host"]
