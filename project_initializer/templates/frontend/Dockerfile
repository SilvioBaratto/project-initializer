# Stage 1: Build Angular application
FROM node:26-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies for Angular CLI)
RUN npm install --legacy-peer-deps --no-audit --no-fund

# Copy application source
COPY . .

# Build Angular app for production
RUN npm run build -- --configuration=production

# Stage 2: Serve with nginx
# The stable branch (an even minor), not the moving `alpine` tag: that one follows
# mainline, so a rebuild could change nginx branch. nginx.conf uses $request_id as
# the CSP nonce, which must be unguessable: stable draws it from random bytes on
# every request, while mainline (1.31.2 on) derives it with SipHash, so changing
# branch means re-checking how the nonce is produced.
FROM nginx:1.30-alpine

# Remove default nginx config
RUN rm -rf /etc/nginx/conf.d/*

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built Angular app from builder stage
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

# Create non-root user for security
RUN addgroup -g 1001 -S nginx-user && \
    adduser -u 1001 -S nginx-user -G nginx-user && \
    chown -R nginx-user:nginx-user /usr/share/nginx/html && \
    chown -R nginx-user:nginx-user /var/cache/nginx && \
    chown -R nginx-user:nginx-user /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown nginx-user:nginx-user /var/run/nginx.pid

# Expose port 80
EXPOSE 80

# Health check
# 127.0.0.1, not localhost: nginx.conf listens on IPv4 only (`listen 80;`), while
# localhost resolves to ::1 first here — which would fail the check forever.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/health || exit 1

# Start nginx
USER nginx-user
CMD ["nginx", "-g", "daemon off;"]
