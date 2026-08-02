FROM nousresearch/hermes-agent:latest

RUN apt-get update && apt-get install -y --no-install-recommends python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY app/requirements.txt app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r app/requirements.txt

COPY app app
COPY entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

ENV HERMES_INTERNAL_URL=http://127.0.0.1:9119
ENV HERMES_HOME=/data
ENV PORT=8080

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
