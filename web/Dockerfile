# Banker CRM web — Next.js standalone for Cloud Run
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Public API URL baked into the client bundle (set at deploy time).
ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# Optional same-origin rewrite target (server-side only).
ARG CRM_API_ORIGIN=
ENV CRM_API_ORIGIN=$CRM_API_ORIGIN
# Visible in the top nav so you can confirm the live build.
ARG NEXT_PUBLIC_WEB_BUILD_ID=dev-local
ENV NEXT_PUBLIC_WEB_BUILD_ID=$NEXT_PUBLIC_WEB_BUILD_ID

RUN npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=8080
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 8080
CMD ["node", "server.js"]
