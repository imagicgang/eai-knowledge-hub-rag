package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"os"
	"time"
)

type server struct {
	aiURL  string
	client *http.Client
}

func main() {
	port := env("PORT", "8080")
	s := &server{aiURL: env("AI_SERVICE_URL", "http://localhost:8000"), client: &http.Client{Timeout: durationEnv("AI_REQUEST_TIMEOUT", 10*time.Minute)}}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.health)
	mux.HandleFunc("POST /api/v1/chat", s.chat)
	mux.HandleFunc("POST /api/v1/data-sources/upload", s.uploadDataSource)
	log.Printf("Go API listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, cors(mux)))
}

func (s *server) uploadDataSource(w http.ResponseWriter, r *http.Request) {
	startedAt := time.Now()
	r.Body = http.MaxBytesReader(w, r.Body, 20<<20)
	if err := r.ParseMultipartForm(20 << 20); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "file is required and must not exceed 20 MB"})
		return
	}
	file, header, err := r.FormFile("file")
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "file is required"})
		return
	}
	defer file.Close()
	log.Printf("ingestion started: file=%q", header.Filename)

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("file", header.Filename)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "could not prepare upload"})
		return
	}
	if _, err = io.Copy(part, file); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "could not read upload"})
		return
	}
	for _, field := range []string{"source_type", "scope", "system", "schema", "version"} {
		_ = writer.WriteField(field, r.FormValue(field))
	}
	_ = writer.Close()

	req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, s.aiURL+"/v1/ingest", &body)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "could not prepare ingestion"})
		return
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	resp, err := s.client.Do(req)
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) {
			log.Printf("ingestion timed out after %s: file=%q: %v", time.Since(startedAt).Round(time.Millisecond), header.Filename, err)
			writeJSON(w, http.StatusGatewayTimeout, map[string]string{"error": "AI ingestion timed out; try embedding chunking or a smaller file"})
			return
		}
		log.Printf("AI ingestion service unavailable: file=%q: %v", header.Filename, err)
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "AI ingestion service unavailable"})
		return
	}
	defer resp.Body.Close()
	log.Printf("ingestion finished: file=%q status=%d duration=%s", header.Filename, resp.StatusCode, time.Since(startedAt).Round(time.Millisecond))
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}

func (s *server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "service": "api"})
}

func (s *server) chat(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}
	var payload struct {
		Message string `json:"message"`
	}
	if json.Unmarshal(body, &payload) != nil || payload.Message == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "message is required"})
		return
	}
	req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, s.aiURL+"/v1/answer", bytes.NewReader(body))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "request failed"})
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := s.client.Do(req)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "AI service unavailable"})
		return
	}
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", env("WEB_ORIGIN", "http://localhost:3000"))
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func durationEnv(key string, fallback time.Duration) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	duration, err := time.ParseDuration(value)
	if err != nil || duration <= 0 {
		log.Printf("invalid %s=%q; using %s", key, value, fallback)
		return fallback
	}
	return duration
}
