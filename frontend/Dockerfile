# =============================================================================
# ML Experiment Hub - Frontend Dockerfile
# Multi-stage: dev (Vite HMR) / prod (nginx with SPA + reverse proxy)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage: deps - Install node_modules (shared cache layer)
# ---------------------------------------------------------------------------
FROM node:20-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---------------------------------------------------------------------------
# Stage: dev - Vite dev server with HMR
# ---------------------------------------------------------------------------
FROM node:20-alpine AS dev

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./

# Source code will be bind-mounted at runtime
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---------------------------------------------------------------------------
# Stage: build - Build production assets
# ---------------------------------------------------------------------------
FROM deps AS build

WORKDIR /app
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage: prod - Nginx serving static + reverse proxy
# ---------------------------------------------------------------------------
FROM nginx:alpine AS prod

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
