# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files and install dependencies (skip postinstall — prisma schema not yet available)
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --ignore-scripts; else npm install --ignore-scripts; fi

# Copy source code
COPY . .

# Run postinstall scripts now that prisma schema is available
RUN npx prisma generate

# Generate BAML client
RUN npx baml-cli generate

# Build the application
RUN npm run build

# Runtime stage
FROM node:22-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup

# Copy package files and lockfile from builder, install prod deps only
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/package-lock.json ./package-lock.json
RUN npm ci --omit=dev --ignore-scripts

# Copy generated clients and built application from builder
COPY --from=builder /app/generated ./generated
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/baml_client ./baml_client
COPY --from=builder /app/baml_src ./baml_src

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Change ownership
RUN chown -R appuser:appgroup /app /entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Run the application
CMD ["node", "dist/src/main"]
