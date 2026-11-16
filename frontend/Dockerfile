FROM node:22-alpine@sha256:0e1754758c2df4cfa3e68d59e2e1b7374bb7fd9ea6328eaaacf15cc934af8202 AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
ARG VITE_DEMO=false
ENV VITE_DEMO=${VITE_DEMO}
RUN npm run build

FROM nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11
COPY --from=build /web/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/content-factory.conf.template
COPY 15-web-token.sh /docker-entrypoint.d/15-web-token.sh
RUN chmod +x /docker-entrypoint.d/15-web-token.sh
