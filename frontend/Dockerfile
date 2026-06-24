# Étape 1 : Build React
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
# npm ci (reproductible) avec repli npm install si le lock dérive d'une autre
# version de npm. Pas de --silent : on veut voir l'erreur réelle.
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
ENV REACT_APP_API_URL=/api/v1
RUN npm run build

# Étape 2 : Servir avec Nginx
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
