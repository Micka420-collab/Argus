FROM nginx:alpine
COPY nginx.conf /etc/nginx/nginx.conf
# Les certificats sont montés depuis le volume
RUN mkdir -p /etc/nginx/certs
EXPOSE 80 443
