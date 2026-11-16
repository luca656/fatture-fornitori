FROM node:22-alpine
WORKDIR /app
COPY server.js index.html ./
ENV DATA_DIR=/data PORT=8080
VOLUME /data
EXPOSE 8080
CMD ["node", "server.js"]
