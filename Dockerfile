FROM node:20-slim

WORKDIR /app

COPY package.json ./package.json
COPY src ./src
COPY README.md ./README.md

RUN mkdir -p /app/config /app/crawl_new/config

ENV NODE_ENV=production
ENV PORT=3000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/health').then((response) => { if (!response.ok) process.exit(1); }).catch(() => process.exit(1));"

CMD ["npm", "start"]
