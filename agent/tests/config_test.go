package tests

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/nullius/agent/config"
)

// - проверяет корректный парсинг полного yaml-конфига
func TestLoadConfig(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nullius.yaml")
	yamlContent := `
agent:
  metrics_interval: 10
  services_interval: 60
  log_sources:
    - /var/log/auth.log
    - /var/log/nginx/access.log
security:
  allowed_services:
    - nginx
    - redis
`
	os.WriteFile(path, []byte(yamlContent), 0644)

	cfg, err := config.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Agent.MetricsInterval != 10 {
		t.Errorf("expected 10, got %d", cfg.Agent.MetricsInterval)
	}
	if len(cfg.Agent.LogSources) != 2 {
		t.Errorf("expected 2 log sources, got %d", len(cfg.Agent.LogSources))
	}
	if len(cfg.Security.AllowedServices) != 2 {
		t.Errorf("expected 2 allowed services, got %d", len(cfg.Security.AllowedServices))
	}
}

// - проверяет что при частичном конфиге неуказанные поля сохраняют дефолты
func TestLoadConfigDefaults(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nullius.yaml")
	os.WriteFile(path, []byte("agent:\n  metrics_interval: 3\n"), 0644)

	cfg, err := config.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Agent.MetricsInterval != 3 {
		t.Errorf("expected 3, got %d", cfg.Agent.MetricsInterval)
	}
	if cfg.Agent.ServicesInterval != 30 {
		t.Errorf("expected default 30, got %d", cfg.Agent.ServicesInterval)
	}
	if cfg.Agent.ProcessesInterval != 10 {
		t.Errorf("expected default processes_interval 10, got %d", cfg.Agent.ProcessesInterval)
	}
	if cfg.Agent.TLSSkipVerify != false {
		t.Errorf("expected default tls_skip_verify false, got %v", cfg.Agent.TLSSkipVerify)
	}
}

// - проверяет что TLS и ProcessesInterval корректно парсятся из yaml
func TestLoadConfigTLSAndProcesses(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nullius.yaml")
	yamlContent := `
agent:
  processes_interval: 20
  tls_skip_verify: true
`
	os.WriteFile(path, []byte(yamlContent), 0644)

	cfg, err := config.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Agent.ProcessesInterval != 20 {
		t.Errorf("expected 20, got %d", cfg.Agent.ProcessesInterval)
	}
	if cfg.Agent.TLSSkipVerify != true {
		t.Errorf("expected true, got %v", cfg.Agent.TLSSkipVerify)
	}
}

// - проверяет что при отсутствии файла возвращаются дефолты без ошибки
func TestLoadConfigMissingFile(t *testing.T) {
	cfg, err := config.Load("/nonexistent/path/to/config.yaml")
	if err != nil {
		t.Fatalf("expected no error for missing file, got %v", err)
	}
	if cfg.Agent.MetricsInterval != 5 {
		t.Errorf("expected default 5, got %d", cfg.Agent.MetricsInterval)
	}
	if cfg.Agent.ServerURL != "ws://127.0.0.1:8000/ws/agent" {
		t.Errorf("expected default server URL, got %s", cfg.Agent.ServerURL)
	}
}
