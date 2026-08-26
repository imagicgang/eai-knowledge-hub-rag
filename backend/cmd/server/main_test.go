package main

import (
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHealth(t *testing.T) {
	s := &server{}
	w := httptest.NewRecorder()
	s.health(w, httptest.NewRequest(http.MethodGet, "/health", nil))
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), `"status":"ok"`) {
		t.Fatalf("unexpected health response: %d %s", w.Code, w.Body.String())
	}
}

func TestUploadForwardsFileToAI(t *testing.T) {
	ai := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/ingest" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		if err := r.ParseMultipartForm(1 << 20); err != nil {
			t.Fatal(err)
		}
		file, header, err := r.FormFile("file")
		if err != nil {
			t.Fatal(err)
		}
		defer file.Close()
		content, _ := io.ReadAll(file)
		if header.Filename != "services.csv" || string(content) != "name,owner\nOrder,Commerce" {
			t.Fatalf("unexpected upload: %s %q", header.Filename, content)
		}
		writeJSON(w, http.StatusCreated, map[string]any{"source": header.Filename, "chunks": 1})
	}))
	defer ai.Close()

	var body strings.Builder
	writer := multipart.NewWriter(&body)
	part, _ := writer.CreateFormFile("file", "services.csv")
	_, _ = part.Write([]byte("name,owner\nOrder,Commerce"))
	_ = writer.WriteField("source_type", "cmdb")
	_ = writer.Close()

	s := &server{aiURL: ai.URL, client: ai.Client()}
	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/data-sources/upload", strings.NewReader(body.String()))
	req.Header.Set("Content-Type", writer.FormDataContentType())
	s.uploadDataSource(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
}

func TestChatRequiresMessage(t *testing.T) {
	s := &server{}
	w := httptest.NewRecorder()
	s.chat(w, httptest.NewRequest(http.MethodPost, "/api/v1/chat", strings.NewReader(`{}`)))
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}
