# netlogo-services

HTTP-wrapper API for JVM NetLogo commands. Internal-use only.

## Sourcing the image
Image is available at `ghcr.io/netlogo/netlogo-services:latest`.

## API documentation

### `GET /preview`

Generates a preview image for a NetLogo model.

**Query parameters**

| Parameter   | Required | Description                          |
|-------------|----------|--------------------------------------|
| `model_url` | yes      | URL to a `.nlogox` file to render    |

The `model_url` value must be URL-encoded. In particular, `&` in paths must be passed as `%26` to avoid being parsed as a query separator.

**Response:** `image/png` on success.

## Local development
```bash
docker build -t netlogo-services .
docker run -p 8080:8080 netlogo-services
```

## Kubernetes deployment
Recommended k8s pod security context:
```yaml
securityContext:
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
```