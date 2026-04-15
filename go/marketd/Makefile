.PHONY: build test run-shadow fmt

build:
	go build ./cmd/marketd

test:
	go test ./...

run-shadow:
	MARKETD_SHADOW_MODE=true go run ./cmd/marketd

fmt:
	gofmt -w ./cmd ./internal
