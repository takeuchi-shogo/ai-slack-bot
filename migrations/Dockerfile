FROM golang:1.23-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates

# Install migrate tool
RUN go install -tags 'mysql' github.com/golang-migrate/migrate/v4/cmd/migrate@v4.17.0

# Create directories for the final image
WORKDIR /app

FROM alpine:3.18

# Install runtime dependencies
RUN apk add --no-cache ca-certificates mysql-client

# Copy binaries from builder stage
COPY --from=builder /go/bin/migrate /usr/local/bin/migrate

# Set working directory
WORKDIR /app/migrations

# Copy migration files
COPY . .

# Create directory for migrations
RUN mkdir -p schema

# Create entrypoint script
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'set -e' >> /entrypoint.sh && \
    echo 'echo "Waiting for MySQL to be ready..."' >> /entrypoint.sh && \
    echo 'while ! mysql -h mysql -u user -ppassword -e "SELECT 1" > /dev/null 2>&1; do' >> /entrypoint.sh && \
    echo '  echo "MySQL is not ready yet, waiting..."' >> /entrypoint.sh && \
    echo '  sleep 2' >> /entrypoint.sh && \
    echo 'done' >> /entrypoint.sh && \
    echo 'echo "MySQL is ready, checking for migration files..."' >> /entrypoint.sh && \
    echo 'if [ -z "$(ls -A ./schema/*.sql 2>/dev/null)" ]; then' >> /entrypoint.sh && \
    echo '  echo "No migration files found. Please add migration files manually."' >> /entrypoint.sh && \
    echo '  echo "Example: touch ./schema/1_create_tables.up.sql"' >> /entrypoint.sh && \
    echo '  exit 1' >> /entrypoint.sh && \
    echo 'fi' >> /entrypoint.sh && \
    echo 'echo "Running migrations..."' >> /entrypoint.sh && \
    echo 'migrate -path ./schema -database "mysql://user:password@tcp(mysql:3306)/slackbot" up' >> /entrypoint.sh && \
    echo 'echo "Migrations completed!"' >> /entrypoint.sh && \
    echo 'exit 0' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
