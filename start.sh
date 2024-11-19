#!/bin/bash
start_time=$(date +%s)

docker-compose up -d

# Loop until curl command exits with a success status
until curl -f localhost:8000/v1.0/status; do
  echo "Waiting for container to become ready..."
  sleep 1
done

end_time=$(date +%s)
echo "Container is ready after $((end_time - start_time)) seconds."
