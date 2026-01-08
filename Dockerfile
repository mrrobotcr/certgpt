# ExamsGPT Web Server - Production Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Install frontend dependencies and build
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Install server dependencies
WORKDIR /app/server
COPY server/package*.json ./
RUN npm ci

COPY server/ ./
RUN npm run build

# Production image
FROM node:20-alpine AS production

WORKDIR /app

# Copy built frontend
COPY --from=builder /app/frontend/dist ./frontend/dist

# Copy server
COPY --from=builder /app/server/dist ./server/dist
COPY --from=builder /app/server/node_modules ./server/node_modules
COPY --from=builder /app/server/package.json ./server/

WORKDIR /app/server

ENV NODE_ENV=production
ENV PORT=3000

EXPOSE 3000

CMD ["node", "dist/index.js"]
