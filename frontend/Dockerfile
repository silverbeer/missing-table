# Build stage
FROM node:20-slim AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build arguments (for Vite, must be prefixed with VITE_)
ARG VITE_API_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_DISABLE_SECURITY
ARG VITE_FARO_URL
ARG VITE_FARO_APP_NAME=missing-table-frontend

# Set as environment variables for Vite build
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
ENV VITE_DISABLE_SECURITY=$VITE_DISABLE_SECURITY
ENV VITE_FARO_URL=$VITE_FARO_URL
ENV VITE_FARO_APP_NAME=$VITE_FARO_APP_NAME

# Build the application (Vite is FAST - typically under 30 seconds)
RUN npm run build

# Production stage - use nginx for static file serving
FROM nginx:alpine

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration for SPA routing
RUN echo 'server { \
    listen 8080; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /health { \
        access_log off; \
        return 200 "OK"; \
        add_header Content-Type text/plain; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
