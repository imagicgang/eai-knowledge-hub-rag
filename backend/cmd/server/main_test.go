package main

import (
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

func TestChatRequiresMessage(t *testing.T) {
	s := &server{}
	w := httptest.NewRecorder()
	s.chat(w, httptest.NewRequest(http.MethodPost, "/api/v1/chat", strings.NewReader(`{}`)))
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}
