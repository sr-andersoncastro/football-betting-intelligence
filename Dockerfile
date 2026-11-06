FROM node:24-alpine
WORKDIR /app
COPY --chown=node:node package.json server.mjs lib.mjs analytics.mjs model.mjs markets.mjs store.mjs ./
COPY --chown=node:node providers ./providers
COPY --chown=node:node public ./public
COPY --chown=node:node data ./data
RUN mkdir runtime && chown node:node runtime
USER node
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.mjs"]

