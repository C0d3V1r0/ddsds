//go:build integration

package tests

import (
	"testing"
	"time"

	"github.com/nullius/agent/ws"
)

// Интеграционный тест: проверяет, что агент может подключиться к живому серверу.
// Запускать только с тегом: go test -tags=integration
func TestAgentConnectsToBackend(t *testing.T) {
	client := ws.NewClient(
		"ws://127.0.0.1:8000/ws/agent",
		"test-secret",
		false,
		func(id, cmd string, params map[string]interface{}) {},
	)
	go func() {
		client.Run()
	}()

	time.Sleep(2 * time.Second)
	err := client.Send(map[string]string{"type": "ping"})
	if err != nil {
		t.Fatalf("Failed to send: %v", err)
	}
	t.Log("Agent connected and sent ping successfully")
}
