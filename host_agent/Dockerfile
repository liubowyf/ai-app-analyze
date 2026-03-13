FROM docker:27-cli AS docker_cli

FROM public.ecr.aws/zeek/zeek:lts AS builder

WORKDIR /app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        cargo \
        rustc \
        tcpdump \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:/usr/local/zeek/bin:/usr/local/bin:${PATH}

COPY host_agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

FROM public.ecr.aws/zeek/zeek:lts

WORKDIR /app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        tcpdump \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/venv/bin:/usr/local/zeek/bin:/usr/local/bin:${PATH}

COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=builder /opt/venv /opt/venv
COPY host_agent /app/host_agent
COPY core /app/core

ENV PYTHONPATH=/app
ENV HOST_AGENT_CAPTURE_DIR=/var/lib/redroid-host-agent

CMD ["sh", "-lc", "/opt/venv/bin/python -m uvicorn host_agent.app:app --host 0.0.0.0 --port ${HOST_AGENT_PORT:-18080}"]
