FROM node:22-bookworm-slim AS web
WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci
COPY web ./web
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY engine ./engine
COPY validation ./validation
COPY service ./service
COPY fixtures ./fixtures
COPY docs ./docs
COPY LICENSE server.py ./
COPY --from=web /app/web/dist ./web/dist
RUN python3 engine/build.py && useradd --create-home stormpilot && chown -R stormpilot:stormpilot /app
USER stormpilot
ENV PORT=8787
EXPOSE 8787
CMD ["python3", "server.py", "--host", "0.0.0.0"]
