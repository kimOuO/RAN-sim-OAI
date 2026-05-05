# Builder stage
FROM node:20-alpine AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_OMNIVERSE_URL=http://localhost:8001
ARG NEXT_PUBLIC_VNC_URL=http://localhost:6080/vnc.html
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8001/api/v0.1/RAN/UE/live

ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_OMNIVERSE_URL=${NEXT_PUBLIC_OMNIVERSE_URL}
ENV NEXT_PUBLIC_VNC_URL=${NEXT_PUBLIC_VNC_URL}
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}
ENV HOSTNAME=0.0.0.0

COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . .
RUN npm run build

# Runner stage
FROM node:20-alpine
WORKDIR /app

RUN apk add --no-cache curl

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
