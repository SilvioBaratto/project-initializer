# ── Development stage (used by docker-compose for hot-reload) ──
FROM node:26-alpine AS dev

WORKDIR /app

RUN apk add --no-cache netcat-openbsd

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --ignore-scripts; else npm install --ignore-scripts; fi

COPY . .
RUN npx prisma generate

# A CRLF checkout on Windows leaves a carriage return in the shebang line, which makes the kernel
# look for an interpreter named "sh\r".
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# The compose bind mount hides the client generated above, so it is rebuilt at every start.
ENV PRISMA_GENERATE_ON_START=true

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["npm", "run", "start:dev"]

# ── Build stage (compiles TypeScript for production) ──
FROM dev AS builder

RUN npm run build

# ── Production stage ──
FROM node:26-alpine

WORKDIR /app

# PORT must match EXPOSE and the HEALTHCHECK below; the application default is 3000.
ENV NODE_ENV=production PORT=8000

RUN apk add --no-cache netcat-openbsd

RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/package-lock.json ./package-lock.json
RUN npm ci --omit=dev --ignore-scripts

COPY --from=builder /app/generated ./generated
COPY --from=builder /app/prisma ./prisma
# The entrypoint runs `prisma migrate deploy`, which takes its datasource from this file and
# stops with "datasource.url property is required" without it.
COPY --from=builder /app/prisma.config.ts ./prisma.config.ts
COPY --from=builder /app/dist ./dist

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

RUN chown -R appuser:appgroup /app /entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/api/v1/health/liveness || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["node", "dist/src/main"]
