# Build
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN yarn install
COPY . .
ENV REACT_APP_BACKEND_URL=https://api.odoo.ambissionindustries.cloud
RUN yarn build

# Serve
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
