FROM python:3.12-slim

WORKDIR /garden
COPY garden/ /garden/

RUN python3 /garden/traps/generate_traps.py

EXPOSE 8080
ENV GARDEN_HOST=0.0.0.0 GARDEN_PORT=8080

# Stdlib only — no pip installs, minimal surface.
CMD ["python3", "/garden/app/server.py"]
