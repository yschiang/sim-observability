FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY proto /proto
RUN mkdir -p /app/gen
RUN python -m grpc_tools.protoc -I/proto --python_out=/app/gen --grpc_python_out=/app/gen /proto/device_proxy.proto
ENV PYTHONPATH=/app/gen
COPY . .
CMD ["python", "server.py"]