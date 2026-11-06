FROM node:24-alpine
WORKDIR /app
COPY --chown=node:node package.json server.mjs lib.mjs ./
COPY --chown=node:node public ./public
COPY --chown=node:node data ./data
USER node
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.mjs"]
