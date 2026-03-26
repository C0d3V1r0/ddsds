package config

import (
	"errors"
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// - конфигурация интервалов сбора и источников логов агента
type AgentConfig struct {
	MetricsInterval   int      `yaml:"metrics_interval"`
	ServicesInterval  int      `yaml:"services_interval"`
	ProcessesInterval int      `yaml:"processes_interval"`
	LogSources        []string `yaml:"log_sources"`
	ServerURL         string   `yaml:"server_url"`
	TLSSkipVerify     bool     `yaml:"tls_skip_verify"`
}

// - список разрешённых сервисов для мониторинга
type SecurityConfig struct {
	AllowedServices []string `yaml:"allowed_services"`
}

// - корневая структура конфигурации агента
type Config struct {
	Agent    AgentConfig    `yaml:"agent"`
	Security SecurityConfig `yaml:"security"`
}

// - загружает конфиг из yaml-файла, при отсутствии файла возвращает дефолты
func Load(path string) (*Config, error) {
	cfg := &Config{
		Agent: AgentConfig{
			MetricsInterval:   5,
			ServicesInterval:  30,
			ProcessesInterval: 10,
			LogSources:        []string{"/var/log/auth.log"},
			ServerURL:         "ws://127.0.0.1:8000/ws/agent",
			TLSSkipVerify:     false,
		},
		Security: SecurityConfig{
			AllowedServices: []string{"nginx", "postgresql", "redis", "mysql", "docker"},
		},
	}

	data, err := os.ReadFile(path)
	if err != nil {
		// - файл не найден — используем дефолтные значения
		if errors.Is(err, os.ErrNotExist) {
			return cfg, nil
		}
		return nil, fmt.Errorf("// - Ошибка чтения конфига: %w", err)
	}

	err = yaml.Unmarshal(data, cfg)
	return cfg, err
}
