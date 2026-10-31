ARG BASE_NODE_IMAGE=node:20-alpine
FROM ${BASE_NODE_IMAGE} AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

ARG BASE_NGINX_IMAGE=nginx:alpine
FROM ${BASE_NGINX_IMAGE}
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
