package config

import (
	"errors"
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// AgentConfig — интервалы опроса, источники логов и адрес API-сервера.
// Все интервалы в секундах.
type AgentConfig struct {
	MetricsInterval   int      `yaml:"metrics_interval"`
	ServicesInterval  int      `yaml:"services_interval"`
	ProcessesInterval int      `yaml:"processes_interval"`
	LogSources        []string `yaml:"log_sources"`
	ServerURL         string   `yaml:"server_url"`
	TLSSkipVerify     bool     `yaml:"tls_skip_verify"`
}

// SecurityConfig — whitelist сервисов, которые агент имеет право рестартить
type SecurityConfig struct {
	AllowedServices []string `yaml:"allowed_services"`
}

// Config — корневая структура конфигурации агента из nullius.yaml
type Config struct {
	Agent    AgentConfig    `yaml:"agent"`
	Security SecurityConfig `yaml:"security"`
}

// Load читает YAML-конфиг. Если файл не найден — молча возвращает дефолты.
// Это нормальное поведение: при первом запуске конфига может ещё не быть.
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
		if errors.Is(err, os.ErrNotExist) {
			return cfg, nil
		}
		return nil, fmt.Errorf("ошибка чтения конфига: %w", err)
	}

	err = yaml.Unmarshal(data, cfg)
	return cfg, err
}
